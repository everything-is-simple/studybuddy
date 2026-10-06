"""Local TTS skill: cache-backed synthesis and ephemeral playback sessions."""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import uuid
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Protocol


MAX_TEXT_CHARS = 12_000
MIN_RATE = 0.5
MAX_RATE = 2.0


class TtsError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TtsArtifact:
    path: Path
    engine: str
    voice: str | None
    duration_ms: int
    fallback_used: bool = False


@dataclass
class Playback:
    playback_id: str
    artifact: TtsArtifact
    state: str = "playing"
    position_ms: int = 0
    rate: float = 1.0
    created_at: str = ""


class TtsProvider(Protocol):
    provider_id: str
    network_required: bool

    def synthesize(self, text: str, output: Path, *, voice: str | None, rate: float,
                   timeout_seconds: float) -> None: ...


class FakeTtsProvider:
    provider_id = "fake"
    network_required = False

    def synthesize(self, text: str, output: Path, *, voice: str | None, rate: float,
                   timeout_seconds: float) -> None:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        frames = max(800, min(8_000, len(text) * 80))
        output.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8_000)
            audio.writeframes((digest * ((frames * 2 // len(digest)) + 1))[:frames * 2])


class SapiTtsProvider:
    provider_id = "sapi"
    network_required = False

    def __init__(self, executable: str | None = None):
        self.executable = executable or "powershell.exe"

    def synthesize(self, text: str, output: Path, *, voice: str | None, rate: float,
                   timeout_seconds: float) -> None:
        if os.name != "nt":
            raise TtsError("tts_provider_unavailable")
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$text=[Console]::In.ReadToEnd(); "
                  "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$s.Rate={max(-10, min(10, round((rate - 1) * 10)))}; "
                  "$s.SetOutputToWaveFile($env:STUDYBUDDY_TTS_OUTPUT); "
                  "$s.Speak($text); $s.Dispose()")
        environment = os.environ.copy()
        environment["STUDYBUDDY_TTS_OUTPUT"] = str(output)
        try:
            result = subprocess.run([self.executable, "-NoProfile", "-NonInteractive",
                                     "-Command", script], input=text, env=environment,
                                    text=True, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=timeout_seconds,
                                    check=False)
        except subprocess.TimeoutExpired:
            raise TtsError("tts_timeout") from None
        except OSError:
            raise TtsError("tts_provider_unavailable") from None
        if result.returncode != 0 or not output.is_file():
            raise TtsError("tts_provider_unavailable")


class EdgeTtsProvider:
    provider_id = "edge-tts"
    network_required = True

    def __init__(self, command: str):
        self.command = command

    def synthesize(self, text: str, output: Path, *, voice: str | None, rate: float,
                   timeout_seconds: float) -> None:
        if not self.command:
            raise TtsError("tts_not_configured")
        args = [self.command, "--text", text, "--write-media", str(output)]
        if voice:
            args.extend(["--voice", voice])
        try:
            result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            raise TtsError("tts_timeout") from None
        except OSError:
            raise TtsError("tts_provider_unavailable") from None
        if result.returncode != 0 or not output.is_file():
            raise TtsError("tts_provider_unavailable")


def _duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as audio:
            return round(audio.getnframes() * 1000 / max(1, audio.getframerate()))
    except (OSError, wave.Error):
        return 0


class TtsManager:
    def __init__(self, config):
        self.config = config
        self._playbacks: dict[str, Playback] = {}
        self._lock = Lock()
        self._engine = config.tts_provider_id

    def update_config(self, config) -> None:
        """Apply the effective settings without discarding active playback state."""
        self.config = config
        self._engine = config.tts_provider_id

    def capabilities(self) -> dict[str, object]:
        provider = self.config.tts_provider_id
        if not self.config.tts_enabled:
            status = "disabled"
        elif provider == "fake":
            status = "demo"
        elif provider in {"sapi", "edge-tts"}:
            status = "configured" if (provider == "sapi" or self.config.tts_edge_command) else "not_configured"
        else:
            status = "not_configured"
        return {"status": status, "configured": status in {"configured", "demo"},
                "verification_status": "not_verified" if status == "configured" else "not_applicable",
                "provider_id": provider, "voice": self.config.tts_voice,
                "network_required": provider == "edge-tts",
                "supports": {"speak": status in {"configured", "demo"}, "pause": True,
                             "retry": True, "cache": True},
                "cache_max_bytes": self.config.tts_cache_max_bytes}

    def _prune_cache(self, cache: Path, keep: Path) -> None:
        files = [path for path in cache.glob('*.wav') if path.is_file()]
        total = sum(path.stat().st_size for path in files)
        if total <= self.config.tts_cache_max_bytes:
            return
        for path in sorted(files, key=lambda item: item.stat().st_mtime):
            if path == keep:
                continue
            try:
                total -= path.stat().st_size
                path.unlink()
            except OSError:
                continue
            if total <= self.config.tts_cache_max_bytes:
                break

    def _provider(self, engine: str) -> TtsProvider:
        if engine == "fake" and self.config.tts_enabled:
            return FakeTtsProvider()
        if engine == "sapi" and self.config.tts_enabled and self.config.tts_provider_id == "sapi":
            return SapiTtsProvider(self.config.tts_sapi_path)
        if engine == "edge-tts" and self.config.tts_enabled and self.config.tts_provider_id == "edge-tts":
            return EdgeTtsProvider(self.config.tts_edge_command or "")
        raise TtsError("tts_not_configured")

    def speak(self, text: str, *, engine: str | None = None, voice: str | None = None,
               rate: float = 1.0) -> Playback:
        text = text.strip() if isinstance(text, str) else ""
        if not text or len(text) > MAX_TEXT_CHARS or not MIN_RATE <= rate <= MAX_RATE:
            raise TtsError("tts_invalid_request")
        selected = engine or self._engine or self.config.tts_provider_id
        if selected is None:
            raise TtsError("tts_not_configured")
        if selected not in {"fake", "sapi", "edge-tts"}:
            raise TtsError("tts_invalid_request")
        provider = self._provider(selected)
        voice = voice or self.config.tts_voice
        fingerprint = hashlib.sha256(f"{selected}\0{voice or ''}\0{rate}\0{text}".encode()).hexdigest()
        cache = self.config.data_root / "tts-cache"
        path = cache / f"{fingerprint}.wav"
        fallback = False
        if not path.is_file():
            temporary = None
            try:
                cache.mkdir(parents=True, exist_ok=True)
                fd, name = tempfile.mkstemp(prefix=".tts-", suffix=".wav", dir=cache)
                os.close(fd)
                temporary = Path(name)
                try:
                    provider.synthesize(text, temporary, voice=voice, rate=rate,
                                        timeout_seconds=self.config.tts_timeout_seconds)
                except TtsError:
                    if selected == "edge-tts" and self.config.tts_fallback_to_sapi:
                        SapiTtsProvider(self.config.tts_sapi_path).synthesize(text, temporary, voice=voice,
                                                                            rate=rate, timeout_seconds=self.config.tts_timeout_seconds)
                        selected, fallback = "sapi", True
                    else:
                        raise
                if _duration_ms(temporary) <= 0:
                    raise TtsError("tts_audio_unavailable")
                temporary.replace(path)
                self._prune_cache(cache, path)
            except TtsError:
                raise
            except OSError:
                raise TtsError("tts_audio_unavailable") from None
            finally:
                if temporary and temporary.exists():
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
        duration = _duration_ms(path)
        try:
            path.touch()
        except OSError:
            pass
        playback = Playback(uuid.uuid4().hex, TtsArtifact(path, selected, voice, duration, fallback),
                            created_at=datetime.now(timezone.utc).isoformat(), rate=rate)
        with self._lock:
            for item in self._playbacks.values():
                if item.state != "stopped":
                    item.state = "stopped"
            self._playbacks[playback.playback_id] = playback
        return playback

    def _get(self, playback_id: str) -> Playback:
        with self._lock:
            playback = self._playbacks.get(playback_id)
        if not playback:
            raise TtsError("tts_playback_not_found")
        return playback

    def control(self, playback_id: str, action: str, rate: float | None = None) -> Playback:
        if action not in {"play", "pause", "stop"} or rate is not None and not MIN_RATE <= rate <= MAX_RATE:
            raise TtsError("tts_invalid_request")
        playback = self._get(playback_id)
        if action == "pause" and playback.state == "playing": playback.state = "paused"
        elif action == "play" and playback.state == "paused": playback.state = "playing"
        elif action == "stop": playback.state = "stopped"
        if rate is not None: playback.rate = rate
        return playback

    def status(self, playback_id: str) -> Playback:
        return self._get(playback_id)

    def audio_path(self, playback_id: str) -> Path:
        playback = self._get(playback_id)
        path = playback.artifact.path.resolve()
        root = (self.config.data_root / "tts-cache").resolve()
        if root not in path.parents or not path.is_file():
            raise TtsError("tts_audio_unavailable")
        return path

    def switch_engine(self, engine: str) -> dict[str, object]:
        if engine not in {"fake", "sapi", "edge-tts"}:
            raise TtsError("tts_invalid_request")
        self._provider(engine)
        self._engine = engine
        return self.capabilities()

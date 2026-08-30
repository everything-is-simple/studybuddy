"""Capture transcription providers."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


from ._core import (
    CaptureProviderError,
    CaptureTranscriptionProvider,
    CaptureTranscriptionRequest,
    CaptureTranscriptionResult,
)


class DeterministicFakeCaptureProvider:
    """Repeatable fake OCR/ASR output, not an accuracy claim."""

    provider_id = "fake"
    model_id = "fake-capture-v1"

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        if request.asset_kind not in {"audio", "image"} or not request.content:
            raise CaptureProviderError("transcription_failed")
        digest = hashlib.sha256(request.content).hexdigest()
        label = "audio" if request.asset_kind == "audio" else "image"
        return CaptureTranscriptionResult(
            language="en",
            segments=[
                {"text": f"Deterministic {label} capture {digest[:12]}", "confidence": 0.94},
                {"text": f"Review marker {digest[12:20]}", "confidence": 0.62},
            ],
        )


class LoopbackCaptureProvider(DeterministicFakeCaptureProvider):
    """Deterministic local loopback profile; it performs no network I/O."""

    provider_id = "loopback"
    model_id = "loopback-capture-v1"


class WhisperCliCaptureProvider:
    """Local, explicit-opt-in adapter for the verified Whisper CLI runtime."""

    provider_id = "whisper-cpp"

    def __init__(self, executable: Path | str, model_path: Path | str, *,
                 model_id: str = "ggml-large-v3-turbo", timeout_seconds: float = 120.0,
                 max_output_bytes: int = 262144) -> None:
        self.executable = Path(executable)
        self.model_path = Path(model_path)
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        if request.asset_kind != "audio" or not request.content:
            raise CaptureProviderError("transcription_failed")
        if not self.executable.is_file() or not self.model_path.is_file():
            raise CaptureProviderError("provider_unavailable")
        if self.timeout_seconds <= 0 or self.max_output_bytes < 1:
            raise CaptureProviderError("transcription_failed")
        temporary_root = Path(tempfile.mkdtemp(prefix="studybuddy-asr-"))
        try:
            input_path = temporary_root / "input.wav"
            input_path.write_bytes(request.content)
            command = [str(self.executable), "-f", str(input_path), "-m", str(self.model_path),
                       "--language", "en", "-otxt", "-osrt", "-nc"]
            try:
                subprocess.run(command, cwd=temporary_root, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=self.timeout_seconds, check=False)
            except subprocess.TimeoutExpired:
                raise CaptureProviderError("provider_timeout") from None
            output_files = [*temporary_root.glob("*.txt"), *temporary_root.glob("*.srt")]
            if sum(path.stat().st_size for path in output_files if path.is_file()) > self.max_output_bytes:
                raise CaptureProviderError("payload_too_large")
            txt_path = temporary_root / "input.txt"
            srt_path = temporary_root / "input.srt"
            text = txt_path.read_text(encoding="utf-8", errors="replace").strip() if txt_path.is_file() else ""
            segments = _parse_srt(srt_path.read_text(encoding="utf-8", errors="replace")) if srt_path.is_file() else []
            if not segments and text:
                segments = [{"text": line.strip(), "confidence": None} for line in text.splitlines() if line.strip()]
            if not segments:
                raise CaptureProviderError("transcript_empty_or_invalid")
            return CaptureTranscriptionResult(segments=segments, language="en")
        except OSError:
            raise CaptureProviderError("provider_unavailable") from None
        finally:
            shutil.rmtree(temporary_root, ignore_errors=True)


def _parse_srt(value: str) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    for block in value.replace("\r\n", "\n").split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = (part.strip() for part in lines[1].split("-->", 1))
        text = " ".join(lines[2:]).strip()
        if text:
            segments.append({"text": text, "start": start, "end": end, "confidence": 0.95})
    return segments


# Short aliases keep the capture surface discoverable for later provider gates.
FakeCaptureProvider = DeterministicFakeCaptureProvider

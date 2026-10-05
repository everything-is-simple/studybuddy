"""TTS skill HTTP boundary. Real engines remain explicitly opt-in."""
from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..tts import TtsError, TtsManager


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    engine: Literal["fake", "sapi", "edge-tts"] | None = None
    voice: str | None = Field(default=None, max_length=200)
    rate: float = Field(default=1.0, ge=0.5, le=2.0)


class ControlRequest(BaseModel):
    playback_id: str = Field(min_length=8, max_length=80)
    action: Literal["play", "pause", "stop"]
    rate: float | None = Field(default=None, ge=0.5, le=2.0)


def _manager(app) -> TtsManager:
    manager = getattr(app.state, "tts_manager", None)
    if manager is None:
        manager = TtsManager(app.state.config)
        app.state.tts_manager = manager
    else:
        manager.update_config(app.state.config)
    return manager


def _error(error: TtsError) -> HTTPException:
    status = 404 if error.code == "tts_playback_not_found" else 400 if error.code == "tts_invalid_request" else 503
    return HTTPException(status_code=status, detail=error.code)


def _public(playback) -> dict[str, object]:
    return {"playback_id": playback.playback_id, "state": playback.state,
            "position_ms": playback.position_ms, "duration_ms": playback.artifact.duration_ms,
            "engine": playback.artifact.engine, "fallback_used": playback.artifact.fallback_used,
            "audio_url": f"/api/tts/audio/{playback.playback_id}"}


def register_routes(app, context):
    @app.get("/api/tts/capabilities")
    def capabilities():
        return _manager(app).capabilities()

    @app.post("/api/tts/speak")
    def speak(request: SpeakRequest):
        try:
            return _public(_manager(app).speak(request.text, engine=request.engine,
                                                voice=request.voice, rate=request.rate))
        except TtsError as error:
            raise _error(error) from None

    @app.post("/api/tts/control")
    def control(request: ControlRequest):
        try:
            return _public(_manager(app).control(request.playback_id, request.action, request.rate))
        except TtsError as error:
            raise _error(error) from None

    @app.get("/api/tts/status/{playback_id}")
    def status(playback_id: str):
        try:
            return _public(_manager(app).status(playback_id))
        except TtsError as error:
            raise _error(error) from None

    @app.get("/api/tts/audio/{playback_id}")
    def audio(playback_id: str):
        try:
            return FileResponse(_manager(app).audio_path(playback_id), media_type="audio/wav",
                                filename="studybuddy-tts.wav")
        except TtsError as error:
            raise _error(error) from None

    return context

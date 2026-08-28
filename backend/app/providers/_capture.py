"""Fake and capture transcription providers."""

from __future__ import annotations

import hashlib

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


# Short aliases keep the capture surface discoverable for later API/provider gates.
FakeCaptureProvider = DeterministicFakeCaptureProvider

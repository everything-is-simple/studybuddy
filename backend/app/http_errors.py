from __future__ import annotations

def _phase9d_http_status(code: str) -> int:
    if code in {
        "capture_not_found", "report_not_found", "transcript_not_found",
    }:
        return 404
    if code in {
        "capture_invalid_state", "transcription_not_ready", "report_invalid_state",
        "delivery_idempotency_mismatch", "transcription_idempotency_mismatch",
        "capture_source_unavailable", "source_deleted", "source_unavailable", "source_stale",
    }:
        return 409
    if code in {"provider_timeout"}:
        return 504
    if code in {"payload_too_large"}:
        return 400
    if code in {"transcription_provider_not_configured"}:
        return 503
    return 400

def _provider_http_status(code: str) -> int:
    if code in {"provider_timeout"}:
        return 504
    if code in {"provider_rate_limited", "provider_quota_exceeded"}:
        return 429
    if code in {"provider_not_configured", "provider_invalid_config"}:
        return 503
    if code in {"provider_connection_failed", "provider_unavailable"}:
        return 503
    return 502

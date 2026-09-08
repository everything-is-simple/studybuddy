"""HTTP 错误码映射 - 将业务错误码映射为 HTTP 状态码。

本模块提供稳定的错误码到 HTTP 状态码映射，供 API 层使用。
映射保证相同错误码总是产生相同状态码（契约稳定性）。

映射原则：
- 404: 资源不存在
- 409: 状态冲突（状态机不允许、幂等键不匹配、源不可用）
- 429: 速率/配额限制
- 400: 请求问题（载荷过大、默认值）
- 503: 服务不可用（未配置、连接失败）
- 504: 上游超时
- 502: 上游异常（提供商默认）

两组映射：
- _phase9d_http_status: 采集/转录/报告（Phase 9D）业务错误
- _provider_http_status: AI 提供商错误
"""
from __future__ import annotations

def _phase9d_http_status(code: str) -> int:
    """将 Phase 9D 业务错误码映射为 HTTP 状态码。
    
    Args:
        code: 业务错误码（如 'capture_not_found'）
    
    Returns:
        HTTP 状态码（默认 400）
    """
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
    """将 AI 提供商错误码映射为 HTTP 状态码。
    
    Args:
        code: 提供商错误码（如 'provider_timeout'）
    
    Returns:
        HTTP 状态码（默认 502，上游异常）
    """
    if code in {"provider_timeout"}:
        return 504
    if code in {"provider_rate_limited", "provider_quota_exceeded"}:
        return 429
    if code in {"provider_not_configured", "provider_invalid_config"}:
        return 503
    if code in {"provider_connection_failed", "provider_unavailable"}:
        return 503
    return 502

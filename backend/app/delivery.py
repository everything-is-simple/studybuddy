"""报告交付 - 出站投递适配器和策略门控。

本模块实现报告的出站交付（SMTP 邮件 / 飞书 Webhook），
是系统中唯一允许出站网络请求的模块，默认关闭、逐次授权。

交付模式（report_delivery_mode）：
- off: 完全禁用（默认）
- dry_run: 干跑，验证序列化但不发网络请求
- live: 正式发送（当前被批准门控拒绝，未开放）

适配器体系：
- DryRunDeliveryAdapter: 干跑（验证 JSON 序列化，不开 socket）
- SmtpDeliveryAdapter: SMTP 邮件（仅限 qq/163 白名单主机）
- FeishuWebhookDeliveryAdapter: 飞书 Webhook（严格 URL 白名单）
- LiveDeliveryAdapter: 正式发送占位（始终拒绝）

安全门控（execute_report_delivery 决策链）：
1. mode=off → blocked (delivery_disabled)
2. 目标不在白名单 → blocked (delivery_target_not_allowed)
3. live 但未启用/未授权 → blocked (delivery_authorization_required)
4. live 门控（9D 始终拒绝）→ blocked (delivery_live_not_approved)
5. dry_run → 适配器执行

幂等与审计：
- 内容指纹: SHA256(content_version + safe_payload_json)
- 重放检测: 相同指纹和幂等键返回上次结果（不重发）
- 审计记录: 仅存内容指纹，绝不存报告正文

错误边界：
- DeliveryAdapterError: 稳定错误码，原始提供商错误不外泄
- 适配器是不可信边界，所有异常收敛为稳定码

配置约束：
- SMTP 主机白名单: smtp.qq.com, smtp.163.com
- 飞书 URL: 必须是 open.feishu.cn 的 bot hook 路径
- 内容上限: 1 MiB
- 超时: 10 秒
"""
from __future__ import annotations

import hashlib
import json
import smtplib
import socket
import sqlite3
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import AppConfig
from .repository import find_report_delivery_replay, record_report_delivery_attempt


DELIVERY_CHANNELS = {"smtp", "feishu"}
DELIVERY_MODES = {"off", "dry_run", "live"}
DELIVERY_TIMEOUT_SECONDS = 10.0
MAX_DELIVERY_CONTENT_BYTES = 1 << 20
FEISHU_WEBHOOK_PREFIX = "/open-apis/bot/v2/hook/"


class DeliveryAdapterError(Exception):
    """交付失败（稳定、安全）- 原始提供商错误绝不跨越此边界。
    
    Args:
        code: 稳定错误码（默认 'delivery_failed'）
    """

    def __init__(self, code: str = "delivery_failed") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class DeliveryContentSummary:
    """交付内容摘要（用于审计，不含正文）。
    
    Attributes:
        content_sha256: 内容 SHA-256 指纹
        content_chars: 字符数
        format: 内容格式（默认 markdown）
    """
    content_sha256: str
    content_chars: int
    format: str = "markdown"

    def public(self) -> dict[str, object]:
        """返回可序列化的公共投影。"""
        return {
            "content_sha256": self.content_sha256,
            "content_chars": self.content_chars,
            "format": self.format,
        }


@dataclass(frozen=True)
class DeliveryOutcome:
    """单次交付结果。
    
    Attributes:
        status: 'sent' / 'dry_run' / 'failed'
        error_code: 失败时的稳定错误码
    """
    status: str
    error_code: str | None = None


class ReportDeliveryAdapter(Protocol):
    channel: str

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                 markdown_content: str) -> DeliveryOutcome:
        ...


class DryRunDeliveryAdapter:
    """干跑适配器 - 构造交付结果但不开 socket、不发送内容。
    
    这是 9D 唯一允许成功执行的路径。
    """

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                 markdown_content: str) -> DeliveryOutcome:
        """验证序列化可行性后返回 dry_run 结果。
        
        Args:
            target_label: 目标标签
            safe_payload: 安全载荷
            markdown_content: Markdown 正文
        
        Returns:
            status='dry_run' 的结果
        
        Raises:
            DeliveryAdapterError: 序列化失败或正文为空时
        """
        # Validate serialization before recording a successful dry-run. This keeps
        # the audit result deterministic while retaining no report body in the DB.
        json.dumps(safe_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if not isinstance(markdown_content, str) or not markdown_content:
            raise DeliveryAdapterError("delivery_failed")
        return DeliveryOutcome(status="dry_run")


class SmtpDeliveryAdapter:
    """运行时配置的 SMTP 适配器 - 正式发送仍受下方门控限制。"""

    channel = "smtp"

    def __init__(self, *, host: str, port: int, username: str, auth_code: str,
                 targets: dict[str, str], secure: bool = True,
                 timeout_seconds: float = DELIVERY_TIMEOUT_SECONDS) -> None:
        """初始化 SMTP 适配器。
        
        Args:
            host: SMTP 主机（白名单: smtp.qq.com / smtp.163.com）
            port: 端口
            username: 发件邮箱
            auth_code: 授权码（非邮箱密码）
            targets: 标签 → 收件人映射
            secure: 是否使用 SSL（默认 True）
            timeout_seconds: 超时秒数
        """
        self.host, self.port, self.username = host.strip(), port, username.strip()
        self.auth_code, self.targets = auth_code, dict(targets)
        self.secure, self.timeout_seconds = secure, timeout_seconds

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                markdown_content: str) -> DeliveryOutcome:
        """发送邮件（验证配置 → 构造消息 → SMTP SSL/TLS 发送）。
        
        Args:
            target_label: 目标标签（必须在 targets 中）
            safe_payload: 安全载荷（未使用，保持接口一致）
            markdown_content: Markdown 正文
        
        Returns:
            status='sent' 的结果
        
        Raises:
            DeliveryAdapterError: 配置无效、内容为空、
                                超限或发送失败时（稳定码，不外泄细节）
        """
        recipient = self.targets.get(target_label)
        if self.host not in {"smtp.qq.com", "smtp.163.com"} or not recipient:
            raise DeliveryAdapterError("delivery_configuration_invalid")
        if not self.username or not self.auth_code or "@" not in self.username or "@" not in recipient:
            raise DeliveryAdapterError("delivery_configuration_invalid")
        if not isinstance(markdown_content, str) or not markdown_content:
            raise DeliveryAdapterError("delivery_failed")
        if len(markdown_content.encode("utf-8")) > MAX_DELIVERY_CONTENT_BYTES:
            raise DeliveryAdapterError("payload_too_large")
        message = EmailMessage()
        message["From"], message["To"] = self.username, recipient
        message["Subject"] = "StudyBuddy report"
        message.set_content(markdown_content)
        try:
            if self.secure:
                client = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout_seconds)
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds)
            with client:
                client.ehlo()
                if not self.secure:
                    client.starttls()
                    client.ehlo()
                client.login(self.username, self.auth_code)
                client.send_message(message)
        except smtplib.SMTPAuthenticationError:
            raise DeliveryAdapterError("delivery_failed") from None
        except (smtplib.SMTPException, OSError, socket.timeout):
            raise DeliveryAdapterError("delivery_failed") from None
        return DeliveryOutcome(status="sent")


class FeishuWebhookDeliveryAdapter:
    """运行时配置的飞书文本 Webhook 适配器（HTTPS）。"""

    channel = "feishu"

    def __init__(self, *, targets: dict[str, str], timeout_seconds: float = DELIVERY_TIMEOUT_SECONDS) -> None:
        """初始化飞书适配器。
        
        Args:
            targets: 标签 → Webhook URL 映射
            timeout_seconds: 超时秒数
        """
        self.targets = dict(targets)
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _allowed_url(url: str) -> bool:
        """验证 Webhook URL（严格白名单：https + open.feishu.cn + bot 路径）。"""
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.netloc == "open.feishu.cn"
            and parsed.path.startswith(FEISHU_WEBHOOK_PREFIX)
            and len(parsed.path.rsplit("/", 1)[-1]) >= 20
            and not parsed.query and not parsed.fragment
        )

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                markdown_content: str) -> DeliveryOutcome:
        """发送飞书文本消息（验证 URL → POST JSON）。
        
        Args:
            target_label: 目标标签（必须在 targets 中）
            safe_payload: 安全载荷（未使用）
            markdown_content: Markdown 正文
        
        Returns:
            status='sent' 的结果
        
        Raises:
            DeliveryAdapterError: URL 不在白名单、内容无效
                                超限或请求失败时
        """
        url = self.targets.get(target_label)
        if not url or not self._allowed_url(url):
            raise DeliveryAdapterError("delivery_configuration_invalid")
        if not isinstance(markdown_content, str) or not markdown_content:
            raise DeliveryAdapterError("delivery_failed")
        body = json.dumps(
            {"msg_type": "text", "content": {"text": markdown_content}},
            ensure_ascii=True, separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > MAX_DELIVERY_CONTENT_BYTES:
            raise DeliveryAdapterError("payload_too_large")
        request = Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json", "Idempotency-Key": target_label},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310: allowlist validated above
                if response.status < 200 or response.status >= 300:
                    raise DeliveryAdapterError("delivery_failed")
                response.read(128)
        except DeliveryAdapterError:
            raise
        except (HTTPError, URLError, OSError, socket.timeout):
            raise DeliveryAdapterError("delivery_failed") from None
        return DeliveryOutcome(status="sent")


class LiveDeliveryAdapter:
    """正式发送占位 - B4-C3 保持正式交付关闭，始终拒绝。"""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                 markdown_content: str) -> DeliveryOutcome:
        """始终拒绝正式发送（门控在适配器选择之前已拦截）。
        
        Raises:
            DeliveryAdapterError: 错误码 delivery_live_not_approved
        """
        raise DeliveryAdapterError("delivery_live_not_approved")


def _target_allowed(config: AppConfig, target_label: str) -> bool:
    """检查目标标签是否在配置的白名单中。"""
    return target_label in set(config.report_delivery_targets)


def _configured_adapter(config: AppConfig, channel: str) -> ReportDeliveryAdapter:
    """从运行时配置构建适配器（仅干跑兼容配置）。
    
    Args:
        config: 应用配置
        channel: 交付渠道（'smtp' 或 'feishu'）
    
    Returns:
        配置好的适配器实例
    
    Raises:
        DeliveryAdapterError: 渠道不允许时
    """
    if channel == "smtp":
        return SmtpDeliveryAdapter(
            host=config.report_delivery_smtp_host,
            port=config.report_delivery_smtp_port,
            username=config.report_delivery_smtp_username or "",
            auth_code=config.report_delivery_smtp_password_runtime or "",
            targets=dict(config.report_delivery_smtp_targets),
            secure=config.report_delivery_smtp_secure,
            timeout_seconds=config.report_delivery_timeout_seconds,
        )
    if channel == "feishu":
        target_label = config.report_delivery_feishu_target_label
        webhook = config.report_delivery_feishu_webhook
        return FeishuWebhookDeliveryAdapter(
            targets={target_label: webhook} if target_label and webhook else {},
            timeout_seconds=config.report_delivery_timeout_seconds,
        )
    raise DeliveryAdapterError("delivery_target_not_allowed")


def _load_report_content(connection: sqlite3.Connection, *, project_id: str,
                         report_id: str) -> tuple[dict[str, object], str, str]:
    """加载报告快照内容（载荷、正文、版本）。
    
    Args:
        connection: 数据库连接
        project_id: 项目 ID
        report_id: 报告 ID
    
    Returns:
        (safe_payload 字典, markdown 正文, content_version)
    
    Raises:
        ValueError: 报告不存在或状态非 ready
        DeliveryAdapterError: 载荷解析失败
    """
    row = connection.execute(
        "SELECT status,content_version,safe_payload_json,markdown_content FROM report_snapshots "
        "WHERE id=? AND project_id=?",
        (report_id, project_id),
    ).fetchone()
    if row is None:
        raise ValueError("report_not_found")
    if row["status"] != "ready":
        raise ValueError("report_invalid_state")
    try:
        payload = json.loads(row["safe_payload_json"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DeliveryAdapterError("delivery_failed") from exc
    if not isinstance(payload, dict):
        raise DeliveryAdapterError("delivery_failed")
    return payload, str(row["markdown_content"]), str(row["content_version"])


def _content_summary(markdown_content: str) -> DeliveryContentSummary:
    """计算内容摘要（SHA-256 指纹 + 字符数，不含正文）。"""
    encoded = markdown_content.encode("utf-8")
    return DeliveryContentSummary(
        content_sha256=hashlib.sha256(encoded).hexdigest(),
        content_chars=len(markdown_content),
    )


def execute_report_delivery(
    connection: sqlite3.Connection,
    *,
    config: AppConfig,
    project_id: str,
    report_id: str,
    channel: str,
    target_label: str,
    mode: str | None = None,
    authorization_granted: bool = False,
    idempotency_key: str | None = None,
    retry_of: str | None = None,
    adapter: ReportDeliveryAdapter | None = None,
) -> dict[str, object]:
    """执行一次显式的、项目范围的报告交付请求。

    9D 中唯一允许成功的执行是本地 dry_run。live 模式会验证
    授权和白名单策略，然后被批准门控拒绝。适配器不会收到
    凭据之外的任何东西，本函数从不隐式重试或后台执行。

    决策链（每个决定都记录为有界审计事实）：
    1. mode=off → blocked (delivery_disabled)
    2. 目标不在白名单 → blocked (delivery_target_not_allowed)
    3. live 未启用/未授权 → blocked (delivery_authorization_required)
    4. live（9D 始终拒绝）→ blocked (delivery_live_not_approved)
    5. dry_run → 适配器执行 → sent/dry_run/failed

    Args:
        connection: 数据库连接
        config: 应用配置
        project_id: 项目 ID
        report_id: 报告 ID
        channel: 交付渠道（'smtp' 或 'feishu'）
        target_label: 目标标签
        mode: 请求模式（必须与配置一致）
        authorization_granted: 本次请求的显式授权标志
        idempotency_key: 幂等键（重放检测）
        retry_of: 重试的原始尝试 ID
        adapter: 注入的适配器（测试用，默认干跑）

    Returns:
        交付尝试结果（含 sent=False 标记和内容摘要）

    Raises:
        ValueError: 渠道/模式/目标标签无效

    注意:
        - 仓库层只存内容指纹，绝不存报告正文
        - 重放检测命中时返回上次结果且 sent=False
    """
    if channel not in DELIVERY_CHANNELS:
        raise ValueError("delivery_target_not_allowed")
    selected_mode = config.report_delivery_mode
    if selected_mode not in DELIVERY_MODES:
        raise ValueError("delivery_failed")
    if mode is not None and mode != selected_mode:
        raise ValueError("delivery_disabled")
    if not isinstance(target_label, str) or not target_label:
        raise ValueError("delivery_target_not_allowed")

    payload, markdown_content, content_version = _load_report_content(
        connection, project_id=project_id, report_id=report_id
    )
    summary = _content_summary(markdown_content)
    safe_payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    content_fingerprint = hashlib.sha256(
        f"{content_version}\x1f{safe_payload_json}".encode("utf-8")
    ).hexdigest()
    replay = find_report_delivery_replay(
        connection, project_id=project_id, report_id=report_id, channel=channel,
        mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
        content_fingerprint=content_fingerprint,
    )
    if replay is not None:
        replay["sent"] = False
        replay["content_summary"] = summary.public()
        return replay
    allowed = _target_allowed(config, target_label)

    # Every policy decision is recorded as a bounded audit fact. The repository
    # stores only a content fingerprint, never the report payload or markdown.
    if selected_mode == "off":
        result = record_report_delivery_attempt(
            connection, project_id=project_id, report_id=report_id, channel=channel,
            mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
            retry_of=retry_of, status_override="blocked", error_code_override="delivery_disabled",
        )
    elif not allowed:
        result = record_report_delivery_attempt(
            connection, project_id=project_id, report_id=report_id, channel=channel,
            mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
            retry_of=retry_of, status_override="blocked", error_code_override="delivery_target_not_allowed",
        )
    elif selected_mode == "live" and (
        not config.report_delivery_enabled
        or not config.report_delivery_authorized
        or not authorization_granted
    ):
        result = record_report_delivery_attempt(
            connection, project_id=project_id, report_id=report_id, channel=channel,
            mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
            retry_of=retry_of, status_override="blocked", error_code_override="delivery_authorization_required",
        )
    elif selected_mode == "live":
        # This gate runs before adapter selection. A live sender cannot be
        # reached in 9D, even when a test or runtime injects one.
        result = record_report_delivery_attempt(
            connection, project_id=project_id, report_id=report_id, channel=channel,
            mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
            retry_of=retry_of, status_override="blocked", error_code_override="delivery_live_not_approved",
        )
    else:
        selected_adapter = adapter or DryRunDeliveryAdapter(channel)
        try:
            outcome = selected_adapter.deliver(
                target_label=target_label, safe_payload=payload, markdown_content=markdown_content
            )
        except DeliveryAdapterError as exc:
            result = record_report_delivery_attempt(
                connection, project_id=project_id, report_id=report_id, channel=channel,
                mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
                retry_of=retry_of, status_override="failed", error_code_override=exc.code,
            )
        except Exception:
            # Adapters are an untrusted boundary: preserve only the stable code.
            result = record_report_delivery_attempt(
                connection, project_id=project_id, report_id=report_id, channel=channel,
                mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
                retry_of=retry_of, status_override="failed", error_code_override="delivery_failed",
            )
        else:
            result = record_report_delivery_attempt(
                connection, project_id=project_id, report_id=report_id, channel=channel,
                mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
                retry_of=retry_of, status_override=outcome.status,
                error_code_override=outcome.error_code,
            )

    result["sent"] = False
    result["content_summary"] = summary.public()
    return result

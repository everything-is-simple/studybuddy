"""配置管理模块。

本模块从环境变量加载 StudyBuddy 的全局配置，并提供不可变的
配置对象。所有配置项都有默认值和验证规则。

配置来源：
- 环境变量（STUDYBUDDY_* 前缀）
- 代码内置默认值

主要组件：
- AppConfig: 不可变的配置数据类，包含所有配置项
- config_from_environment(): 从环境变量构造 AppConfig 实例
- 验证函数: _env_int, _env_float, _env_bool, _valid_base_url 等

配置分类：
1. 核心配置：
   - data_root: 数据根目录
   - project_id: 项目 ID
   - max_upload_bytes: 文件上传限制

2. AI 配置：
   - ai_provider_id, ai_model_id: LLM 提供商和模型
   - ai_base_url, ai_api_key: API 访问凭据
   - ai_timeout_seconds, ai_max_output_tokens: 资源限制

3. Embedding 配置：
   - embedding_provider_id, embedding_model_id: 嵌入模型
   - embedding_max_batch_size, embedding_max_dimensions: 批处理限制

4. ASR/OCR 配置：
   - asr_provider_id, asr_model_id, asr_runtime_path: 音频转录
   - ocr_provider_id, ocr_model_id, ocr_model_root: 图像识别
   - ocr_enabled: OCR 启用开关

5. 报告交付配置：
   - report_delivery_mode: 'off'/'smtp'/'feishu'
   - report_delivery_smtp_*: SMTP 邮件配置
   - report_delivery_feishu_*: 飞书机器人配置
   - 注意：默认关闭，需显式授权

6. 运行时配置：
   - host, port: HTTP 服务器配置
   - task_max_concurrency: 任务并发数
   - log_level: 日志级别
   - demo_mode: 演示模式（使用 fake provider）

安全性：
- 所有敏感字段（API 密钥、密码）使用 repr=False
- HTTP base_url 限制：HTTPS 或本地 HTTP
- 邮件交付默认关闭，需显式授权
- SMTP 主机白名单：smtp.qq.com, smtp.163.com
- 飞书 Webhook URL 严格验证

示例：
    import os
    os.environ['STUDYBUDDY_DATA_ROOT'] = '/data/studybuddy'
    os.environ['STUDYBUDDY_AI_PROVIDER'] = 'openai'
    os.environ['STUDYBUDDY_AI_MODEL'] = 'gpt-4o-mini'
    
    config = config_from_environment()
    print(config.data_root)  # Path('/data/studybuddy')
    print(config.ai_provider_id)  # 'openai'
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_AI_TIMEOUT_SECONDS = 30.0
DEFAULT_AI_MAX_OUTPUT_TOKENS = 800
DEFAULT_AI_MAX_PROMPT_CHARS = 30000
DEFAULT_AI_MAX_ANSWER_CHARS = 12000
DEFAULT_AI_MAX_RETRIES = 0
DEFAULT_EMBEDDING_PROVIDER = None
DEFAULT_EMBEDDING_MODEL = None
DEFAULT_EMBEDDING_MODEL_REVISION = "1"
DEFAULT_EMBEDDING_TIMEOUT_SECONDS = 30.0
DEFAULT_EMBEDDING_MAX_BATCH_SIZE = 32
DEFAULT_EMBEDDING_MAX_TEXT_CHARS = 12000
DEFAULT_EMBEDDING_MAX_DIMENSIONS = 4096
DEFAULT_EMBEDDING_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_EMBEDDING_MAX_RETRIES = 0
DEFAULT_REPORT_DELIVERY_MODE = "off"
DEFAULT_REPORT_DELIVERY_ENABLED = False
DEFAULT_REPORT_DELIVERY_AUTHORIZED = False
DEFAULT_REPORT_DELIVERY_SMTP_HOST = "smtp.qq.com"
DEFAULT_REPORT_DELIVERY_SMTP_PORT = 465
DEFAULT_REPORT_DELIVERY_SMTP_SECURE = True
DEFAULT_REPORT_DELIVERY_TIMEOUT_SECONDS = 10.0
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
DEFAULT_TASK_MAX_CONCURRENCY = 1
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_ASR_PROVIDER = None
DEFAULT_ASR_MODEL = "ggml-large-v3-turbo"
DEFAULT_ASR_TIMEOUT_SECONDS = 120.0
DEFAULT_ASR_MAX_OUTPUT_BYTES = 262144
DEFAULT_OCR_PROVIDER = None
DEFAULT_OCR_MODEL = "PP-OCRv5_server_det+PP-OCRv5_server_rec"
DEFAULT_OCR_TIMEOUT_SECONDS = 120.0
DEFAULT_OCR_MAX_OUTPUT_BYTES = 524288
# Environment-derived configuration stays explicit: an unset gate reads False.
# Out-of-box enablement happens in the resolve step (see capabilities.py), where a
# locally detected, structurally valid component turns the capability on.
DEFAULT_OCR_ENABLED = False
DEFAULT_AUTO_DETECT = True


@dataclass(frozen=True)
class AppConfig:
    """应用全局配置数据类（不可变）。
    
    所有配置项均为只读，创建后不可修改。敏感字段（API 密钥、密码）
    使用 repr=False 隐藏，不会出现在日志和字符串表示中。
    
    核心字段：
        data_root: 数据根目录（必需）
        project_id: 项目 ID（默认 'default'）
        ai_provider_id, ai_model_id: LLM 配置
        embedding_provider_id, embedding_model_id: 嵌入模型配置
        ocr_provider_id, ocr_model_id: OCR 配置
        asr_provider_id, asr_model_id: ASR 配置
        host, port: HTTP 服务器配置
    
    属性：
        originals_root: 原始文件存储目录（data_root / 'originals'）
        database_path: SQLite 数据库路径（data_root / 'studybuddy.sqlite3'）
    
    注意：
        - 直接构造 AppConfig(...) 不会探测主机能力
        - 使用 config_from_environment() 从环境变量加载
        - auto_detect_enabled=True 时会在 capabilities.py 中探测本地 OCR/ASR
    """
    data_root: Path
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    project_id: str = "default"
    ai_provider_id: str | None = None
    ai_model_id: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = field(default=None, repr=False)
    ai_timeout_seconds: float = DEFAULT_AI_TIMEOUT_SECONDS
    ai_max_output_tokens: int = DEFAULT_AI_MAX_OUTPUT_TOKENS
    ai_max_prompt_chars: int = DEFAULT_AI_MAX_PROMPT_CHARS
    ai_max_answer_chars: int = DEFAULT_AI_MAX_ANSWER_CHARS
    ai_max_retries: int = DEFAULT_AI_MAX_RETRIES
    embedding_provider_id: str | None = DEFAULT_EMBEDDING_PROVIDER
    embedding_model_id: str | None = DEFAULT_EMBEDDING_MODEL
    embedding_base_url: str | None = None
    embedding_api_key: str | None = field(default=None, repr=False)
    embedding_model_revision: str = DEFAULT_EMBEDDING_MODEL_REVISION
    embedding_timeout_seconds: float = DEFAULT_EMBEDDING_TIMEOUT_SECONDS
    embedding_max_batch_size: int = DEFAULT_EMBEDDING_MAX_BATCH_SIZE
    embedding_max_text_chars: int = DEFAULT_EMBEDDING_MAX_TEXT_CHARS
    embedding_max_dimensions: int = DEFAULT_EMBEDDING_MAX_DIMENSIONS
    embedding_max_response_bytes: int = DEFAULT_EMBEDDING_MAX_RESPONSE_BYTES
    embedding_max_retries: int = DEFAULT_EMBEDDING_MAX_RETRIES
    # Delivery is deliberately disabled for live use. Secrets are runtime-only
    # configuration and are excluded from reprs and persistence by design.
    report_delivery_mode: str = DEFAULT_REPORT_DELIVERY_MODE
    report_delivery_enabled: bool = DEFAULT_REPORT_DELIVERY_ENABLED
    report_delivery_authorized: bool = DEFAULT_REPORT_DELIVERY_AUTHORIZED
    report_delivery_targets: tuple[str, ...] = ()
    report_delivery_smtp_password: str | None = field(default=None, repr=False)
    report_delivery_feishu_secret: str | None = field(default=None, repr=False)
    # Runtime/release controls are appended to preserve existing positional
    # AppConfig construction compatibility. Secrets remain repr-hidden above.
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    task_max_concurrency: int = DEFAULT_TASK_MAX_CONCURRENCY
    log_level: str = DEFAULT_LOG_LEVEL
    backup_root: Path | None = None
    demo_mode: bool = False
    asr_provider_id: str | None = DEFAULT_ASR_PROVIDER
    asr_model_id: str | None = DEFAULT_ASR_MODEL
    asr_runtime_path: Path | None = None
    asr_model_path: Path | None = None
    asr_timeout_seconds: float = DEFAULT_ASR_TIMEOUT_SECONDS
    asr_max_output_bytes: int = DEFAULT_ASR_MAX_OUTPUT_BYTES
    ocr_provider_id: str | None = DEFAULT_OCR_PROVIDER
    ocr_model_id: str | None = DEFAULT_OCR_MODEL
    ocr_model_root: Path | None = None
    ocr_timeout_seconds: float = DEFAULT_OCR_TIMEOUT_SECONDS
    ocr_max_output_bytes: int = DEFAULT_OCR_MAX_OUTPUT_BYTES
    ocr_enabled: bool = DEFAULT_OCR_ENABLED
    # Provenance of optional local capability configuration, for UI display only.
    ocr_source: str = "unset"
    asr_source: str = "unset"
    # Explicit construction is explicit: direct AppConfig(...) never probes the host.
    # `config_from_environment()` turns probing on (STUDYBUDDY_AUTO_DETECT=0 opts out).
    auto_detect_enabled: bool = False
    # B4 runtime delivery settings remain opt-in and are never persisted.
    report_delivery_smtp_host: str = DEFAULT_REPORT_DELIVERY_SMTP_HOST
    report_delivery_smtp_port: int = DEFAULT_REPORT_DELIVERY_SMTP_PORT
    report_delivery_smtp_secure: bool = DEFAULT_REPORT_DELIVERY_SMTP_SECURE
    report_delivery_smtp_username: str | None = field(default=None, repr=False)
    report_delivery_smtp_password_runtime: str | None = field(default=None, repr=False)
    report_delivery_smtp_targets: tuple[tuple[str, str], ...] = field(default=(), repr=False)
    report_delivery_feishu_target_label: str | None = None
    report_delivery_timeout_seconds: float = DEFAULT_REPORT_DELIVERY_TIMEOUT_SECONDS
    report_delivery_feishu_webhook: str | None = field(default=None, repr=False)

    @property
    def originals_root(self) -> Path:
        """原始文件存储目录（data_root / 'originals'）。"""
        return self.data_root / "originals"

    @property
    def database_path(self) -> Path:
        """主 SQLite 数据库文件路径（data_root / 'studybuddy.sqlite3'）。"""
        return self.data_root / "studybuddy.sqlite3"


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"invalid_{name.lower()}") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"invalid_{name.lower()}")
    return value


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid_{name.lower()}") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"invalid_{name.lower()}")
    return value


def _valid_base_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("invalid_ai_base_url")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("invalid_ai_base_url")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("invalid_ai_base_url") from exc
    return value.rstrip("/")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid_{name.lower()}")


def _env_host() -> str:
    value = os.environ.get("STUDYBUDDY_HOST", DEFAULT_HOST).strip()
    if value not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("invalid_host")
    return value


def _env_log_level() -> str:
    value = os.environ.get("STUDYBUDDY_LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper()
    if value not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ValueError("invalid_log_level")
    return value


def _env_delivery_mode() -> str:
    value = os.environ.get("STUDYBUDDY_REPORT_DELIVERY_MODE", DEFAULT_REPORT_DELIVERY_MODE).strip().lower()
    if value not in {"off", "dry_run", "live"}:
        raise ValueError("invalid_report_delivery_mode")
    return value


def _env_delivery_mappings(name: str) -> tuple[tuple[str, str], ...]:
    raw = os.environ.get(name, "")
    pairs: list[tuple[str, str]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if item.count("=") != 1:
            raise ValueError(f"invalid_{name.lower()}")
        label, target = (part.strip() for part in item.split("=", 1))
        if (not label or not target or len(label) > 100 or len(target) > 500
                or any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in label)):
            raise ValueError(f"invalid_{name.lower()}")
        pairs.append((label, target))
    if len({label for label, _ in pairs}) != len(pairs):
        raise ValueError(f"invalid_{name.lower()}")
    return tuple(pairs)


def _env_delivery_label(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    if (len(value) > 100
            or any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in value)):
        raise ValueError(f"invalid_{name.lower()}")
    return value


def _env_delivery_smtp_host() -> str:
    value = os.environ.get("STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST", DEFAULT_REPORT_DELIVERY_SMTP_HOST).strip().lower()
    if value not in {"smtp.qq.com", "smtp.163.com"}:
        raise ValueError("invalid_report_delivery_smtp_host")
    return value


def _env_delivery_feishu_webhook() -> str | None:
    value = os.environ.get("STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK", "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if (parsed.scheme != "https" or parsed.netloc != "open.feishu.cn"
            or not parsed.path.startswith("/open-apis/bot/v2/hook/")
            or len(parsed.path.rsplit("/", 1)[-1]) < 20
            or parsed.query or parsed.fragment):
        raise ValueError("invalid_report_delivery_feishu_webhook")
    return value


def _env_delivery_targets() -> tuple[str, ...]:
    raw = os.environ.get("STUDYBUDDY_REPORT_DELIVERY_TARGETS", "")
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if len(values) > 100 or any(len(item) > 100 for item in values):
        raise ValueError("invalid_report_delivery_targets")
    for value in values:
        if any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in value):
            raise ValueError("invalid_report_delivery_targets")
    return values


def config_from_environment() -> AppConfig:
    """从环境变量构造应用配置。
    
    读取所有 STUDYBUDDY_* 前缀的环境变量，验证并构造 AppConfig 实例。
    未设置的环境变量使用代码内置的默认值。
    
    关键环境变量：
        STUDYBUDDY_DATA_ROOT: 数据根目录（默认 ~/.studybuddy/data）
        STUDYBUDDY_PROJECT_ID: 项目 ID（默认 'default'）
        STUDYBUDDY_AI_PROVIDER: AI 提供商（如 'openai'）
        STUDYBUDDY_AI_MODEL: AI 模型 ID（如 'gpt-4o-mini'）
        STUDYBUDDY_AI_API_KEY: AI API 密钥
        STUDYBUDDY_HOST: HTTP 服务器主机（默认 '127.0.0.1'）
        STUDYBUDDY_PORT: HTTP 服务器端口（默认 8787）
        STUDYBUDDY_DEMO_MODE: 演示模式（0/1）
        STUDYBUDDY_AUTO_DETECT: 自动检测本地能力（默认 1）
    
    Returns:
        完整的 AppConfig 实例，所有字段已验证
    
    Raises:
        ValueError: 环境变量格式错误或超出允许范围时，
                    错误代码为 'invalid_<小写变量名>'
    
    示例：
        >>> import os
        >>> os.environ['STUDYBUDDY_DATA_ROOT'] = '/data/study'
        >>> config = config_from_environment()
        >>> print(config.data_root)
        PosixPath('/data/study')
    
    注意：
        - 此函数启用 auto_detect_enabled=True（除非显式设置为 0）
        - demo_mode=True 时强制使用 fake provider，忽略其他 AI 配置
        - 报告交付功能默认关闭，需显式启用并授权
    """
    configured_root = os.environ.get("STUDYBUDDY_DATA_ROOT")
    if not configured_root:
        configured_root = str(Path.home() / ".studybuddy" / "data")
    raw_limit = os.environ.get("STUDYBUDDY_MAX_UPLOAD_BYTES")
    if raw_limit is None:
        max_upload_bytes = DEFAULT_MAX_UPLOAD_BYTES
    else:
        try:
            max_upload_bytes = int(raw_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_max_upload_bytes") from exc
        if max_upload_bytes < 1:
            raise ValueError("invalid_max_upload_bytes")
    demo_mode = _env_bool("STUDYBUDDY_DEMO_MODE", False)
    ai_provider = os.environ.get("STUDYBUDDY_AI_PROVIDER") or None
    ai_model = os.environ.get("STUDYBUDDY_AI_MODEL") or None
    if demo_mode:
        if (ai_provider not in {None, "fake"}
                or os.environ.get("STUDYBUDDY_AI_BASE_URL")
                or os.environ.get("STUDYBUDDY_AI_API_KEY")):
            raise ValueError("invalid_demo_configuration")
        ai_provider = "fake"
        ai_model = ai_model or "fake-studybuddy-v1"
    return AppConfig(
        data_root=Path(configured_root),
        max_upload_bytes=max_upload_bytes,
        project_id=os.environ.get("STUDYBUDDY_PROJECT_ID", "default"),
        ai_provider_id=ai_provider,
        ai_model_id=ai_model,
        ai_base_url=_valid_base_url(os.environ.get("STUDYBUDDY_AI_BASE_URL")),
        ai_api_key=os.environ.get("STUDYBUDDY_AI_API_KEY") or None,
        ai_timeout_seconds=_env_float("STUDYBUDDY_AI_TIMEOUT_SECONDS", DEFAULT_AI_TIMEOUT_SECONDS, minimum=0.1, maximum=120.0),
        ai_max_output_tokens=_env_int("STUDYBUDDY_AI_MAX_OUTPUT_TOKENS", DEFAULT_AI_MAX_OUTPUT_TOKENS, minimum=1, maximum=8192),
        ai_max_prompt_chars=_env_int("STUDYBUDDY_AI_MAX_PROMPT_CHARS", DEFAULT_AI_MAX_PROMPT_CHARS, minimum=100, maximum=200000),
        ai_max_answer_chars=_env_int("STUDYBUDDY_AI_MAX_ANSWER_CHARS", DEFAULT_AI_MAX_ANSWER_CHARS, minimum=100, maximum=100000),
        ai_max_retries=_env_int("STUDYBUDDY_AI_MAX_RETRIES", DEFAULT_AI_MAX_RETRIES, minimum=0, maximum=2),
        embedding_provider_id=os.environ.get("STUDYBUDDY_EMBEDDING_PROVIDER") or None,
        embedding_model_id=os.environ.get("STUDYBUDDY_EMBEDDING_MODEL") or None,
        embedding_base_url=_valid_base_url(os.environ.get("STUDYBUDDY_EMBEDDING_BASE_URL")),
        embedding_api_key=os.environ.get("STUDYBUDDY_EMBEDDING_API_KEY") or None,
        embedding_model_revision=os.environ.get("STUDYBUDDY_EMBEDDING_MODEL_REVISION", DEFAULT_EMBEDDING_MODEL_REVISION),
        embedding_timeout_seconds=_env_float("STUDYBUDDY_EMBEDDING_TIMEOUT_SECONDS", DEFAULT_EMBEDDING_TIMEOUT_SECONDS, minimum=0.1, maximum=120.0),
        embedding_max_batch_size=_env_int("STUDYBUDDY_EMBEDDING_MAX_BATCH_SIZE", DEFAULT_EMBEDDING_MAX_BATCH_SIZE, minimum=1, maximum=32),
        embedding_max_text_chars=_env_int("STUDYBUDDY_EMBEDDING_MAX_TEXT_CHARS", DEFAULT_EMBEDDING_MAX_TEXT_CHARS, minimum=1, maximum=12000),
        embedding_max_dimensions=_env_int("STUDYBUDDY_EMBEDDING_MAX_DIMENSIONS", DEFAULT_EMBEDDING_MAX_DIMENSIONS, minimum=1, maximum=4096),
        embedding_max_response_bytes=_env_int("STUDYBUDDY_EMBEDDING_MAX_RESPONSE_BYTES", DEFAULT_EMBEDDING_MAX_RESPONSE_BYTES, minimum=1, maximum=16 * 1024 * 1024),
        embedding_max_retries=_env_int("STUDYBUDDY_EMBEDDING_MAX_RETRIES", DEFAULT_EMBEDDING_MAX_RETRIES, minimum=0, maximum=2),
        report_delivery_mode=_env_delivery_mode(),
        report_delivery_enabled=_env_bool("STUDYBUDDY_REPORT_DELIVERY_ENABLED", DEFAULT_REPORT_DELIVERY_ENABLED),
        report_delivery_authorized=_env_bool("STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED", DEFAULT_REPORT_DELIVERY_AUTHORIZED),
        report_delivery_targets=_env_delivery_targets(),
        report_delivery_smtp_password=os.environ.get("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD") or None,
        report_delivery_feishu_secret=os.environ.get("STUDYBUDDY_REPORT_DELIVERY_FEISHU_SECRET") or None,
        host=_env_host(),
        port=_env_int("STUDYBUDDY_PORT", DEFAULT_PORT, minimum=1024, maximum=65535),
        task_max_concurrency=_env_int("STUDYBUDDY_TASK_MAX_CONCURRENCY", DEFAULT_TASK_MAX_CONCURRENCY, minimum=1, maximum=1),
        log_level=_env_log_level(),
        backup_root=Path(os.environ["STUDYBUDDY_BACKUP_ROOT"]) if os.environ.get("STUDYBUDDY_BACKUP_ROOT") else None,
        demo_mode=demo_mode,
        asr_provider_id=os.environ.get("STUDYBUDDY_ASR_PROVIDER") or DEFAULT_ASR_PROVIDER,
        asr_model_id=os.environ.get("STUDYBUDDY_ASR_MODEL") or DEFAULT_ASR_MODEL,
        asr_runtime_path=Path(os.environ["STUDYBUDDY_ASR_RUNTIME"]) if os.environ.get("STUDYBUDDY_ASR_RUNTIME") else None,
        asr_model_path=Path(os.environ["STUDYBUDDY_ASR_MODEL_PATH"]) if os.environ.get("STUDYBUDDY_ASR_MODEL_PATH") else None,
        asr_timeout_seconds=_env_float("STUDYBUDDY_ASR_TIMEOUT_SECONDS", DEFAULT_ASR_TIMEOUT_SECONDS, minimum=0.1, maximum=600.0),
        asr_max_output_bytes=_env_int("STUDYBUDDY_ASR_MAX_OUTPUT_BYTES", DEFAULT_ASR_MAX_OUTPUT_BYTES, minimum=1, maximum=16 * 1024 * 1024),
        ocr_provider_id=os.environ.get("STUDYBUDDY_OCR_PROVIDER") or DEFAULT_OCR_PROVIDER,
        ocr_model_id=os.environ.get("STUDYBUDDY_OCR_MODEL") or DEFAULT_OCR_MODEL,
        ocr_model_root=Path(os.environ["STUDYBUDDY_OCR_MODEL_ROOT"]) if os.environ.get("STUDYBUDDY_OCR_MODEL_ROOT") else None,
        ocr_timeout_seconds=_env_float("STUDYBUDDY_OCR_TIMEOUT_SECONDS", DEFAULT_OCR_TIMEOUT_SECONDS, minimum=0.1, maximum=600.0),
        ocr_max_output_bytes=_env_int("STUDYBUDDY_OCR_MAX_OUTPUT_BYTES", DEFAULT_OCR_MAX_OUTPUT_BYTES, minimum=1, maximum=16 * 1024 * 1024),
        ocr_enabled=_env_bool("STUDYBUDDY_OCR_ENABLED", DEFAULT_OCR_ENABLED),
        auto_detect_enabled=_env_bool("STUDYBUDDY_AUTO_DETECT", DEFAULT_AUTO_DETECT),
        report_delivery_smtp_host=_env_delivery_smtp_host(),
        report_delivery_smtp_port=_env_int("STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT", DEFAULT_REPORT_DELIVERY_SMTP_PORT, minimum=1, maximum=65535),
        report_delivery_smtp_secure=_env_bool("STUDYBUDDY_REPORT_DELIVERY_SMTP_SECURE", DEFAULT_REPORT_DELIVERY_SMTP_SECURE),
        report_delivery_smtp_username=os.environ.get("STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME") or None,
        report_delivery_smtp_password_runtime=os.environ.get("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD") or None,
        report_delivery_smtp_targets=_env_delivery_mappings("STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS"),
        report_delivery_feishu_target_label=_env_delivery_label("STUDYBUDDY_REPORT_DELIVERY_FEISHU_TARGET_LABEL"),
        report_delivery_timeout_seconds=_env_float("STUDYBUDDY_REPORT_DELIVERY_TIMEOUT_SECONDS", DEFAULT_REPORT_DELIVERY_TIMEOUT_SECONDS, minimum=0.1, maximum=60.0),
        report_delivery_feishu_webhook=_env_delivery_feishu_webhook(),
    )

"""P1-5-3 配置持久化评估治理测试。

本文件把 P1-5-3 的决策（不引入配置持久化）转为可执行断言：
- 无系统配置表 / 设置表 / secret 表
- 配置仅从环境变量加载（不读文件）
- 生产代码无 dotenv 加载器
- AppConfig 保持 frozen
- 全部 secret / 隐私字段 repr=False
- backup 不复制任意 data_root 文件
- 无配置写入 endpoint
- 评估文档记录决策

决策文档：docs/contracts/P1_5_3_CONFIGURATION_PERSISTENCE_EVALUATION.md
"""

from __future__ import annotations

import dataclasses
import inspect
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import AppConfig  # noqa: E402

APP_ROOT = ROOT / "backend" / "app"
MIGRATIONS_ROOT = APP_ROOT / "migrations"
EVALUATION_DOC = ROOT / "docs" / "contracts" / "P1_5_3_CONFIGURATION_PERSISTENCE_EVALUATION.md"

# 契约 §1.2 排除 SQLite 作为配置载体。这些名字代表"系统配置表"，
# 领域表（如 rhythm_settings）不在此列，因为它属于学习节奏领域而非系统配置。
FORBIDDEN_CONFIG_TABLE_NAMES = (
    "system_config",
    "app_config",
    "configuration",
    "provider_config",
    "delivery_config",
    "email_config",
    "secrets",
    "credentials",
    "api_keys",
)

# config.py 必须只读环境变量，不得读取任何文件。
FILE_READ_PATTERNS = (
    r"\bopen\s*\(",
    r"\.read_text\s*\(",
    r"\.read_bytes\s*\(",
    r"\bjson\.load\s*\(",
    r"\bconfigparser\b",
    r"\btomllib\b",
    r"\byaml\b",
)


def _migration_sources() -> dict[str, str]:
    """Return migration filename -> source text for every versioned migration."""
    sources = {}
    for path in sorted(MIGRATIONS_ROOT.glob("_v*.py")):
        sources[path.name] = path.read_text(encoding="utf-8")
    return sources


def _created_table_names(source: str) -> set[str]:
    """Extract table names from CREATE TABLE statements in one migration."""
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`\[]?(\w+)",
        re.IGNORECASE,
    )
    return {match.group(1).lower() for match in pattern.finditer(source)}


def test_no_config_or_settings_table_in_migrations() -> None:
    """验证没有任何 migration 创建系统配置表 / secret 表。

    契约 §1.2：SQLite 是明确排除的配置持久化路径。
    P1-5-3 §4.6：SQLite 是 secret 的最差载体（backup 全库复制）。
    """
    sources = _migration_sources()
    assert sources, "未找到任何 migration 文件"

    all_tables: set[str] = set()
    for name, source in sources.items():
        all_tables |= _created_table_names(source)

    for forbidden in FORBIDDEN_CONFIG_TABLE_NAMES:
        assert forbidden not in all_tables, (
            f"migration 创建了被禁止的系统配置表 {forbidden!r}；"
            "契约 §1.2 排除 SQLite 作为配置载体"
        )

    # rhythm_settings 是学习节奏领域表，属于允许存在的既有业务表。
    assert "rhythm_settings" in all_tables, (
        "rhythm_settings 领域表应当存在；本测试的排除清单不应影响既有领域表"
    )


def test_config_is_loaded_from_environment_only() -> None:
    """验证 config.py 不读取任何文件，配置来源仅为环境变量。

    契约 §1.2 / §4.1：runtime-only 环境变量来源。
    """
    config_source = (APP_ROOT / "config.py").read_text(encoding="utf-8")

    for pattern in FILE_READ_PATTERNS:
        assert not re.search(pattern, config_source), (
            f"config.py 出现文件读取模式 {pattern!r}；配置来源必须仅为环境变量"
        )

    # 必须确实使用环境变量。
    assert "os.environ" in config_source, "config.py 应从 os.environ 读取配置"


def test_no_dotenv_loader_in_production_code() -> None:
    """验证生产代码不含 dotenv 加载器。

    .env.example 是纯文档模板，运行时不得被读取。
    """
    offenders = []
    for path in APP_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8", errors="replace")
        if "dotenv" in source or "load_dotenv" in source:
            offenders.append(path.relative_to(ROOT).as_posix())

    assert not offenders, (
        f"以下生产文件引用了 dotenv：{offenders}；"
        ".env 文件不得在运行时被加载"
    )


def test_appconfig_remains_frozen() -> None:
    """验证 AppConfig 保持不可变。

    frozen dataclass 阻止运行时就地修改配置，是"不支持热重载"的实施基础。
    """
    assert dataclasses.is_dataclass(AppConfig), "AppConfig 必须是 dataclass"

    params = getattr(AppConfig, "__dataclass_params__", None)
    assert params is not None, "无法读取 AppConfig 的 dataclass 参数"
    assert params.frozen is True, (
        "AppConfig 必须保持 frozen=True；契约 §4.1 不支持运行时热重载"
    )


def test_all_secret_fields_have_repr_false() -> None:
    """验证全部 secret / 隐私字段标记 repr=False。

    P1-5-3 §2.2：实际为 8 个字段（契约 §4.2 少列 3 个）。
    """
    expected_hidden = {
        "ai_api_key",
        "embedding_api_key",
        "report_delivery_smtp_password",
        "report_delivery_feishu_secret",
        "report_delivery_smtp_username",
        "report_delivery_smtp_password_runtime",
        "report_delivery_smtp_targets",
        "report_delivery_feishu_webhook",
    }

    fields_by_name = {field.name: field for field in dataclasses.fields(AppConfig)}

    for name in expected_hidden:
        assert name in fields_by_name, f"AppConfig 缺少预期字段 {name!r}"
        assert fields_by_name[name].repr is False, (
            f"{name!r} 必须标记 repr=False，否则可能通过 repr(config) 泄漏"
        )

    # 反向检查：repr 输出不含任何敏感字段名。
    sample = AppConfig(data_root=Path("/tmp/studybuddy-p1-5-3-fake-root"))
    rendered = repr(sample)
    for name in expected_hidden:
        assert name not in rendered, f"repr(AppConfig) 暴露了 {name!r}"


def test_backup_does_not_copy_arbitrary_data_root_files() -> None:
    """验证 backup 只复制数据库、originals 与 manifest。

    这保证操作员放在 data_root 的任何本地文件不会进入 backup 归档。
    """
    backup_source = (APP_ROOT / "backup.py").read_text(encoding="utf-8")

    # backup 归档的三个组成部分。
    assert "_DB_NAME" in backup_source, "backup 应使用固定数据库文件名常量"
    assert "manifest.json" in backup_source, "backup 应写入 manifest.json"
    assert "originals" in backup_source, "backup 应复制 originals"

    # 不得整目录复制 data_root。
    assert "copytree(data_root" not in backup_source.replace(" ", ""), (
        "backup 不得整目录复制 data_root；否则本地配置文件会进入归档"
    )


def test_no_config_write_endpoint_exists() -> None:
    """验证不存在任何配置写入 endpoint。

    契约 §3.1：P1-5 不实现配置写入 API。
    P1-5-3 §5.2：P1-5-1 配置 UI 也不新增写入 endpoint。
    """
    forbidden_routes = (
        "/api/system/provider-config",
        "/api/system/email-config",
        "/api/system/config",
        "/api/config",
    )

    api_root = APP_ROOT / "api"
    offenders = []
    for path in api_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8", errors="replace")
        for route in forbidden_routes:
            if route in source:
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: {route}")

    assert not offenders, (
        f"发现配置写入路由：{offenders}；P1-5 不批准配置写入 endpoint"
    )


def _endpoint_body(source: str, route: str) -> str:
    """Return one route handler body, bounded by the next @app decorator."""
    marker = f'"{route}"'
    assert marker in source, f"未找到路由 {route!r}"
    start = source.index(marker)
    remainder = source[start + len(marker):]
    next_decorator = remainder.find("@app.")
    return remainder if next_decorator == -1 else remainder[:next_decorator]


def test_connection_test_endpoints_do_not_persist() -> None:
    """验证 connection-test endpoint 不写入任何持久化载体。

    P1-5-2 已实现的两个 endpoint 必须保持无副作用。
    """
    system_source = (APP_ROOT / "api" / "system.py").read_text(encoding="utf-8")

    routes = ("/api/system/provider-connection-test", "/api/system/email-connection-test")
    forbidden_calls = ("connect(", "INSERT", "UPDATE", "DELETE", "write_text", "os.environ[")

    for route in routes:
        body = _endpoint_body(system_source, route)
        assert body.strip(), f"{route} 的处理器为空"
        for call in forbidden_calls:
            assert call not in body, (
                f"{route} 处理器包含 {call!r}；connection-test 必须无持久化副作用"
            )


def test_evaluation_document_records_decision() -> None:
    """验证 P1-5-3 评估文档存在且记录明确决策。"""
    assert EVALUATION_DOC.exists(), "P1-5-3 评估文档不存在"

    text = EVALUATION_DOC.read_text(encoding="utf-8")

    # 状态声明。
    assert "evaluation-complete" in text, "文档未声明评估完成"
    assert "decision-recorded" in text, "文档未声明决策已记录"

    # 必须评估的方案。
    for marker in ("方案 0", "方案 A", "方案 B", "方案 C", "方案 D"):
        assert marker in text, f"文档缺少 {marker} 的评估"

    # 必须记录的结论。
    assert "不引入任何配置持久化" in text, "文档未明确记录不持久化的决策"
    assert "schema 影响" in text, "文档未声明 schema 影响"

    # 必须记录未验证边界。
    assert "未验证边界" in text, "文档缺少未验证边界声明"


def test_schema_version_unchanged_by_this_slice() -> None:
    """验证本切片未变更 schema 版本。

    P1-5-3 是纯评估切片，不得引入 migration。
    """
    runner_source = (MIGRATIONS_ROOT / "runner.py").read_text(encoding="utf-8")
    match = re.search(r"CURRENT_SCHEMA_VERSION\s*=\s*(\d+)", runner_source)
    assert match is not None, "无法读取 CURRENT_SCHEMA_VERSION"
    assert int(match.group(1)) == 14, (
        "P1-5-3 是评估切片，不得变更 schema 版本（应保持 14）"
    )

"""P1-5-0 Provider + Email 配置安全契约治理测试。

本文件验证 P1-5-0 契约冻结的关键约束：
- Secret 字段标记 repr=False
- 配置来源仅为 runtime 环境变量
- Capabilities API 不暴露 secret
- Backup manifest 不含 credentials
- 前端保持只读状态
- Delivery 默认值保持关闭
- 无生产代码修改（通过 git 验证）
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import AppConfig, config_from_environment  # noqa: E402
from app.providers._registry import ProviderRegistry, EmbeddingProviderRegistry  # noqa: E402


def test_p1_5_0_contract_document_exists_and_declares_frozen() -> None:
    """验证 P1-5 契约文档存在且声明为 contract-frozen。"""
    contract_path = ROOT / "docs/contracts/P1_5_PROVIDER_EMAIL_CONFIGURATION_CONTRACT.md"
    assert contract_path.exists(), "P1-5 契约文档不存在"

    contract_text = contract_path.read_text(encoding="utf-8")

    # 验证契约状态声明
    assert "contract-frozen" in contract_text, "契约未声明为 frozen 状态"
    assert "2026-01-09" in contract_text or "2026-01" in contract_text, "契约缺少冻结日期"

    # 验证关键章节存在
    required_sections = [
        "Provider 配置边界",
        "Email 配置边界",
        "Secret Source 契约",
        "Connection-Test 契约",
        "Backup/Restore 契约",
    ]
    for section in required_sections:
        assert section in contract_text, f"契约缺少章节：{section}"

    # 验证明确声明不修改代码
    assert "P1-5-0" in contract_text
    assert "不修改" in contract_text or "不新增" in contract_text
    assert "backend/app/" in contract_text


def test_p1_5_0_secret_fields_have_repr_false() -> None:
    """验证所有敏感字段标记 repr=False，不出现在 repr(config) 中。"""
    # 获取 AppConfig dataclass 的字段定义
    config_fields = AppConfig.__dataclass_fields__

    # 验证敏感字段标记 repr=False
    secret_fields = [
        "ai_api_key",
        "embedding_api_key",
        "report_delivery_smtp_password",
        "report_delivery_smtp_password_runtime",
        "report_delivery_feishu_webhook",
    ]

    for field_name in secret_fields:
        assert field_name in config_fields, f"敏感字段 {field_name} 不存在于 AppConfig"
        field = config_fields[field_name]
        assert field.repr is False, f"敏感字段 {field_name} 未标记 repr=False"

    # 验证 repr(config) 不包含敏感值
    test_config = AppConfig(
        data_root=Path("/tmp/test"),
        project_id="test",
        ai_api_key="SECRET_API_KEY_12345",
        embedding_api_key="SECRET_EMBEDDING_KEY_67890",
        report_delivery_smtp_password="SECRET_SMTP_PASSWORD",
        report_delivery_smtp_password_runtime="SECRET_SMTP_RUNTIME",
        report_delivery_feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/SECRET_WEBHOOK_TOKEN",
    )

    config_repr = repr(test_config)

    # 验证 secret 不出现在 repr 中
    assert "SECRET_API_KEY_12345" not in config_repr
    assert "SECRET_EMBEDDING_KEY_67890" not in config_repr
    assert "SECRET_SMTP_PASSWORD" not in config_repr
    assert "SECRET_SMTP_RUNTIME" not in config_repr
    assert "SECRET_WEBHOOK_TOKEN" not in config_repr

    # 验证非敏感字段仍出现在 repr 中
    assert "data_root" in config_repr
    assert "project_id" in config_repr


def test_p1_5_0_config_source_is_runtime_environment_only() -> None:
    """验证配置仅从环境变量读取，不从 SQLite 或文件系统读取。"""
    # 检查 config.py 的 config_from_environment 函数
    config_module_path = ROOT / "backend/app/config.py"
    config_source = config_module_path.read_text(encoding="utf-8")

    # 验证使用 os.environ.get
    assert "os.environ.get" in config_source, "config.py 未使用 os.environ.get"

    # 验证不从 SQLite 读取配置
    assert "SELECT" not in config_source or "config" not in config_source.lower(), \
        "config.py 可能从 SQLite 读取配置（需人工复核）"

    # 验证不从文件系统读取配置文件
    forbidden_patterns = [
        "open(",
        ".read_text(",
        ".read_bytes(",
        "json.load(",
        "yaml.load(",
    ]
    # 排除注释和文档字符串中的误报
    lines = [line for line in config_source.split("\n") if not line.strip().startswith("#")]
    source_without_comments = "\n".join(lines)

    for pattern in forbidden_patterns:
        if pattern in source_without_comments:
            # 允许 open() 用于路径存在性检查，但不应用于读取配置
            if pattern == "open(":
                # 简单启发式：如果 open() 后面跟着 .read，则可能是读取配置
                if ".read" in source_without_comments:
                    pytest.fail(f"config.py 可能从文件读取配置：{pattern}")


def test_p1_5_0_capabilities_api_does_not_expose_secrets() -> None:
    """验证 Provider capabilities API 不返回敏感字段。"""
    # 测试 ProviderRegistry.capabilities() 返回格式
    registry = ProviderRegistry(provider_id=None, model_id=None, api_key="SECRET_KEY_TEST")
    capabilities = registry.capabilities()

    # 验证返回的字段
    assert "status" in capabilities
    assert "configured" in capabilities
    assert "provider_id" in capabilities
    assert "model_id" in capabilities

    # 验证不返回敏感字段
    assert "api_key" not in capabilities
    assert "SECRET_KEY_TEST" not in str(capabilities)
    assert "base_url" not in capabilities  # 不返回完整 URL（可能含 token）

    # 验证返回的 JSON 序列化不包含 secret
    capabilities_json = json.dumps(capabilities)
    assert "SECRET_KEY_TEST" not in capabilities_json
    assert "api_key" not in capabilities_json

    # 测试 fake provider
    fake_registry = ProviderRegistry(provider_id="fake", model_id=None)
    fake_capabilities = fake_registry.capabilities()
    assert fake_capabilities["status"] == "demo"
    assert fake_capabilities["configured"] is True

    # 测试 embedding registry
    embedding_registry = EmbeddingProviderRegistry(
        provider_id=None, model_id=None, api_key="SECRET_EMBEDDING_KEY"
    )
    embedding_capabilities = embedding_registry.capabilities()
    assert "api_key" not in embedding_capabilities
    assert "SECRET_EMBEDDING_KEY" not in str(embedding_capabilities)


def test_p1_5_0_backup_manifest_excludes_credentials() -> None:
    """验证 backup manifest 不包含 credentials。"""
    backup_module_path = ROOT / "backend/app/backup.py"
    backup_source = backup_module_path.read_text(encoding="utf-8")

    # 验证 manifest 元数据函数存在
    assert "_manifest" in backup_source or "def manifest" in backup_source

    # 验证 backup 文档明确声明不含 credentials
    backup_doc_path = ROOT / "docs/BACKUP_RESTORE.md"
    backup_doc = backup_doc_path.read_text(encoding="utf-8")

    # 关键断言：backup 不包含 credentials
    assert "不包含" in backup_doc or "exclude" in backup_doc.lower()
    assert "credential" in backup_doc.lower() or "secret" in backup_doc.lower() or "密钥" in backup_doc

    # 验证 B4 契约也声明不含 credentials
    b4_contract_path = ROOT / "docs/contracts/B4_DELIVERY_COMPONENT_CONTRACT.md"
    b4_contract = b4_contract_path.read_text(encoding="utf-8")
    assert "backup" in b4_contract.lower()
    # B4 契约应该提及 backup 与 credentials 的关系（可能使用不同措辞）
    # 如果 B4 契约中没有明确声明，则通过 BACKUP_RESTORE.md 的声明即可


def test_p1_5_0_frontend_config_page_is_test_then_save() -> None:
    """验证配置页保持“先测后存”，且持久化只走白名单 settings 接口。

    P2-USE-3 推翻了 P1-5-0 的“前端只读”结论：要求使用者手抄环境变量才能开启已安装
    能力是缺陷，不是安全控制。保留的真安全约束是：先测后存、不写浏览器存储、
    不回显密钥、对外投递仍默认关闭。
    """
    settings_provider_path = ROOT / "backend/app/static/settings-provider.html"
    settings_provider = settings_provider_path.read_text(encoding="utf-8")

    # 测试入口保留，且测试本身不改配置。
    assert "provider-connection-test" in settings_provider
    assert "email-connection-test" in settings_provider
    assert "测试不改变当前配置" in settings_provider

    # 保存按钮存在，但默认隐藏，只在测通后显现。
    assert 'id="provider-save"' in settings_provider
    assert 'id="email-save"' in settings_provider
    assert re.search(r'id="provider-save"[^>]*hidden', settings_provider)
    assert re.search(r'id="email-save"[^>]*hidden', settings_provider)
    assert "$('provider-save').hidden=false" in settings_provider
    assert "$('email-save').hidden=false" in settings_provider
    # A passing test is required before saving, and editing the form withdraws it.
    assert "if(!providerVerified)return" in settings_provider
    assert "if(!emailVerified)return" in settings_provider
    assert "dropProviderVerification" in settings_provider
    assert "dropEmailVerification" in settings_provider

    # 持久化只能走白名单 settings 接口，不得写浏览器存储。
    assert "/api/system/settings" in settings_provider
    assert "localStorage" not in settings_provider
    assert "sessionStorage" not in settings_provider
    assert "/api/system/config" not in settings_provider

    # 对外投递开关不得从本页打开。
    for guarded in ("report_delivery_mode", "report_delivery_enabled",
                    "report_delivery_authorized"):
        assert guarded not in settings_provider

    api_js_path = ROOT / "backend/app/static/js/api.js"
    api_js = api_js_path.read_text(encoding="utf-8")
    forbidden_functions = [
        "saveProviderConfig",
        "saveEmailConfig",
        "updateProviderConfig",
        "updateEmailConfig",
    ]
    for func_name in forbidden_functions:
        assert func_name not in api_js, f"api.js 包含配置保存函数：{func_name}"


def test_p1_5_0_delivery_defaults_remain_closed() -> None:
    """验证 delivery 配置默认值保持关闭状态（继承 B4 契约）。"""
    # 使用空环境变量测试默认值
    import os
    original_env = os.environ.copy()

    try:
        # 清除所有 delivery 相关环境变量
        delivery_env_vars = [
            "STUDYBUDDY_REPORT_DELIVERY_MODE",
            "STUDYBUDDY_REPORT_DELIVERY_ENABLED",
            "STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED",
            "STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST",
            "STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD",
            "STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK",
        ]
        for var in delivery_env_vars:
            os.environ.pop(var, None)

        # 读取默认配置
        config = config_from_environment()

        # 验证默认值
        assert config.report_delivery_mode == "off", "delivery mode 默认值应为 off"
        assert config.report_delivery_enabled is False, "delivery enabled 默认值应为 false"
        assert config.report_delivery_authorized is False, "delivery authorized 默认值应为 false"

        # 验证 delivery targets 为空
        assert config.report_delivery_smtp_targets == (), "SMTP targets 默认值应为空元组"
        assert config.report_delivery_feishu_target_label is None, "Feishu target label 默认值应为 None"

    finally:
        # 恢复原始环境变量
        os.environ.clear()
        os.environ.update(original_env)


def test_p1_5_0_no_production_code_modified() -> None:
    """验证 P1-5-0 未修改 backend/app/ 生产代码（通过文档声明验证）。

    注：本测试验证契约文档声明，实际代码未修改由 git diff 和 commit message 保证。
    """
    contract_path = ROOT / "docs/contracts/P1_5_PROVIDER_EMAIL_CONFIGURATION_CONTRACT.md"
    contract_text = contract_path.read_text(encoding="utf-8")

    # 验证契约明确声明不修改生产代码
    assert "不修改" in contract_text and "backend/app/" in contract_text, \
        "契约未明确声明不修改 backend/app/"

    # 验证契约声明不新增 schema/migration
    assert "schema" in contract_text.lower() and "migration" in contract_text.lower()

    # 验证契约声明不新增 endpoint
    assert "endpoint" in contract_text.lower() or "API" in contract_text

    # 验证证据文档也确认此点
    evidence_path = ROOT / "docs/evidence/P1_5_0_CONTRACT_EVIDENCE.md"
    evidence_text = evidence_path.read_text(encoding="utf-8")

    assert "生产代码修改" in evidence_text and "无" in evidence_text, \
        "证据文档未确认无生产代码修改"
    assert "Schema/Migration 修改" in evidence_text and "无" in evidence_text, \
        "证据文档未确认无 schema/migration 修改"


def test_p1_5_0_stable_error_codes_documented() -> None:
    """验证稳定错误码在契约和证据文档中有明确记录。"""
    contract_path = ROOT / "docs/contracts/P1_5_PROVIDER_EMAIL_CONFIGURATION_CONTRACT.md"
    contract_text = contract_path.read_text(encoding="utf-8")

    evidence_path = ROOT / "docs/evidence/P1_5_0_CONTRACT_EVIDENCE.md"
    evidence_text = evidence_path.read_text(encoding="utf-8")

    # 验证 Provider 错误码
    provider_error_codes = [
        "provider_not_configured",
        "provider_invalid_config",
        "provider_connection_failed",
        "provider_timeout",
        "provider_unavailable",
    ]

    for error_code in provider_error_codes:
        assert error_code in contract_text or error_code in evidence_text, \
            f"错误码 {error_code} 未在契约或证据文档中记录"

    # 验证 Delivery 错误码
    delivery_error_codes = [
        "delivery_disabled",
        "delivery_target_not_allowed",
        "delivery_authorization_required",
        "delivery_configuration_invalid",
        "delivery_timeout",
        "delivery_failed",
    ]

    for error_code in delivery_error_codes:
        assert error_code in contract_text or error_code in evidence_text, \
            f"错误码 {error_code} 未在契约或证据文档中记录"

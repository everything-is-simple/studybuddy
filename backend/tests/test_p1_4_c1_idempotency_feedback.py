"""P1-4 C1 幂等与反馈切片测试

验证 P14-P1-01/P1-02/P1-03 的修复：
- P1-01: review/mark-mistake 幂等键
- P1-02: generation guard（仅验证已知有问题的页面）
- P1-03: 错误码映射扩充
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient
from app.config import AppConfig
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    """Isolated client with fake provider."""
    root = tmp_path / "data"
    config = AppConfig(
        data_root=root,
        max_upload_bytes=1024 * 1024,
        ai_provider_id="fake",
    )
    with TestClient(create_app(config)) as c:
        yield c


def test_review_html_sends_idempotency_key_for_review_and_mark():
    """P14-P1-01: review.html 的 mutateAttempt 现在发送 Idempotency-Key。

    C1 修复前：reviewAttempt 和 markAttempt 只设置 Content-Type。
    C1 修复后：headers 包含 Idempotency-Key。
    """
    review_html = (ROOT / "app" / "static" / "review.html").read_text(encoding="utf-8")
    # 验证 mutateAttempt 函数包含 Idempotency-Key
    assert "'Idempotency-Key':sbApi.idempotencyKey()" in review_html
    # 验证它在 reviewAttempt 和 markAttempt 的调用路径中
    assert "async function reviewAttempt" in review_html
    assert "async function markAttempt" in review_html
    assert "mutateAttempt(attemptId,'review'" in review_html
    assert "mutateAttempt(attemptId,'mark'" in review_html


def test_error_mapping_covers_c0_discovered_codes():
    """P14-P1-03: C0 发现的错误码现在都有用户友好映射。

    C0 发现的未映射码：
    - requires_converter, unsupported_rtf, corrupt_pdf (拒绝码)
    - revision_fingerprint_conflict (P14-P0-05 新发现)
    - retrieval_not_ready
    - material_not_found, task_not_found 等 *_not_found
    """
    api_js = (ROOT / "app" / "static" / "js" / "api.js").read_text(encoding="utf-8")
    known_start = api_js.index("safeError(error){const known={")
    known_end = api_js.index("};return known[error.code", known_start)
    known_block = api_js[known_start:known_end]
    
    # C0 明确发现的码
    assert "requires_converter:" in known_block
    assert "unsupported_rtf:" in known_block
    assert "corrupt_pdf:" in known_block
    assert "revision_fingerprint_conflict:" in known_block
    assert "retrieval_not_ready:" in known_block
    
    # 常见的 not_found 系列
    assert "material_not_found:" in known_block
    assert "task_not_found:" in known_block
    assert "card_not_found:" in known_block
    assert "exercise_not_found:" in known_block
    
    # 其他高频错误
    assert "file_too_large:" in known_block
    assert "review_not_allowed:" in known_block
    assert "review_duplicate:" in known_block


def test_error_mapping_does_not_expose_sensitive_info():
    """P14-P1-03: 错误映射不得暴露路径、SQL、traceback、密钥。

    所有映射的文案必须是用户可理解的中文，不得包含：
    - 文件路径（H:\\ 或 /）
    - SQL 关键字
    - Python traceback
    - api_key, secret, password
    """
    api_js = (ROOT / "app" / "static" / "js" / "api.js").read_text(encoding="utf-8")
    known_start = api_js.index("safeError(error){const known={")
    known_end = api_js.index("};return known[error.code", known_start)
    known_block = api_js[known_start:known_end]
    
    # 禁止的敏感信息
    forbidden = ["H:\\\\", ":/", "SELECT ", "INSERT ", "UPDATE ", "DELETE ", "Traceback", 
                 "api_key", "secret", "password", "stored_path"]
    for pattern in forbidden:
        assert pattern not in known_block, f"错误映射泄露敏感信息: {pattern}"


def test_idempotency_key_auto_addition_still_works():
    """验证共享层的自动 Idempotency-Key 仍然生效。

    sbApi._fetch 对所有 non-GET 请求自动添加 Idempotency-Key，
    除非显式传入 idempotent: false。这是 C1 之前就存在的机制。
    """
    api_js = (ROOT / "app" / "static" / "js" / "api.js").read_text(encoding="utf-8")
    assert "if(method!=='GET'&&!headers.has('Idempotency-Key')&&options.idempotent!==false)" in api_js
    assert "headers.set('Idempotency-Key',this.idempotencyKey())" in api_js


def test_generation_guard_exists_in_key_pages():
    """P14-P1-02 基线：关键页面已有 generation guard。

    本测试不是 C1 的新增功能，而是确认既有保护仍在；
    C1 只修复"实测 stale 更新"，不做无关前端重构。
    
    实际有 generation 的页面（经 grep 确认，2025-01-08）：
    - note-detail.html, plan-detail.html
    - practice-result.html, practice-session.html
    - review.html
    
    其他页面（materials.html、notes.html、plans.html、cards.html、
    exercises.html、qa.html 等）没有 generation guard，但 C1 不强制添加，
    除非有实测证据证明它们确实会出现 stale response 问题。
    
    P14-P1-02 的范围是"补齐实测 generation guard"，不是"给所有页面加 generation"。
    """
    pages_with_generation = [
        "note-detail.html",
        "plan-detail.html",
        "practice-result.html",
        "practice-session.html",
        "review.html",
    ]
    for page in pages_with_generation:
        content = (ROOT / "app" / "static" / page).read_text(encoding="utf-8")
        assert "let generation" in content or "let run" in content, f"{page} 缺少 generation guard"
        assert "++generation" in content or "++run" in content, f"{page} 缺少 generation 递增"
        assert "!==generation" in content or "!==run" in content, f"{page} 缺少 generation 检查"

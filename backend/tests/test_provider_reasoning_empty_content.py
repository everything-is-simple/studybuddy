"""思考型模型空 content 场景解析测试。

glm-5.3-flash 等思考/非思考双模式模型会把推理过程放在
message.reasoning_content；当 max_tokens 预算被推理耗尽时
content 为空且 finish_reason=length。此时应报
provider_output_too_large（预算耗尽）而非 provider_malformed_response。
"""
from __future__ import annotations

import pytest

from app.providers._helpers import _parse_openai_response
from app.providers._core import ProviderError


def _payload(content: str | None, finish_reason: str, reasoning: str | None = None) -> dict:
    message: dict = {"role": "assistant"}
    if content is not None:
        message["content"] = content
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return {"choices": [{"message": message, "finish_reason": finish_reason}]}


def test_empty_content_with_reasoning_and_length_is_output_too_large():
    with pytest.raises(ProviderError) as exc:
        _parse_openai_response(
            _payload(None, "length", "推理过程……"), "openai", "glm-5.3-flash", 4000)
    assert exc.value.code == "provider_output_too_large"


def test_empty_content_without_reasoning_still_malformed():
    with pytest.raises(ProviderError) as exc:
        _parse_openai_response(_payload("", "stop"), "openai", "test-model", 4000)
    assert exc.value.code == "provider_malformed_response"


def test_nonempty_content_parses_normally():
    result = _parse_openai_response(
        _payload("琥珀的形成需要四个条件 [ctx-1]。", "stop"), "openai", "glm-5.3-flash", 4000)
    assert "琥珀" in result.answer_text
    assert result.citation_keys == ["ctx-1"]

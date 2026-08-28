"""Fake LLM provider for testing and demo purposes."""

from __future__ import annotations

import hashlib
import json

from ._core import (
    FAKE_MODEL_ID,
    FAKE_PROVIDER_ID,
    MAX_PROVIDER_PROMPT_CHARS,
    ProviderError,
    ProviderRequest,
    ProviderResult,
)
from ._helpers import _snippet


class FakeLLMProvider:
    provider_id = FAKE_PROVIDER_ID
    model_id = FAKE_MODEL_ID

    def generate_answer(self, request: ProviderRequest) -> ProviderResult:
        question = request.question.strip()
        if not question or len(question) > MAX_PROVIDER_PROMPT_CHARS:
            raise ProviderError("provider_invalid_request")
        citation_keys: list[str] = []
        snippets: list[str] = []
        prompt_chars = len(question)
        for block in request.context_blocks[:3]:
            key = str(block.get("citation_key", ""))
            text = str(block.get("text", "")).strip()
            prompt_chars += len(text)
            if key and key not in citation_keys:
                citation_keys.append(key)
            if text:
                snippets.append(_snippet(text))
        if prompt_chars > request.max_prompt_chars:
            raise ProviderError("provider_invalid_request")
        fingerprint = hashlib.sha256((question + "\x1f" + "\x1f".join(citation_keys)).encode("utf-8")).hexdigest()[:12]
        if request.generation_kind:
            if request.generation_kind not in {"card", "exercise", "note"} or not 1 <= request.generation_count <= 10:
                raise ProviderError("provider_invalid_request")
            if request.generation_kind == "note" and request.generation_count != 1:
                raise ProviderError("provider_invalid_request")
            if request.generation_kind == "exercise" and request.exercise_type not in {"multiple_choice", "true_false", "short_answer"}:
                raise ProviderError("provider_invalid_request")
            if not citation_keys or not snippets:
                raise ProviderError("provider_invalid_request")
            if request.generation_kind == "note":
                blocks = [
                    {"block_kind": "heading", "content": f"Notes on {question}", "citation_keys": [citation_keys[0]]},
                    {"block_kind": "text", "content": f"The retrieved material contains evidence relevant to {question}.", "citation_keys": [citation_keys[0]]},
                ]
                answer = json.dumps({"title": f"Notes on {question}", "blocks": blocks}, ensure_ascii=False, separators=(",", ":"))
            else:
                items: list[dict[str, object]] = []
                for index in range(request.generation_count):
                    key, snippet = citation_keys[index % len(citation_keys)], snippets[index % len(snippets)]
                    if request.generation_kind == "card":
                        items.append({"front": f"What does the source say about {question}?", "back": snippet,
                                      "explanation": "Generated from retrieved source context.", "tags": ["generated"],
                                      "citations": [key]})
                    elif request.exercise_type == "multiple_choice":
                        items.append({"exercise_type": "multiple_choice", "prompt": f"Which statement is supported about {question}?",
                                      "options": [snippet, "The source provides no support."], "answer_key": 0,
                                      "explanation": "The first option is grounded in the cited context.", "citations": [key]})
                    elif request.exercise_type == "true_false":
                        items.append({"exercise_type": "true_false", "prompt": f"True or false: {snippet}",
                                      "options": [], "answer_key": True,
                                      "explanation": "The statement is grounded in the cited context.", "citations": [key]})
                    else:
                        items.append({"exercise_type": "short_answer", "prompt": f"Explain the source finding about {question}.",
                                      "options": [], "answer_key": snippet,
                                      "explanation": "Compare the response with the cited context.", "citations": [key]})
                answer = json.dumps({"items": items}, ensure_ascii=False, separators=(",", ":"))
        elif snippets:
            cited = " ".join(f"[{key}]" for key in citation_keys)
            answer = f"Fake answer {fingerprint}: {snippets[0]} {cited}".strip()
        else:
            answer = f"Fake answer {fingerprint}: no retrieved context was available."
        if len(answer) > request.max_answer_chars:
            raise ProviderError("provider_output_too_large")
        prompt_tokens = max(1, prompt_chars // 4)
        completion_tokens = max(1, len(answer) // 4)
        return ProviderResult(
            answer_text=answer,
            citation_keys=citation_keys,
            provider_id=self.provider_id,
            model_id=self.model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason="stop",
        )

"""S2 material modules API, source selection and AI draft confirmation."""
from __future__ import annotations

import json
import sqlite3

from fastapi import HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from ..repositories import knowledge_modules as km
from ..repositories.connection import connect
from ..repositories.ai import assemble_context
from ..providers import ProviderRequest, ProviderError, ProviderRegistry
from ..http_errors import _provider_http_status


class ModuleFields(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=4000)
    importance: int = Field(default=1, ge=1, le=5, strict=True)
    difficulty: int = Field(default=3, ge=1, le=5, strict=True)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    tags: list[str] = Field(default_factory=list, max_length=10)


class ModuleCreate(ModuleFields):
    material_id: str = Field(min_length=1, max_length=100)
    chunk_ids: list[str] = Field(min_length=1, max_length=10)


class ModulePatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    importance: int | None = Field(default=None, ge=1, le=5, strict=True)
    difficulty: int | None = Field(default=None, ge=1, le=5, strict=True)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    tags: list[str] | None = Field(default=None, max_length=10)


class ModuleExtract(BaseModel):
    model_config = ConfigDict(extra='forbid')
    material_id: str = Field(min_length=1, max_length=100)
    max_modules: int = Field(default=3, ge=1, le=10, strict=True)
    chunk_ids: list[str] | None = Field(default=None, min_length=1, max_length=10)


def _error(error):
    code = str(error)
    status = 404 if code in {'material_not_found','knowledge_module_not_found'} else 409 if code in {
        'source_deleted','knowledge_source_invalid','knowledge_module_invalid_state','retrieval_not_ready'} else 400
    return HTTPException(status_code=status, detail=code)


def register_routes(app, context):
    def run(action):
        try:
            with connect(app.state.config.database_path) as conn:
                return action(conn)
        except ValueError as error:
            raise _error(error) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail='knowledge_module_failed') from None

    project = lambda: app.state.config.project_id

    @app.get('/api/knowledge-modules')
    def list_modules(material_id: str | None = None, q: str | None = None, lifecycle: str | None = None,
                     status: str | None = None, importance: int | None = None, limit: int = 50, offset: int = 0):
        return run(lambda c: km.list_modules(c, project_id=project(), material_id=material_id, query=q,
                                             lifecycle=lifecycle, learn_status=status, importance=importance, limit=limit, offset=offset))

    @app.get('/api/knowledge-modules/sources')
    def sources(material_id: str):
        return run(lambda c: km.source_chunks(c, project_id=project(), material_id=material_id))

    @app.post('/api/knowledge-modules', status_code=201)
    def create_module(request: ModuleCreate):
        return run(lambda c: km.create_modules(c, project_id=project(), material_id=request.material_id, payloads=[request.model_dump()])[0])

    @app.post('/api/knowledge-modules/extract')
    def extract_modules(request: ModuleExtract):
        config = app.state.config
        def prepare(c):
            chunks = request.chunk_ids or [r['chunk_id'] for r in km.source_chunks(c, project_id=project(), material_id=request.material_id)[:10]]
            if not chunks:
                raise ValueError('retrieval_not_ready')
            evidence = km.evidence_for_chunks(c, project_id=project(), material_id=request.material_id, chunk_ids=chunks)
            blocks = assemble_context(c, project_id=project(), hits=[{'chunk_id': cid} for cid in chunks])['context_blocks']
            return evidence, blocks
        evidence, blocks = run(prepare)
        try:
            provider = ProviderRegistry(config.ai_provider_id, config.ai_model_id) if config.ai_provider_id == 'fake' else ProviderRegistry(
                config.ai_provider_id, config.ai_model_id, base_url=config.ai_base_url, api_key=config.ai_api_key,
                timeout_seconds=config.ai_timeout_seconds, max_retries=config.ai_max_retries)
            result = provider.configured_provider().generate_answer(ProviderRequest(
                question='提取可独立复习的知识要点，重要性和难度均使用1到5。', context_blocks=blocks,
                generation_kind='knowledge_module', generation_count=request.max_modules,
                max_output_tokens=config.ai_max_output_tokens, max_prompt_chars=config.ai_max_prompt_chars,
                max_answer_chars=config.ai_max_answer_chars))
        except ProviderError as error:
            raise HTTPException(status_code=_provider_http_status(error.code), detail=error.code) from None
        try:
            if len(result.answer_text) > 12000:
                raise ValueError('knowledge_generation_invalid')
            payload = json.loads(result.answer_text)
            if not isinstance(payload, dict) or set(payload) != {'items'} or not isinstance(payload['items'], list) or len(payload['items']) != request.max_modules:
                raise ValueError('knowledge_generation_invalid')
            keys = {b['citation_key']: cid for b, cid in zip(blocks, evidence['chunk_ids'])}
            prepared = []
            for item in payload['items']:
                if not isinstance(item, dict) or set(item) != {'title','description','importance','difficulty','tags','citations'}:
                    raise ValueError('knowledge_generation_invalid')
                citations = item['citations']
                if not isinstance(citations, list) or not citations or any(not isinstance(k, str) or k not in keys for k in citations):
                    raise ValueError('knowledge_generation_invalid')
                values = {k:v for k,v in item.items() if k != 'citations'}
                km._values(values)
                values['chunk_ids'] = list(dict.fromkeys(keys[k] for k in citations))
                prepared.append(values)
        except (ValueError, TypeError, KeyError):
            raise HTTPException(status_code=502, detail='knowledge_generation_invalid') from None
        def persist(c):
            if km.source_status(c, project(), evidence) != 'valid':
                raise ValueError('knowledge_source_invalid')
            return km.create_modules(c, project_id=project(), material_id=request.material_id, payloads=prepared,
                                     provenance='ai_generated', provider_id=result.provider_id, model_id=result.model_id)
        return {'draft_modules': run(persist)}

    def require(c, module_id):
        result = km.get_module(c, project_id=project(), module_id=module_id)
        if result is None:
            raise ValueError('knowledge_module_not_found')
        return result

    @app.get('/api/knowledge-modules/{module_id}')
    def detail(module_id: str):
        return run(lambda c: require(c, module_id))

    @app.get('/api/knowledge-modules/{module_id}/practice-history')
    def history(module_id: str):
        def get(c):
            require(c, module_id)
            return {'module_id': module_id, 'attempts': km.practice_history(c, project_id=project(), module_id=module_id)}
        return run(get)

    @app.patch('/api/knowledge-modules/{module_id}')
    def update(module_id: str, request: ModulePatch):
        return run(lambda c: km.update_module(c, project_id=project(), module_id=module_id, payload=request.model_dump(exclude_unset=True)))

    @app.post('/api/knowledge-modules/{module_id}/confirm')
    def confirm(module_id: str):
        return run(lambda c: km.transition_module(c, project_id=project(), module_id=module_id, action='confirm'))

    @app.post('/api/knowledge-modules/{module_id}/reject')
    def reject(module_id: str):
        return run(lambda c: km.transition_module(c, project_id=project(), module_id=module_id, action='reject'))

    @app.delete('/api/knowledge-modules/{module_id}', status_code=204)
    def delete(module_id: str):
        run(lambda c: km.transition_module(c, project_id=project(), module_id=module_id, action='delete'))
        return Response(status_code=204)

    return context

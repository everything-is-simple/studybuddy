from __future__ import annotations

import json
import mimetypes
import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from .adapters.file_parsers import ParseOptions, parse_file
from .config import AppConfig, config_from_environment
from .repository import VALID_STATUSES, connect, get_material, get_spans, list_materials, save_material_with_extraction
from .storage import sha256_file, store_original


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: AppConfig = app.state.config
    config.data_root.mkdir(parents=True, exist_ok=True)
    with connect(config.database_path):
        pass
    yield


def _valid_filename(raw_name: str) -> str | None:
    original_name = Path(raw_name).name
    if (not raw_name or not original_name or original_name in {".", ".."}
            or raw_name != original_name or "/" in raw_name or "\\" in raw_name):
        return None
    return original_name


def _item(original_name: str, status: str, *, material_id: str | None = None,
          extraction_id: str | None = None, source_sha256: str = "", text_length: int = 0,
          span_count: int = 0, error_code: str | None = None,
          warnings: list[str] | None = None) -> dict[str, object]:
    return {"original_name": original_name, "status": status, "material_id": material_id,
            "extraction_id": extraction_id, "source_sha256": source_sha256,
            "text_length": text_length, "span_count": span_count,
            "error_code": error_code, "warnings": warnings or []}


async def _process_file(file: UploadFile, config: AppConfig, *, batch: bool) -> dict[str, object]:
    raw_name = file.filename or ""
    original_name = _valid_filename(raw_name)
    if original_name is None:
        await file.close()
        if not batch:
            raise HTTPException(status_code=400, detail="invalid_filename")
        return _item(raw_name, "rejected", error_code="invalid_filename")
    temporary_path: Path | None = None
    stored_path: Path | None = None
    stored_created = False
    try:
        config.data_root.mkdir(parents=True, exist_ok=True)
        suffix = Path(original_name).suffix.lower()
        with tempfile.NamedTemporaryFile(dir=config.data_root, prefix=".incoming-", suffix=suffix, delete=False) as handle:
            temporary_path = Path(handle.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > config.max_upload_bytes:
                    if not batch:
                        raise HTTPException(status_code=413, detail="file_too_large")
                    return _item(original_name, "rejected", error_code="file_too_large")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        digest = sha256_file(temporary_path)
        stored = store_original(temporary_path, original_name, digest, config.originals_root)
        stored_path, stored_created = stored.path, stored.created
        result = parse_file(temporary_path, declared_media_type=file.content_type,
                            options=ParseOptions(max_bytes=config.max_upload_bytes))
        try:
            with connect(config.database_path) as connection:
                material_id, extraction_id = save_material_with_extraction(
                    connection, config.project_id, original_name, digest, stored.path,
                    file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream", result,
                )
        except Exception as exc:
            if stored.created:
                stored.path.unlink(missing_ok=True)
            if not batch:
                raise HTTPException(status_code=500, detail="material_persist_failed") from exc
            return _item(original_name, "failed", source_sha256=digest, error_code="material_persist_failed")
        return _item(original_name, result.status, material_id=material_id, extraction_id=extraction_id,
                     source_sha256=result.source_sha256, text_length=len(result.text),
                     span_count=len(result.spans), error_code=result.error_code, warnings=result.warnings)
    except HTTPException:
        raise
    except (OSError, ValueError):
        if stored_created and stored_path is not None:
            stored_path.unlink(missing_ok=True)
        return _item(original_name, "failed", error_code="file_processing_failed")
    finally:
        await file.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def create_app(config: AppConfig | None = None) -> FastAPI:
    app = FastAPI(title="StudyBuddy", lifespan=lifespan)
    app.state.config = config or config_from_environment()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/materials")
    def materials(status: str | None = None) -> list[dict[str, object]]:
        if status is not None and status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="invalid_status")
        with connect(app.state.config.database_path) as connection:
            return [dict(row) for row in list_materials(connection, status)]

    @app.get("/api/materials/{material_id}")
    def material(material_id: str) -> dict[str, object]:
        with connect(app.state.config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            payload = dict(row)
            payload["warnings"] = json.loads(payload.pop("warnings_json"))
            payload["spans"] = [dict(span) for span in get_spans(connection, row["extraction_id"])]
            return payload

    @app.post("/api/materials", status_code=201)
    async def upload_material(file: Annotated[UploadFile, File(...)]) -> dict[str, object]:
        return await _process_file(file, app.state.config, batch=False)

    @app.post("/api/materials/batch", status_code=201)
    async def upload_materials(files: Annotated[list[UploadFile], File(...)]) -> dict[str, object]:
        items = [await _process_file(file, app.state.config, batch=True) for file in files]
        counts = {status: sum(item["status"] == status for item in items)
                  for status in ("success", "empty", "rejected", "failed")}
        return {"batch_id": f"batch_{uuid.uuid4().hex}", "total": len(items), **counts, "items": items}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    return app


INDEX_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StudyBuddy 文件导入</title>
<style>body{font-family:system-ui,sans-serif;max-width:1060px;margin:0 auto;padding:32px;color:#17202a;background:#f6f7f9}main{background:white;border:1px solid #d8dde3;padding:24px;border-radius:8px}h1{margin-top:0}button{background:#1769aa;color:white;border:0;border-radius:4px;padding:9px 14px;cursor:pointer}input{margin:12px 0}.status{padding:12px 0;color:#52606d}.summary{display:flex;gap:16px;flex-wrap:wrap;color:#52606d}.batch-item{border-top:1px solid #e5e7eb;padding:7px 0}.layout{display:grid;grid-template-columns:320px 1fr;gap:24px;margin-top:24px}.filters{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0 12px}.filters button{background:#e8edf2;color:#17202a;padding:6px 9px}.filters button.active{background:#1769aa;color:white}.item{display:block;width:100%;text-align:left;border:1px solid #d8dde3;background:#fff;color:#17202a;margin:6px 0}.item:hover{background:#eef5fb}.meta{color:#52606d;font-size:14px}.content{white-space:pre-wrap;line-height:1.6;max-height:55vh;overflow:auto;border-top:1px solid #e5e7eb;padding-top:16px}@media(max-width:700px){body{padding:12px}.layout{grid-template-columns:1fr}}</style></head>
<body><main><h1>StudyBuddy 文件导入</h1><form id="form"><input id="file" type="file" multiple required><button type="submit">导入文件</button></form><div id="status" class="status"></div><div id="summary" class="summary"></div><div id="batch-items"></div><section class="layout"><aside><h2>材料</h2><div id="filters" class="filters"></div><div id="materials"></div></aside><article><h2 id="title">选择材料</h2><div id="meta" class="meta"></div><div id="warnings" class="meta"></div><div id="spans" class="meta"></div><div id="content" class="content"></div></article></section></main>
<script>const statusEl=document.querySelector('#status'),listEl=document.querySelector('#materials'),summaryEl=document.querySelector('#summary'),batchItemsEl=document.querySelector('#batch-items'),filterEl=document.querySelector('#filters');let currentFilter='';
async function loadList(){const url=currentFilter?`/api/materials?status=${currentFilter}`:'/api/materials';const r=await fetch(url);const items=await r.json();listEl.innerHTML=items.map(x=>`<button class="item" data-id="${x.id}">${x.original_name}<br><span class="meta">${x.status} · ${x.media_type} · ${x.text_length} 字 · ${x.span_count} spans${x.error_code?' · '+x.error_code:''}</span></button>`).join('')||'<p class="meta">暂无材料</p>';document.querySelectorAll('.item').forEach(x=>x.onclick=()=>loadMaterial(x.dataset.id));}
async function loadMaterial(id){const r=await fetch('/api/materials/'+id);if(!r.ok){statusEl.textContent='读取失败';return}const x=await r.json();document.querySelector('#title').textContent=x.original_name;document.querySelector('#meta').textContent=`${x.status} · ${x.parser_id} ${x.parser_version} · SHA-256 ${x.source_sha256}`;document.querySelector('#warnings').textContent=x.error_code?`error_code: ${x.error_code} · ${x.warnings.join(' ')}`:x.warnings.join(' ');document.querySelector('#spans').textContent=`spans: ${x.spans.length} · ${x.spans.map(s=>s.label).join(', ')}`;document.querySelector('#content').textContent=x.text||x.spans.filter(s=>s.text.trim()).map(s=>`[${s.label}]\\n${s.text}`).join('\\n\\n')||'没有可显示的正文';}
function filters(){filterEl.innerHTML=['全部','成功','空文件','拒绝','失败'].map((label,i)=>`<button class="${(i?['success','empty','rejected','failed'][i-1]:'')===currentFilter?'active':''}" data-status="${i?['success','empty','rejected','failed'][i-1]:''}">${label}</button>`).join('');filterEl.querySelectorAll('button').forEach(b=>b.onclick=()=>{currentFilter=b.dataset.status;filters();loadList()})}
document.querySelector('#form').onsubmit=async e=>{e.preventDefault();const files=[...document.querySelector('#file').files];if(!files.length)return;statusEl.textContent=`正在导入 ${files.length} 个文件`;const body=new FormData();if(files.length===1){body.append('file',files[0])}else{files.forEach(file=>body.append('files',file))}const r=await fetch(files.length===1?'/api/materials':'/api/materials/batch',{method:'POST',body});const x=await r.json();if(!r.ok){statusEl.textContent=typeof x.detail==='string'?x.detail:JSON.stringify(x.detail);return}if(files.length===1){statusEl.textContent=`导入完成：${x.status}，${x.text_length} 字符`;summaryEl.textContent='';batchItemsEl.innerHTML='';await loadList();if(x.material_id)await loadMaterial(x.material_id);return}statusEl.textContent=`批量导入完成：${x.total} 个文件`;summaryEl.textContent=`总数 ${x.total} · 成功 ${x.success} · 空文件 ${x.empty} · 拒绝 ${x.rejected} · 失败 ${x.failed}`;batchItemsEl.innerHTML=x.items.map(item=>`<div class="batch-item">${item.original_name} · ${item.status}${item.error_code?' · '+item.error_code:''}${item.warnings.length?' · '+item.warnings.join(' '):''}</div>`).join('');await loadList();const first=x.items.find(item=>item.material_id);if(first)await loadMaterial(first.material_id)};filters();loadList();</script></body></html>"""

app = create_app()

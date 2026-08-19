from __future__ import annotations

import json
import mimetypes
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from .adapters.file_parsers import ParseOptions, parse_file
from .config import AppConfig, config_from_environment
from .repository import connect, get_material, get_spans, list_materials, save_material_with_extraction
from .storage import sha256_file, store_original


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: AppConfig = app.state.config
    config.data_root.mkdir(parents=True, exist_ok=True)
    with connect(config.database_path):
        pass
    yield


def create_app(config: AppConfig | None = None) -> FastAPI:
    app = FastAPI(title="StudyBuddy", lifespan=lifespan)
    app.state.config = config or config_from_environment()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/materials")
    def materials() -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return [dict(row) for row in list_materials(connection)]

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
        config: AppConfig = app.state.config
        original_name = Path(file.filename or "").name
        if not original_name or original_name in {".", ".."}:
            raise HTTPException(status_code=400, detail="invalid_filename")
        suffix = Path(original_name).suffix.lower()
        config.data_root.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=config.data_root, prefix=".incoming-", suffix=suffix, delete=False) as handle:
                temporary_path = Path(handle.name)
                size = 0
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > config.max_upload_bytes:
                        raise HTTPException(status_code=413, detail="file_too_large")
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            digest = sha256_file(temporary_path)
            stored = store_original(temporary_path, original_name, digest, config.originals_root)
            result = parse_file(temporary_path, declared_media_type=file.content_type,
                                options=ParseOptions(max_bytes=config.max_upload_bytes))
            with connect(config.database_path) as connection:
                material_id, extraction_id = save_material_with_extraction(
                    connection, config.project_id, original_name, digest, stored.path,
                    file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream", result,
                )
            return {"material_id": material_id, "extraction_id": extraction_id, "original_name": original_name,
                    "status": result.status, "source_sha256": result.source_sha256, "text_length": len(result.text),
                    "span_count": len(result.spans), "error_code": result.error_code, "warnings": result.warnings}
        finally:
            await file.close()
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    return app


INDEX_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StudyBuddy 文件导入</title>
<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:0 auto;padding:32px;color:#17202a;background:#f6f7f9}main{background:white;border:1px solid #d8dde3;padding:24px;border-radius:8px}h1{margin-top:0}button{background:#1769aa;color:white;border:0;border-radius:4px;padding:9px 14px;cursor:pointer}input{margin:12px 0}.status{padding:12px 0;color:#52606d}.layout{display:grid;grid-template-columns:280px 1fr;gap:24px;margin-top:24px}.item{display:block;width:100%;text-align:left;border:1px solid #d8dde3;background:#fff;color:#17202a;margin:6px 0}.item:hover{background:#eef5fb}.meta{color:#52606d;font-size:14px}.content{white-space:pre-wrap;line-height:1.6;max-height:55vh;overflow:auto;border-top:1px solid #e5e7eb;padding-top:16px}@media(max-width:700px){body{padding:12px}.layout{grid-template-columns:1fr}}</style></head>
<body><main><h1>StudyBuddy 文件导入</h1><form id="form"><input id="file" type="file" required><button type="submit">导入文件</button></form><div id="status" class="status"></div><section class="layout"><aside><h2>材料</h2><div id="materials"></div></aside><article><h2 id="title">选择材料</h2><div id="meta" class="meta"></div><div id="content" class="content"></div></article></section></main>
<script>const statusEl=document.querySelector('#status'),listEl=document.querySelector('#materials');
async function loadList(){const r=await fetch('/api/materials');const items=await r.json();listEl.innerHTML=items.map(x=>`<button class="item" data-id="${x.id}">${x.original_name}<br><span class="meta">${x.status} · ${x.media_type}</span></button>`).join('')||'<p class="meta">暂无材料</p>';document.querySelectorAll('.item').forEach(x=>x.onclick=()=>loadMaterial(x.dataset.id));}
async function loadMaterial(id){const r=await fetch('/api/materials/'+id);if(!r.ok){statusEl.textContent='读取失败';return}const x=await r.json();document.querySelector('#title').textContent=x.original_name;document.querySelector('#meta').textContent=`${x.status} · ${x.parser_id} ${x.parser_version} · SHA-256 ${x.source_sha256}`;document.querySelector('#content').textContent=x.text||x.spans.map(s=>`[${s.label}]\n${s.text}`).join('\n\n')||'没有可显示的正文';}
document.querySelector('#form').onsubmit=async e=>{e.preventDefault();const file=document.querySelector('#file').files[0];if(!file)return;statusEl.textContent='正在导入';const body=new FormData();body.append('file',file);const r=await fetch('/api/materials',{method:'POST',body});const x=await r.json();if(!r.ok){statusEl.textContent=typeof x.detail==='string'?x.detail:JSON.stringify(x.detail);return}statusEl.textContent=`导入完成：${x.status}，${x.text_length} 字符`;await loadList();await loadMaterial(x.material_id);};loadList();</script></body></html>"""

app = create_app()

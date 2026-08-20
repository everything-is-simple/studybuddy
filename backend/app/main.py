from __future__ import annotations

import io
import json
import mimetypes
import sqlite3
import os
import tempfile
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from .adapters.file_parsers import ParseOptions, parse_file
from .config import AppConfig, config_from_environment
from .repository import (VALID_STATUSES, connect, get_material, get_spans, list_deleted_materials,
                         list_materials, material_state, purge_material, rename_material, restore_material,
                         save_material_with_extraction, soft_delete_material)
from .storage import sha256_file, store_original


def _download_name(original_name: str, suffix: str = "") -> str:
    safe_name = Path(original_name).name.replace('"', "'")
    return f"{safe_name}{suffix}"


def _checked_original_path(config: AppConfig, stored_path: str, expected_hash: str) -> Path:
    root = config.originals_root.resolve()
    target = Path(stored_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="original_path_invalid") from exc
    if not target.is_file():
        raise HTTPException(status_code=500, detail="original_not_found")
    if sha256_file(target) != expected_hash:
        raise HTTPException(status_code=500, detail="original_hash_mismatch")
    return target


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


class RenameMaterialRequest(BaseModel):
    original_name: str


class ExportMaterialsRequest(BaseModel):
    material_ids: list[str]
    include_original: bool = True
    include_text: bool = True


def _rename_name(raw_name: str) -> str | None:
    name = raw_name.strip()
    if len(name) > 255:
        return None
    return _valid_filename(name)


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
    def materials(status: str | None = None, q: str | None = None) -> list[dict[str, object]]:
        if status is not None and status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="invalid_status")
        with connect(app.state.config.database_path) as connection:
            return [dict(row) for row in list_materials(connection, status, q)]

    @app.get("/api/materials/deleted")
    def deleted_materials() -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return [dict(row) for row in list_deleted_materials(connection)]

    @app.post("/api/materials/export")
    def export_materials(request: ExportMaterialsRequest):
        if not request.material_ids or len(request.material_ids) > 200:
            raise HTTPException(status_code=400, detail="invalid_export_request")
        if len(set(request.material_ids)) != len(request.material_ids) or not (request.include_original or request.include_text):
            raise HTTPException(status_code=400, detail="invalid_export_request")
        placeholders = ",".join("?" for _ in request.material_ids)
        with connect(app.state.config.database_path) as connection:
            rows = connection.execute(
                f"SELECT m.id, m.original_name, m.stored_path, m.source_sha256, e.text "
                f"FROM materials m JOIN extractions e ON e.material_id = m.id "
                f"WHERE m.id IN ({placeholders}) AND m.deleted_at IS NULL",
                request.material_ids,
            ).fetchall()
        if len(rows) != len(request.material_ids):
            raise HTTPException(status_code=404, detail="material_not_found")
        by_id = {row["id"]: row for row in rows}
        ordered = [by_id[material_id] for material_id in request.material_ids]
        buffer = io.BytesIO()
        used: set[str] = set()
        logical_size = 0
        try:
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for row in ordered:
                    name = Path(row["original_name"]).name
                    stem, suffix = Path(name).stem, Path(name).suffix
                    def unique_entry(prefix: str, filename: str) -> str:
                        candidate = f"{prefix}/{filename}"
                        index = 2
                        while candidate in used:
                            candidate = f"{prefix}/{stem} ({index}){suffix}"
                            index += 1
                        used.add(candidate)
                        return candidate
                    if request.include_original:
                        target = _checked_original_path(app.state.config, row["stored_path"], row["source_sha256"])
                        data = target.read_bytes()
                        logical_size += len(data)
                        if logical_size > 256 * 1024 * 1024:
                            raise HTTPException(status_code=413, detail="export_too_large")
                        archive.writestr(unique_entry("originals", name), data)
                    if request.include_text:
                        text_name = f"{name}.extracted.txt"
                        data = str(row["text"]).encode("utf-8")
                        logical_size += len(data)
                        if logical_size > 256 * 1024 * 1024:
                            raise HTTPException(status_code=413, detail="export_too_large")
                        archive.writestr(unique_entry("text", text_name), data)
        except HTTPException:
            raise
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=500, detail="material_export_failed") from exc
        buffer.seek(0)
        return Response(content=buffer.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="studybuddy-materials.zip"'})

    @app.get("/api/materials/{material_id}/original")
    def download_original(material_id: str):
        config = app.state.config
        with connect(config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            target = _checked_original_path(config, row["stored_path"], row["source_sha256"])
            return FileResponse(target, media_type=row["media_type"], filename=_download_name(row["original_name"]))

    @app.get("/api/materials/{material_id}/text")
    def export_text(material_id: str):
        config = app.state.config
        with connect(config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            headers = {"Content-Disposition": f'attachment; filename="{_download_name(row["original_name"], ".extracted.txt")}"'}
            return Response(content=row["text"], media_type="text/plain", headers=headers)

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

    @app.post("/api/materials/{material_id}/restore")
    def restore_existing_material(material_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                state = material_state(connection, material_id)
                row = restore_material(connection, material_id)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="material_restore_failed") from exc
        if row is None:
            if state == "missing":
                raise HTTPException(status_code=404, detail="material_not_found")
            raise HTTPException(status_code=404, detail="material_not_deleted")
        return dict(row)

    @app.post("/api/materials/{material_id}/purge")
    def purge_existing_material(material_id: str) -> dict[str, object]:
        config = app.state.config
        try:
            with connect(config.database_path) as connection:
                source_sha256, stored_path, _ = purge_material(connection, material_id)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="material_purge_failed") from exc
        if source_sha256 is None or stored_path is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        try:
            with connect(config.database_path) as connection:
                remaining = connection.execute(
                    "SELECT COUNT(*) FROM materials WHERE source_sha256 = ?", (source_sha256,)
                ).fetchone()[0]
        except sqlite3.Error:
            remaining = 1
        if remaining == 0:
            try:
                target = _checked_original_path(config, stored_path, source_sha256)
                target.unlink(missing_ok=True)
            except (HTTPException, OSError):
                pass
        return {"status": "purged", "material_id": material_id}

    @app.patch("/api/materials/{material_id}")
    def rename_existing_material(material_id: str, request: RenameMaterialRequest) -> dict[str, object]:
        original_name = _rename_name(request.original_name)
        if original_name is None:
            raise HTTPException(status_code=400, detail="invalid_filename")
        try:
            with connect(app.state.config.database_path) as connection:
                row = rename_material(connection, material_id, original_name)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="material_update_failed") from exc
        if row is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        return dict(row)

    @app.delete("/api/materials/{material_id}", status_code=204)
    def delete_existing_material(material_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                deleted = soft_delete_material(connection, material_id)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="material_delete_failed") from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="material_not_found")
        return Response(status_code=204)

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
<style>body{font-family:system-ui,sans-serif;max-width:1060px;margin:0 auto;padding:32px;color:#17202a;background:#f6f7f9}main{background:white;border:1px solid #d8dde3;padding:24px;border-radius:8px}h1{margin-top:0}button{background:#1769aa;color:white;border:0;border-radius:4px;padding:9px 14px;cursor:pointer}input{margin:12px 0}.status{padding:12px 0;color:#52606d}.summary{display:flex;gap:16px;flex-wrap:wrap;color:#52606d}.batch-item{border-top:1px solid #e5e7eb;padding:7px 0}.layout{display:grid;grid-template-columns:320px 1fr;gap:24px;margin-top:24px}.filters{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0 12px}#search-form{display:flex;gap:6px;margin:8px 0}#search{min-width:0;flex:1;margin:0;padding:7px}#search-form button{padding:7px}.filters button{background:#e8edf2;color:#17202a;padding:6px 9px}.filters button.active{background:#1769aa;color:white}.item{display:block;width:100%;text-align:left;border:1px solid #d8dde3;background:#fff;color:#17202a;margin:6px 0}.item:hover{background:#eef5fb}#management{display:flex;gap:8px;margin:14px 0}#management button{background:#52606d}.meta{color:#52606d;font-size:14px}.search-match{display:inline-block;color:#1769aa;font-size:13px;font-weight:600;margin-top:4px}.search-snippet{display:block;color:#52606d;font-size:14px;line-height:1.45;margin-top:4px;white-space:pre-wrap;overflow-wrap:anywhere}.search-highlight{background:#fff0a8;color:inherit;border-radius:2px;padding:0 1px}.content{white-space:pre-wrap;line-height:1.6;max-height:55vh;overflow:auto;border-top:1px solid #e5e7eb;padding-top:16px}@media(max-width:700px){body{padding:12px}.layout{grid-template-columns:1fr}} </style></head>
<body><main><h1>StudyBuddy 文件导入</h1><form id="form"><input id="file" type="file" multiple required><button type="submit">导入文件</button></form><div id="status" class="status"></div><div id="summary" class="summary"></div><div id="batch-items"></div><section class="layout"><aside><h2>材料</h2><div id="views" class="filters"><button id="active-view" type="button">正常材料</button><button id="deleted-view" type="button">回收站</button></div><form id="search-form"><input id="search" type="search" placeholder="搜索材料"><button id="search-submit" type="submit">搜索</button><button id="search-clear" type="button">清除</button></form><div id="search-summary" class="meta"></div><div id="filters" class="filters"></div><div id="batch-export" class="filters"><button id="select-all" type="button">全选当前列表</button><button id="export-selected-originals" type="button">导出选中原文件</button><button id="export-selected-text" type="button">导出选中文本</button><button id="export-selected-bundle" type="button">导出选中全部</button></div><div id="materials"></div></aside><article><h2 id="title">选择材料</h2><div id="meta" class="meta"></div><div id="warnings" class="meta"></div><div id="spans" class="meta"></div><div id="management"><button id="rename" type="button">重命名</button><button id="delete" type="button">删除</button><button id="restore" type="button">恢复</button><button id="purge" type="button">永久删除</button><button id="download-original" type="button">下载原文件</button><button id="export-text" type="button">导出解析正文</button></div><div id="content" class="content"></div></article></section></main>
<script>const statusEl=document.querySelector('#status'),listEl=document.querySelector('#materials'),summaryEl=document.querySelector('#summary'),batchItemsEl=document.querySelector('#batch-items'),filterEl=document.querySelector('#filters');let currentFilter='';
let viewMode='active';let currentQuery='';let exportInFlight=false;
function textNode(tag, className, value){const node=document.createElement(tag);if(className)node.className=className;node.textContent=value;return node}
function renderMaterial(item, deleted){const button=document.createElement('button');button.className=`item${deleted?' deleted-item':''}`;button.dataset.id=item.id;if(!deleted){const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.className='material-select';checkbox.dataset.id=item.id;checkbox.addEventListener('click',event=>event.stopPropagation());button.append(checkbox,document.createTextNode(' '))}button.append(textNode('span','',item.original_name),document.createElement('br'));const meta=deleted?`已删除 · ${item.status} · ${item.deleted_at}`:`${item.status} · ${item.media_type} · ${item.text_length} 字 · ${item.span_count} spans${item.error_code?' · '+item.error_code:''}`;button.append(textNode('span','meta',meta),document.createElement('br'),textNode('span','meta',deleted?`${item.text_length} 字 · ${item.span_count} spans`:`${item.text_length} 字 · ${item.span_count} spans`));if(!deleted&&currentQuery){if(item.match_fields&&item.match_fields.length){const labels={original_name:'名称',text:'正文'};button.append(document.createElement('br'),textNode('span','search-match',`命中：${item.match_fields.map(field=>labels[field]||field).join('、')}`))}if(item.snippet){button.append(document.createElement('br'),textNode('span','search-snippet',item.snippet))}}button.onclick=()=>deleted?loadDeletedMaterial(item.id):loadMaterial(item.id);return button}
let listGeneration=0;
function activeMaterialsUrl(){return `/api/materials?${new URLSearchParams(Object.fromEntries([['status',currentFilter],['q',currentQuery]].filter(([,value])=>value)))}`}
function renderList(items,deleted){document.querySelector('#batch-export').style.display=deleted?'none':'flex';listEl.replaceChildren();if(!items.length){listEl.append(textNode('p','meta',deleted?'回收站为空':'暂无材料'))}else{items.forEach(item=>listEl.append(renderMaterial(item,deleted)))}}
async function loadList(){const generation=++listGeneration;const deleted=viewMode==='deleted';const url=deleted?'/api/materials/deleted':activeMaterialsUrl();try{const r=await fetch(url);if(!r.ok)throw new Error('list_load_failed');const items=await r.json();if(generation!==listGeneration)return null;renderList(items,deleted);document.querySelector('#search-summary').textContent=!deleted&&currentQuery?`匹配 ${items.length}`:'';return items}catch(error){if(generation!==listGeneration)return null;statusEl.textContent='材料列表加载失败';return null}}
let selectedMaterialId=null;let selectedMaterial=null;let detailGeneration=0;let mutationInFlight=false;
function selectedIds(){return [...document.querySelectorAll('.material-select:checked')].map(node=>node.dataset.id)}
function setExportBusy(busy){exportInFlight=busy;['export-selected-originals','export-selected-text','export-selected-bundle','select-all'].forEach(id=>document.querySelector('#'+id).disabled=busy||viewMode==='deleted')}
async function exportSelected(includeOriginal,includeText){if(exportInFlight||viewMode==='deleted')return;const ids=selectedIds();if(!ids.length){statusEl.textContent='请选择至少一个材料';return}setExportBusy(true);try{const r=await fetch('/api/materials/export',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({material_ids:ids,include_original:includeOriginal,include_text:includeText})});if(!r.ok){statusEl.textContent=r.status===413?'导出文件过大':'批量导出失败';return}const blob=await r.blob();const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='studybuddy-materials.zip';anchor.click();URL.revokeObjectURL(url);statusEl.textContent='批量导出完成'}catch(_){statusEl.textContent='批量导出失败'}finally{setExportBusy(false)}}
function setMutationBusy(busy){mutationInFlight=busy;document.querySelector('#rename').disabled=busy||viewMode==='deleted'||!selectedMaterialId;document.querySelector('#delete').disabled=busy||viewMode==='deleted'||!selectedMaterialId;document.querySelector('#restore').disabled=busy||viewMode!=='deleted'||!selectedMaterialId;document.querySelector('#purge').disabled=busy||viewMode!=='deleted'||!selectedMaterialId;document.querySelector('#download-original').disabled=busy||viewMode!=='active'||!selectedMaterialId;document.querySelector('#export-text').disabled=busy||viewMode!=='active'||!selectedMaterialId;}
function clearMaterial(){detailGeneration++;selectedMaterialId=null;selectedMaterial=null;document.querySelector('#title').textContent='选择材料';document.querySelector('#meta').textContent='';document.querySelector('#warnings').textContent='';document.querySelector('#spans').textContent='';document.querySelector('#content').textContent='';document.querySelector('#rename').disabled=true;document.querySelector('#delete').disabled=true;document.querySelector('#restore').disabled=true;document.querySelector('#purge').disabled=true;document.querySelector('#download-original').disabled=true;document.querySelector('#export-text').disabled=true;}
function queryTokens(){return currentQuery.trim().split(/\\s+/).filter(Boolean)}
function firstTextMatch(text,tokens){const lowered=text.toLocaleLowerCase();let found=null;for(const token of tokens){const start=lowered.indexOf(token.toLocaleLowerCase());if(start>=0&&(!found||start<found.start))found={start,end:start+token.length,token:text.slice(start,start+token.length)}}return found}
function renderDetailContent(text){const content=document.querySelector('#content');content.replaceChildren();const match=viewMode==='active'&&currentQuery?firstTextMatch(text,queryTokens()):null;if(!match){content.append(document.createTextNode(text));return null}content.append(document.createTextNode(text.slice(0,match.start)));const mark=document.createElement('mark');mark.className='search-highlight';mark.textContent=match.token;content.append(mark,document.createTextNode(text.slice(match.end)));requestAnimationFrame(()=>mark.scrollIntoView({block:'center',inline:'nearest'}));return match}
function searchContext(name,text){if(viewMode!=='active'||!currentQuery)return '';const tokens=queryTokens();const nameMatch=tokens.some(token=>name.toLocaleLowerCase().includes(token.toLocaleLowerCase()));const textMatch=tokens.some(token=>text.toLocaleLowerCase().includes(token.toLocaleLowerCase()));const fields=[];if(nameMatch)fields.push('名称');if(textMatch)fields.push('正文');return fields.length?`搜索命中：${fields.join('、')}`:''}
async function loadMaterial(id){const generation=++detailGeneration;const r=await fetch('/api/materials/'+id);if(generation!==detailGeneration)return;if(!r.ok){statusEl.textContent='材料不可用';clearMaterial();return}const x=await r.json();if(generation!==detailGeneration)return;selectedMaterialId=id;selectedMaterial=x;document.querySelector('#rename').disabled=mutationInFlight;document.querySelector('#delete').disabled=mutationInFlight;document.querySelector('#restore').disabled=true;document.querySelector('#download-original').disabled=mutationInFlight;document.querySelector('#export-text').disabled=mutationInFlight;document.querySelector('#title').textContent=x.original_name;const context=searchContext(x.original_name,x.text||'');document.querySelector('#meta').textContent=`${x.status} · ${x.parser_id} ${x.parser_version} · SHA-256 ${x.source_sha256}${context?' · '+context:''}`;document.querySelector('#warnings').textContent=x.error_code?`error_code: ${x.error_code} · ${x.warnings.join(' ')}`:x.warnings.join(' ');document.querySelector('#spans').textContent=`spans: ${x.spans.length} · ${x.spans.map(s=>s.label).join(', ')}`;const displayText=x.text||x.spans.filter(s=>s.text.trim()).map(s=>`[${s.label}]\\n${s.text}`).join('\\n\\n')||'没有可显示的正文';renderDetailContent(displayText);}
async function loadDeletedMaterial(id){const generation=++detailGeneration;const r=await fetch('/api/materials/deleted');const items=await r.json();if(generation!==detailGeneration)return;const x=items.find(item=>item.id===id);if(!x){statusEl.textContent='材料不可用';clearMaterial();return}selectedMaterialId=id;selectedMaterial=x;document.querySelector('#rename').disabled=true;document.querySelector('#delete').disabled=true;document.querySelector('#restore').disabled=mutationInFlight;document.querySelector('#purge').disabled=mutationInFlight;document.querySelector('#download-original').disabled=true;document.querySelector('#export-text').disabled=true;document.querySelector('#title').textContent=x.original_name;document.querySelector('#meta').textContent=`已删除 · ${x.status} · 删除于 ${x.deleted_at}`;document.querySelector('#warnings').textContent=x.error_code?`error_code: ${x.error_code}`:'';document.querySelector('#spans').textContent=`spans: ${x.span_count}`;document.querySelector('#content').replaceChildren();}
async function purgeSelected(){if(!selectedMaterialId||viewMode!=='deleted'||mutationInFlight)return;if(!window.confirm(`永久删除后不可恢复，且原文件可能被删除。确认永久删除“${selectedMaterial.original_name}”？`))return;const id=selectedMaterialId;mutationInFlight=true;listGeneration++;detailGeneration++;setMutationBusy(true);try{const r=await fetch('/api/materials/'+id+'/purge',{method:'POST'});if(!r.ok){statusEl.textContent='永久删除失败';return}statusEl.textContent='材料已永久删除';clearMaterial();await loadList()}catch(_){statusEl.textContent='永久删除失败'}finally{mutationInFlight=false;setMutationBusy(false)}}
async function restoreSelected(){if(!selectedMaterialId||mutationInFlight)return;const id=selectedMaterialId;mutationInFlight=true;listGeneration++;detailGeneration++;setMutationBusy(true);try{const r=await fetch('/api/materials/'+id+'/restore',{method:'POST'});const x=await r.json();if(!r.ok){statusEl.textContent='恢复失败';return}statusEl.textContent='材料已恢复';clearMaterial();await setView('active');await loadMaterial(x.id)}catch(_){statusEl.textContent='恢复失败'}finally{mutationInFlight=false;setMutationBusy(false)}}
function downloadOriginal(){if(selectedMaterialId&&viewMode==='active')window.location.href='/api/materials/'+selectedMaterialId+'/original'}
function exportText(){if(selectedMaterialId&&viewMode==='active')window.location.href='/api/materials/'+selectedMaterialId+'/text'}
async function renameSelected(){if(!selectedMaterialId||viewMode==='deleted'||mutationInFlight)return;const name=window.prompt('输入新的材料名称',selectedMaterial.original_name);if(name===null)return;const id=selectedMaterialId;mutationInFlight=true;listGeneration++;detailGeneration++;setMutationBusy(true);try{const r=await fetch('/api/materials/'+id,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({original_name:name})});const x=await r.json();if(!r.ok){statusEl.textContent='重命名失败';return}statusEl.textContent='重命名成功';await loadList();await loadMaterial(id)}catch(_){statusEl.textContent='重命名失败'}finally{mutationInFlight=false;setMutationBusy(false)}}
async function deleteSelected(){if(!selectedMaterialId||viewMode==='deleted'||mutationInFlight)return;if(!window.confirm(`确认删除材料“${selectedMaterial.original_name}”？`))return;const id=selectedMaterialId;mutationInFlight=true;listGeneration++;detailGeneration++;setMutationBusy(true);try{const r=await fetch('/api/materials/'+id,{method:'DELETE'});if(!r.ok){await r.json();statusEl.textContent='删除失败';return}statusEl.textContent='材料已删除';clearMaterial();await loadList()}catch(_){statusEl.textContent='删除失败'}finally{mutationInFlight=false;setMutationBusy(false)}}
async function submitSearch(){if(viewMode==='deleted')return;currentQuery=document.querySelector('#search').value.trim();await loadList()}
function setView(mode){viewMode=mode;document.querySelector('#active-view').classList.toggle('active',mode==='active');document.querySelector('#deleted-view').classList.toggle('active',mode==='deleted');filterEl.style.display=mode==='active'?'flex':'none';document.querySelector('#search-form').style.display=mode==='active'?'flex':'none';if(mode==='deleted'){currentQuery='';document.querySelector('#search').value='';document.querySelector('#search-summary').textContent=''}clearMaterial();return loadList()}
document.querySelector('#select-all').onclick=()=>{const boxes=[...document.querySelectorAll('.material-select')];const checked=boxes.every(box=>box.checked);boxes.forEach(box=>box.checked=!checked)};document.querySelector('#export-selected-originals').onclick=()=>exportSelected(true,false);document.querySelector('#export-selected-text').onclick=()=>exportSelected(false,true);document.querySelector('#export-selected-bundle').onclick=()=>exportSelected(true,true);document.querySelector('#rename').onclick=renameSelected;document.querySelector('#delete').onclick=deleteSelected;document.querySelector('#restore').onclick=restoreSelected;document.querySelector('#purge').onclick=purgeSelected;document.querySelector('#download-original').onclick=downloadOriginal;document.querySelector('#export-text').onclick=exportText;document.querySelector('#search-form').onsubmit=async event=>{event.preventDefault();await submitSearch()};document.querySelector('#search-clear').onclick=async()=>{document.querySelector('#search').value='';currentQuery='';await loadList()};document.querySelector('#active-view').onclick=()=>setView('active');document.querySelector('#deleted-view').onclick=()=>setView('deleted');clearMaterial();
function filters(){const labels=['全部','成功','空文件','拒绝','失败'];const statuses=['','success','empty','rejected','failed'];filterEl.replaceChildren();labels.forEach((label,i)=>{const button=document.createElement('button');button.textContent=label;button.dataset.status=statuses[i];button.classList.toggle('active',statuses[i]===currentFilter);button.onclick=async()=>{currentFilter=button.dataset.status;filters();await submitSearch()};filterEl.append(button)})}
document.querySelector('#form').onsubmit=async e=>{e.preventDefault();const files=[...document.querySelector('#file').files];if(!files.length)return;statusEl.textContent=`正在导入 ${files.length} 个文件`;const body=new FormData();if(files.length===1){body.append('file',files[0])}else{files.forEach(file=>body.append('files',file))}const r=await fetch(files.length===1?'/api/materials':'/api/materials/batch',{method:'POST',body});const x=await r.json();if(!r.ok){statusEl.textContent=typeof x.detail==='string'?x.detail:JSON.stringify(x.detail);return}if(files.length===1){statusEl.textContent=`导入完成：${x.status}，${x.text_length} 字符`;summaryEl.textContent='';batchItemsEl.innerHTML='';await loadList();if(x.material_id)await loadMaterial(x.material_id);return}statusEl.textContent=`批量导入完成：${x.total} 个文件`;summaryEl.textContent=`总数 ${x.total} · 成功 ${x.success} · 空文件 ${x.empty} · 拒绝 ${x.rejected} · 失败 ${x.failed}`;batchItemsEl.replaceChildren();x.items.forEach(item=>{const row=document.createElement('div');row.className='batch-item';const parts=[item.original_name,item.status];if(item.error_code)parts.push(item.error_code);if(item.warnings.length)parts.push(item.warnings.join(' '));row.textContent=parts.join(' · ');batchItemsEl.append(row)});await loadList();const first=x.items.find(item=>item.material_id);if(first)await loadMaterial(first.material_id)};filters();loadList();</script></body></html>"""

app = create_app()

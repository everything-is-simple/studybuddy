from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    def pagination_values(limit: str | None, offset: str | None) -> tuple[int, int, bool]:
        paged = limit is not None or offset is not None
        try:
            page_limit = 20 if limit is None else int(limit)
            page_offset = 0 if offset is None else int(offset)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_pagination") from exc
        if page_limit < 1 or page_limit > 100 or page_offset < 0:
            raise HTTPException(status_code=400, detail="invalid_pagination")
        return page_limit, page_offset, paged

    @app.get("/api/materials")
    def materials(status: str | None = None, q: str | None = None, limit: str | None = None, offset: str | None = None) -> list[dict[str, object]] | dict[str, object]:
        if status is not None and status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="invalid_status")
        page_limit, page_offset, paged = pagination_values(limit, offset)
        with connect(app.state.config.database_path) as connection:
            if paged:
                items, total = list_materials_page(connection, status, q, page_limit, page_offset)
                return {"items": [dict(row) for row in items], "total": total, "limit": page_limit, "offset": page_offset, "has_more": page_offset + len(items) < total}
            return [dict(row) for row in list_materials(connection, status, q)]

    @app.get("/api/materials/deleted")
    def deleted_materials(limit: str | None = None, offset: str | None = None) -> list[dict[str, object]] | dict[str, object]:
        page_limit, page_offset, paged = pagination_values(limit, offset)
        with connect(app.state.config.database_path) as connection:
            if paged:
                items, total = list_deleted_materials_page(connection, page_limit, page_offset)
                return {"items": [dict(row) for row in items], "total": total, "limit": page_limit, "offset": page_offset, "has_more": page_offset + len(items) < total}
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

    globals()['pagination_values'] = pagination_values
    context.update({'pagination_values': pagination_values})
    return context

from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
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
            payload.pop("stored_path", None)
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
        payload = dict(row)
        payload.pop("stored_path", None)
        return payload

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
        lock = acquire_hash_lock(source_sha256)
        try:
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
        finally:
            release_hash_lock(source_sha256, lock)
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
        payload = dict(row)
        payload.pop("stored_path", None)
        return payload

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
        result = await _process_file(file, app.state.config, batch=False)
        record_import(str(result.get("status", "failed")))
        return result

    @app.post("/api/materials/batch", status_code=201)
    async def upload_materials(files: Annotated[list[UploadFile], File(...)]) -> dict[str, object]:
        items = [await _process_file(file, app.state.config, batch=True) for file in files]
        for item in items:
            record_import(str(item.get("status", "failed")))
        counts = {status: sum(item["status"] == status for item in items)
                  for status in ("success", "empty", "rejected", "failed")}
        return {"batch_id": f"batch_{uuid.uuid4().hex}", "total": len(items), **counts, "items": items}
    return context

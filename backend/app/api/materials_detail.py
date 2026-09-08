"""材料详情与文件操作 API。

提供单个材料的详细信息查询、文件下载和上传功能。

主要端点：
- GET /api/materials/{material_id}/original - 下载原始文件
- GET /api/materials/{material_id}/text - 导出提取的文本
- GET /api/materials/{material_id} - 查询材料详情
- DELETE /api/materials/{material_id}/purge - 物理删除材料
- POST /api/materials - 上传单个材料
- POST /api/materials/batch - 批量上传材料

关联模块：
- repositories.materials - 材料数据访问
- adapters.file_parsers - 文件解析器
- backend.app.storage - 文件存储管理

注意：
- 文件上传限制：单文件最大 100MB
- 支持的格式：PDF, DOCX, TXT, MD, PPTX
- DELETE purge 是物理删除，不可恢复
"""

from __future__ import annotations

import json


def register_routes(app, context: dict[str, object]) -> None:
    """注册材料详情和文件操作相关路由。
    
    Args:
        app: FastAPI 应用实例
        context: 路由上下文字典（包含共享的辅助函数和常量）
        
    Returns:
        更新后的上下文字典（本模块未添加新的上下文项）
    """
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    
    @app.get("/api/materials/{material_id}/original")
    def download_original(material_id: str):
        """下载材料的原始文件。
        
        Args:
            material_id: 材料 ID
            
        Returns:
            FileResponse: 原始文件的二进制流
            - Content-Type: 文件的 MIME 类型
            - Content-Disposition: attachment; filename="原始文件名"
            
        Raises:
            HTTPException(404): material_not_found - 材料不存在
            HTTPException(404): source_deleted - 文件已被物理删除
            HTTPException(500): file_read_failed - 文件读取失败
        """
        config = app.state.config
        with connect(config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            target = _checked_original_path(config, row["stored_path"], row["source_sha256"])
            return FileResponse(target, media_type=row["media_type"], filename=_download_name(row["original_name"]))

    @app.get("/api/materials/{material_id}/text")
    def export_text(material_id: str):
        """导出材料提取的文本内容（UTF-8 纯文本）。
        
        Args:
            material_id: 材料 ID
            
        Returns:
            Response: UTF-8 编码的纯文本
            - Content-Type: text/plain; charset=utf-8
            - Content-Disposition: attachment; filename="原始文件名.extracted.txt"
            
        Raises:
            HTTPException(404): material_not_found - 材料不存在
            HTTPException(404): extraction_not_found - 文本提取记录不存在
            HTTPException(500): text_export_failed - 文本导出失败
        """
        config = app.state.config
        with connect(config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            extraction = connection.execute(
                "SELECT text FROM extractions WHERE material_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (material_id,),
            ).fetchone()
            headers = {"Content-Disposition": f'attachment; filename="{_download_name(row["original_name"], ".extracted.txt")}"'}
            return Response(content=row["text"], media_type="text/plain", headers=headers)

    @app.get("/api/materials/{material_id}")
    def material_detail(material_id: str) -> dict[str, object]:
        """查询材料的详细信息。
        
        Args:
            material_id: 材料 ID
            
        Returns:
            材料详情字典（get_material 行 + warnings 解析 + spans 列表；
            不含 stored_path）
            
        Raises:
            HTTPException(404): material_not_found - 材料不存在
            HTTPException(500): material_detail_failed - 查询失败
        """
        with connect(app.state.config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            payload = dict(row)
            payload.pop("stored_path", None)
            payload["warnings"] = json.loads(payload.pop("warnings_json") or "[]")
            payload["spans"] = [dict(span) for span in get_spans(connection, row["extraction_id"])]
            return payload

    @app.post("/api/materials/{material_id}/purge")
    def purge_existing_material(material_id: str) -> dict[str, object]:
        """物理删除材料及其关联的文件。
        
        此操作会：
        1. 通过 repository 层级联删除数据库中的材料记录及所有关联数据
           （分块/嵌入/搜索索引/QA 引用标记 source_unavailable）
        2. 如果没有其他材料引用相同的文件（通过 SHA256 判断），则删除物理文件
        
        Args:
            material_id: 材料 ID
            
        Returns:
            {"status": "purged", "material_id": str}
            
        Raises:
            HTTPException(404): material_not_found - 材料不存在
            HTTPException(500): material_purge_failed - 删除失败
            
        Warning:
            这是不可逆操作！删除后无法恢复。
            建议在删除前先调用 DELETE /api/materials/{id} 进行软删除，
            确认无误后再调用此端点进行物理删除。
        """
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
        """重命名材料（仅改显示名，不改变内容身份）。
        
        Args:
            material_id: 材料 ID
            request: 重命名请求（original_name 为新文件名）
            
        Returns:
            更新后的材料字典（不含 stored_path）
            
        Raises:
            HTTPException(400): invalid_filename - 文件名非法
            HTTPException(404): material_not_found - 材料不存在
            HTTPException(500): material_update_failed - 数据库更新失败
            
        Side Effects:
            - 更新 materials 表的 original_name 和 updated_at
            - 内容哈希和存储键不变
        """
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

    @app.post("/api/materials", status_code=201)
    async def upload_material(file: Annotated[UploadFile, File(...)]) -> dict[str, object]:
        """上传单个材料文件。
        
        Args:
            file: 上传的文件（multipart/form-data）
                  - 最大大小：100MB
                  - 支持格式：PDF, DOCX, TXT, MD, PPTX
                  
        Returns:
            上传结果字典：
            {
                "status": "success" | "empty" | "rejected" | "failed",
                "material_id": str | None,
                "original_name": str,
                "error_code": str | None,
                "created_at": str | None
            }
            
        Raises:
            HTTPException(400): 
                - file_empty - 文件为空
                - file_too_large - 文件超过 100MB
                - unsupported_file_type - 不支持的文件格式
            HTTPException(500): material_upload_failed - 上传处理失败
            
        Note:
            - 上传成功后会自动触发文本提取
            - 文件通过 SHA256 去重，相同内容的文件只存储一次
            - 返回 status="success" 表示上传成功，但文本提取可能失败
        """
        result = await _process_file(file, app.state.config, batch=False)
        record_import(str(result.get("status", "failed")))
        return result

    @app.post("/api/materials/batch", status_code=201)
    async def upload_materials(files: Annotated[list[UploadFile], File(...)]) -> dict[str, object]:
        """批量上传多个材料文件。
        
        Args:
            files: 上传的文件列表（multipart/form-data）
                   - 每个文件最大 100MB
                   - 建议单次上传不超过 10 个文件
                   
        Returns:
            批量上传结果字典：
            {
                "batch_id": str,
                "total": int,
                "success": int,
                "empty": int,
                "rejected": int,
                "failed": int,
                "items": [
                    {
                        "status": "success" | "empty" | "rejected" | "failed",
                        "material_id": str | None,
                        "original_name": str,
                        "error_code": str | None,
                        "created_at": str | None
                    },
                    ...
                ]
            }
            
        Raises:
            HTTPException(400): 文件列表为空或参数无效
            HTTPException(500): material_batch_upload_failed - 批量上传失败
            
        Note:
            - 批量上传是串行处理的（一个接一个）
            - 单个文件失败不会影响其他文件的处理
            - 返回的 items 顺序与上传顺序一致
            - success/empty/rejected/failed 计数总和等于 total
        """
        items = [await _process_file(file, app.state.config, batch=True) for file in files]
        for item in items:
            record_import(str(item.get("status", "failed")))
        counts = {status: sum(item["status"] == status for item in items)
                  for status in ("success", "empty", "rejected", "failed")}
        return {"batch_id": f"batch_{uuid.uuid4().hex}", "total": len(items), **counts, "items": items}
    return context

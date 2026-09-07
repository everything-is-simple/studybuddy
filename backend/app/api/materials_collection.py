"""材料集合管理 API。

提供材料的列表查询、搜索、删除和批量导出功能。材料是 StudyBuddy 的核心资源，
所有学习活动都基于上传的材料展开。

主要端点：
- GET /api/materials - 查询材料列表（支持搜索、过滤、分页）
- DELETE /api/materials/{material_id} - 软删除材料
- POST /api/materials/{material_id}/restore - 恢复已删除材料
- POST /api/materials/export - 批量导出材料为 ZIP

关联模块：
- repositories.materials - 材料数据访问层
- backend.app.storage - 文件存储管理

注意：
- 删除操作是软删除（标记 deleted_at），不会立即删除文件
- 搜索功能支持文件名模糊匹配（SQL LIKE）
- 导出功能限制单次最多 200 个材料，总大小不超过 256MB
"""

from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    """注册材料集合管理相关路由。
    
    Args:
        app: FastAPI 应用实例
        context: 路由上下文字典（包含共享的辅助函数和常量）
        
    Returns:
        更新后的上下文字典（添加 pagination_values 辅助函数供其他模块使用）
    """
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    
    def pagination_values(limit: str | None, offset: str | None) -> tuple[int, int, bool]:
        """解析并验证分页参数。
        
        Args:
            limit: 可选的分页限制（字符串形式的整数，如 "20"）
            offset: 可选的分页偏移量（字符串形式的整数，如 "0"）
            
        Returns:
            元组 (page_limit, page_offset, paged)：
            - page_limit: 解析后的限制数（1-100，默认 20）
            - page_offset: 解析后的偏移量（>=0，默认 0）
            - paged: 是否启用了分页（limit 或 offset 有一个非 None）
            
        Raises:
            HTTPException(400): invalid_pagination - 参数格式错误或超出范围
        """
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
        """查询材料列表（支持搜索、过滤和分页）。
        
        返回当前项目的材料列表。支持按状态过滤、按文件名搜索和分页。
        如果提供了分页参数，返回结构包含元数据；否则返回完整列表。
        
        Args:
            status: 可选的状态过滤（"active"|"deleted"，默认 "active"）
            q: 可选的搜索关键词（匹配文件名，SQL LIKE 模糊搜索）
            limit: 可选的分页限制（1-100，默认 20）
            offset: 可选的分页偏移量（>=0，默认 0）
            
        Returns:
            如果未启用分页，返回材料列表：
            [
                {
                    "id": str,
                    "original_name": str,
                    "media_type": str,
                    "file_size_bytes": int,
                    "created_at": str (ISO 8601),
                    "deleted_at": str | None
                },
                ...
            ]
            
            如果启用分页，返回带元数据的字典：
            {
                "materials": [...同上结构],
                "total": int,
                "limit": int,
                "offset": int,
                "has_more": bool
            }
            
        Raises:
            HTTPException(400): invalid_status - status 参数不是 "active" 或 "deleted"
            HTTPException(400): invalid_pagination - 分页参数格式错误或超出范围
            HTTPException(500): materials_list_failed - 数据库查询失败
        """
        page_limit, page_offset, paged = pagination_values(limit, offset)
        query_status = "active" if status is None else status
        if query_status not in {"active", "deleted"}:
            raise HTTPException(status_code=400, detail="invalid_status")
        query = q if q else None
        try:
            with connect(app.state.config.database_path) as connection:
                if paged:
                    from ..repository import list_materials_paged
                    result = list_materials_paged(connection, project_id=app.state.config.project_id,
                                                status=query_status, query=query, limit=page_limit, offset=page_offset)
                    return result
                else:
                    from ..repository import list_materials
                    items = list_materials(connection, project_id=app.state.config.project_id,
                                         status=query_status, query=query)
                    return items
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=400, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="materials_list_failed") from None

    @app.delete("/api/materials/{material_id}")
    def delete_material(material_id: str) -> dict[str, object]:
        """软删除指定材料。
        
        将材料标记为已删除（设置 deleted_at 时间戳），但不立即删除文件系统文件。
        已删除的材料可以通过 restore 端点恢复。
        
        Args:
            material_id: 材料唯一标识符
            
        Returns:
            包含删除结果的字典：
            {
                "id": str,
                "deleted_at": str (ISO 8601),
                "original_name": str
            }
            
        Raises:
            HTTPException(404): material_not_found - 材料不存在
            HTTPException(404): material_already_deleted - 材料已被删除
            HTTPException(500): material_delete_failed - 数据库更新失败
            
        Side Effects:
            - 更新 materials 表的 deleted_at 字段
            - 相关联的索引、嵌入、问答等数据仍保留
            - 文件系统中的文件未删除（需要后续清理任务）
            
        Note:
            硬删除（物理删除文件）需要运行后台清理任务，不在 API 范围内。
        """
        try:
            with connect(app.state.config.database_path) as connection:
                from ..repository import delete_material as delete_material_repo
                result = delete_material_repo(connection, material_id=material_id,
                                            project_id=app.state.config.project_id)
        except ValueError as error:
            code = str(error)
            status_code = 404 if code in {"material_not_found", "material_already_deleted"} else 400
            raise HTTPException(status_code=status_code, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="material_delete_failed") from None
        return result

    @app.post("/api/materials/{material_id}/restore")
    def restore_material(material_id: str) -> dict[str, object]:
        """恢复已删除的材料。
        
        清除材料的 deleted_at 标记，使其重新成为可用的活跃材料。
        
        Args:
            material_id: 材料唯一标识符
            
        Returns:
            包含恢复结果的字典：
            {
                "id": str,
                "deleted_at": None,
                "original_name": str,
                "restored_at": str (ISO 8601)
            }
            
        Raises:
            HTTPException(404): material_not_found - 材料不存在
            HTTPException(404): material_not_deleted - 材料未被删除，无需恢复
            HTTPException(500): material_restore_failed - 数据库更新失败
            
        Side Effects:
            - 清除 materials 表的 deleted_at 字段（设为 NULL）
            - 材料重新出现在活跃材料列表中
        """
        try:
            with connect(app.state.config.database_path) as connection:
                from ..repository import restore_material as restore_material_repo
                result = restore_material_repo(connection, material_id=material_id,
                                             project_id=app.state.config.project_id)
        except ValueError as error:
            code = str(error)
            status_code = 404 if code in {"material_not_found", "material_not_deleted"} else 400
            raise HTTPException(status_code=status_code, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="material_restore_failed") from None
        return result

    @app.post("/api/materials/export")
    def export_materials(request: ExportMaterialsRequest):
        """批量导出材料为 ZIP 压缩包。
        
        将多个材料及其提取的文本内容打包为一个 ZIP 文件供下载。
        支持选择性导出原始文件和/或提取的文本。
        
        Args:
            request: 导出请求体，包含：
                material_ids: list[str] - 要导出的材料 ID 列表（1-200 个，不能重复）
                include_original: bool - 是否包含原始文件
                include_text: bool - 是否包含提取的文本（.extracted.txt）
                
        Returns:
            ZIP 文件响应（application/zip）：
            Content-Disposition: attachment; filename="studybuddy-materials.zip"
            
        Raises:
            HTTPException(400): invalid_export_request - 请求参数无效：
                - material_ids 为空或超过 200 个
                - material_ids 包含重复
                - include_original 和 include_text 都为 false
            HTTPException(404): material_not_found - 某些材料不存在
            HTTPException(404): source_deleted - 某些材料已被删除
            HTTPException(413): export_too_large - 导出内容超过 256MB
            HTTPException(500): material_export_failed - 文件打包失败
            
        ZIP 结构：
            studybuddy-materials.zip
            ├── originals/
            │   ├── document1.pdf
            │   ├── document2.docx
            │   └── ...
            └── text/
                ├── document1.extracted.txt
                ├── document2.extracted.txt
                └── ...
                
        Note:
            - 单次导出限制：最多 200 个材料，总大小不超过 256MB
            - 文件名冲突时自动添加数字后缀（如 file.pdf, file(1).pdf）
            - 已删除的材料（deleted_at 非空）不会被导出
        """
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
        try:
            import io
            import zipfile
            from pathlib import Path
            buffer = io.BytesIO()
            logical_size = 0
            seen_original = {}
            seen_text = {}
            def unique_entry(prefix: str, name: str) -> str:
                seen = seen_original if prefix == "originals" else seen_text
                if name not in seen:
                    seen[name] = 0
                    return f"{prefix}/{name}"
                seen[name] += 1
                stem = Path(name).stem
                suffix = Path(name).suffix
                return f"{prefix}/{stem}({seen[name]}){suffix}"
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for row in rows:
                    name = row["original_name"]
                    if request.include_original:
                        stored_path = Path(app.state.config.data_root) / row["stored_path"]
                        if not stored_path.is_file():
                            raise HTTPException(status_code=404, detail="source_deleted")
                        data = stored_path.read_bytes()
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

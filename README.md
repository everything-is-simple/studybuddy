# StudyBuddy

个人学习系统主目录。

远端仓库：`https://github.com/everything-is-simple/studybuddy.git`

本目录只存正式产品源码、正式测试和必要文档。组件必须先在 `H:\studybuddy-composer` 完成独立测试，再在 `H:\studybuddy-integration` 完成组合测试，最后由主系统重新实现或装配。不得从参考项目直接复制源码作为正式实现。

## 当前正式实现

正式文件解析 Adapter 位于 `backend/app/adapters/file_parsers/`，依据已通过的 Composer smoke 和 Integration 契约独立重实现。当前覆盖 TXT、Markdown、PDF、DOCX、PPTX；RTF、旧 DOC、旧 PPT 明确拒绝。Adapter 返回 SHA-256、版本、状态、结构化 page/slide span、warning、错误码和耗时，并执行文件大小与 ZIP/XML 容器资源限制。

默认单文件上传上限为 50 MiB，可通过 `STUDYBUDDY_MAX_UPLOAD_BYTES` 调整；这不是免费版或解析组件的硬限制。ZIP/XML 容器仍执行 member 数量、解压总量和压缩比限制。`backend/app/storage.py` 提供最小原文件保存边界，`backend/app/repository.py` 提供最小 SQLite extraction/span 事务边界。`backend/app/main.py` 现在提供最小 FastAPI multipart 上传、材料查询和静态文件选择器页面：上传文件会保存原文件、调用 Parser、在同一 SQLite 事务写入 extraction/spans，并可在服务重启后通过 API 回读。

正式文件导入基础链路已达到局部 `real-pass`，最终证据位于 `H:\studybuddy-test\artifacts\formal-file-import-final\latest.json`。真实 Chromium 已覆盖 TXT/Markdown/中文 TXT、合法空文件、PDF、DOCX、PPTX、损坏容器、RTF/旧 DOC/旧 PPT rejection；50 MiB 边界、重复 hash、原文件清理、刷新回读和服务重启回读均已通过。

多文件导入与材料列表基础能力已实现：`POST /api/materials/batch` 接受多个 `files`，每个文件独立解析、保存和 SQLite 事务，允许 batch 部分成功；单文件超限仍返回 HTTP 413，batch 中超限文件返回 item-level `rejected/file_too_large`。`GET /api/materials?status=success|empty|rejected|failed` 只返回列表元数据，不返回正文；详情接口回读正文和 spans。页面支持真实多文件选择、批量摘要、逐文件结果、列表筛选、详情查看及刷新/重启回读。当前 `formal-multi-file-import = real-pass`，最终证据位于 `H:\studybuddy-test\artifacts\formal-multi-file-import\latest.json`。

材料管理基础能力已达到局部 `real-pass`：`PATCH /api/materials/{material_id}` 只修改展示名称和 `updated_at`，不改变 source hash、stored path 或解析结果；`DELETE /api/materials/{material_id}` 使用 `deleted_at` 逻辑删除，默认列表隐藏、详情返回 404，但保留 extraction、text_spans 和 hash 派生原文件。同 hash 的其他 material 不受影响。

材料回收站与恢复已达到局部 `real-pass`：`GET /api/materials/deleted` 只返回已删除材料元数据，`POST /api/materials/{material_id}/restore` 只清空 `deleted_at` 并更新 `updated_at`，不重新解析、不创建 original/material/extraction/span。页面支持正常材料与回收站切换、真实恢复和刷新/重启回读。

材料导出已达到局部 `real-pass`：`GET /api/materials/{material_id}/original` 只允许 active material，使用数据库 stored_path，经 originals_root 路径边界和 SHA-256 校验后下载当前展示文件名的 immutable original；`GET /api/materials/{material_id}/text` 从 extraction.text 导出 UTF-8 的 `<original_name>.extracted.txt`，不重新解析。rename 后只改变下载文件名，不改变内容。deleted material 恢复前两个导出接口均返回 404，恢复后重新可用。

材料搜索已达到局部 `real-pass`：`GET /api/materials?q=<query>` 搜索 active material 的展示名称和 extraction.text，可与 `status` 组合。ASCII token 使用 SQLite FTS5 的安全 AND 候选查询，中文或特殊 token 使用参数化 substring fallback；所有结果重新按 active source tables 过滤，返回元数据、match_fields 和最多 160 个字符的纯文本 snippet，不返回完整正文或 stored_path。浏览器搜索结果现在以安全的纯文本 DOM 节点显示命中字段和 snippet；进入 active 详情后会定位并标示首个正文命中，名称-only 命中不会伪造正文高亮；页面动态内容（批量文件名、warning、error_code、筛选按钮）统一使用安全 DOM 文本节点渲染；搜索计数和列表共用一次 API 响应；请求代数保护快速搜索、筛选和清除操作，已通过真实 Chromium 验证过期响应和过期错误不会覆盖新状态；非搜索及回收站列表不显示搜索上下文。rename 同事务更新索引，delete/restore 通过 active lifecycle filter 控制可见性。本阶段不支持语义/向量/AI 搜索、搜索历史或 saved search。

这不代表整个 StudyBuddy 已 real-pass。当前没有文件夹导入、后台任务队列、OCR、转换器、真实 provider 或 S1-S7 业务实现；崩溃恢复、磁盘满、网络盘和长时间压力测试仍暂缓。

测试使用 `H:\studybuddy-test` 下的合成 fixture、runs 和脱敏 artifact，不写入本目录运行数据库或原文件副本。

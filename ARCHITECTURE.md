# StudyBuddy Architecture Boundary

## Runtime target

`127.0.0.1` 本机 Web 应用：React/Vite 前端 + FastAPI 后端 + SQLite + 本地文件。AI 通过当前选中的单一 OpenAI-compatible provider 直接请求。不引入 pi、Electron、自动 fallback 或多进程 AgentSession。

## Evidence flow

参考系统/组件 -> `H:\studybuddy-composer` 独立 smoke -> `H:\studybuddy-integration` 组合测试 -> `H:\studybuddy` 正式 Adapter 与用户路径。

系统测试运行根统一位于 `H:\studybuddy-test`。任何目录的测试通过，都不能替代下一层真实测试。

## Formal file foundation

`backend/app/adapters/file_parsers/` 是正式系统自己的解析模块，不导入 Composer、Integration 或 KaoBuddy。`parse_file(Path, declared_media_type, ParseOptions)` 返回版本、hash、状态、错误码、warning 和 document/page/slide spans。当前只实现 TXT、Markdown、PDF、DOCX、PPTX；RTF、旧 DOC、旧 PPT 拒绝。Parser 不保存原文件、不依赖网络、不打印完整正文。

`backend/app/storage.py` 通过配置传入的 root 保存 hash 派生路径下的原文件，并使用临时文件加原子替换。`backend/app/repository.py` 只承载 projects/materials/extractions/text_spans 最小 schema，启用外键和 WAL，extraction 与 spans 在同一事务中写入。

正式默认运行路径不指向 fixture；本阶段测试使用 `H:\studybuddy-test\runs`。`backend/app/main.py` 提供最小 FastAPI 用户路径：multipart 文件选择与上传、配置存储根下的原文件保存、Parser 调用、SQLite extraction/span 事务写入、材料列表/详情 API 和同服务的文件选择器页面。默认单文件上传上限为 50 MiB，可由 `STUDYBUDDY_MAX_UPLOAD_BYTES` 调整；这属于正式系统配置，不是免费版或 Parser 能力限制。服务重新启动后，材料详情从 SQLite 回读。

正式文件导入基础链路已通过 Chromium 真实选择文件、上传、页面展示、完整 fixture 失败矩阵、50 MiB 边界、重复 hash、刷新回读和服务重启后页面回读；浏览器 console error 为 0，可标记为局部 `real-pass`。这只表示文件导入基础链路，不代表整个 StudyBuddy。

多文件基础能力新增 `POST /api/materials/batch`。batch 中每个文件复用同一单文件处理边界，但拥有独立临时文件、原文件 hash 复用和 material/extraction/spans 事务；一个文件失败不阻断其他文件。单文件超限保持 HTTP 413，批量超限是 item-level rejected；列表 API 支持四种 status 筛选且不带 extraction text，详情 API 才返回正文和 spans。页面真实支持 multiple file input、批量结果、材料筛选、详情及刷新/重启回读。当前状态为 `formal-multi-file-import = real-pass`，最终证据位于 `H:\studybuddy-test\artifacts\formal-multi-file-import\latest.json`。

材料管理使用 active material 语义：rename 只更新 `materials.original_name/updated_at`；delete 只设置 `materials.deleted_at`，不物理删除 hash 派生 original，不删除 extraction 或 text_spans。列表和详情默认只读取 `deleted_at IS NULL`，deleted detail 返回 404；同 hash material 删除一个时，其他 material 继续引用同一 original。当前 `formal-material-management = real-pass`。回收站新增 `GET /api/materials/deleted`，只返回 deleted material 元数据；恢复新增 `POST /api/materials/{material_id}/restore`，只在同一 SQLite 事务中清空 `deleted_at` 并更新 `updated_at`。恢复不改变 source_sha256、stored_path、extraction、text_spans 或 physical original，也不调用 Parser。页面提供正常材料/回收站切换和真实恢复流程，恢复后详情重新可读。当前 `formal-material-recycle-bin = real-pass`；不提供 include_deleted、批量恢复、回收站清空、恢复历史或物理 GC。

材料导出新增 `GET /api/materials/{material_id}/original` 和 `GET /api/materials/{material_id}/text`。前者只读取 active material 的数据库 stored_path，并验证其位于 configured originals_root 内且 SHA-256 匹配；后者只读取 active extraction.text 并以 UTF-8 plain text 下载。两个 endpoint 都拒绝 deleted material；restore 后恢复。rename 不变更内容身份，但会改变 Content-Disposition 下载文件名。导出不调用 Parser、不创建数据库记录、不创建 original 或临时文件。本阶段不提供批量下载、ZIP、文件夹导出或后台导出队列。

材料搜索扩展 `GET /api/materials` 的可选 `q` 参数。`material_search` 是 SQLite FTS5 可重建索引，不是 source of truth；connect 初始化时对已有 material/extraction 补齐缺失索引行，上传和 rename 在 SQLite 事务中同步写入或替换索引行。查询始终 join materials/extractions 并限定 `deleted_at IS NULL`，所以 delete 不删除索引且 restore 不需要重新解析。q 会 trim、按空白切 token、按 AND 匹配；ASCII token 以安全引用的 FTS5 MATCH 候选查询，中文和特殊 token 走参数化 `instr` fallback。结果不含 extraction text 或 stored_path，snippet 最长 160 字符。内嵌页面使用 `textContent`/DOM 节点渲染 snippet、match_fields 和详情正文命中，不将用户内容作为 HTML 执行；active 搜索详情会安全标示首个正文命中，名称-only 命中不伪造高亮；批量导入结果和 filters 也使用安全 DOM 文本节点，动态数据不作为 HTML 执行；列表与搜索计数共用一次 active API 响应，并以 generation 忽略过期响应，避免快速搜索、筛选或清除时旧结果覆盖新结果，真实 Chromium 已验证竞态边界和当前错误状态；详情请求也使用 generation 保护，旧详情响应不会覆盖当前材料；rename、delete、restore 使用 mutation busy guard，成功或失败后恢复页面操作状态，详情和导出按钮按 active/deleted 状态重新计算；生命周期 mutation 的成功、失败、重复操作和旧响应边界由真实 Chromium 验收覆盖；active/deleted lifecycle 规则不变。

回收站 purge 是显式单材料操作：只允许 deleted material，事务删除 material/extraction/text_spans 并手动删除 FTS 行；提交后以 source_sha256 引用计数保护共享 original，再通过 originals_root 边界和 SHA-256 校验执行 best-effort 文件删除。OCR、旧格式转换、provider、S1-S7、崩溃恢复和压力测试暂缓。

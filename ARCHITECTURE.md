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

材料管理使用 active material 语义：rename 只更新 `materials.original_name/updated_at`；delete 只设置 `materials.deleted_at`，不物理删除 hash 派生 original，不删除 extraction 或 text_spans。列表和详情默认只读取 `deleted_at IS NULL`，deleted detail 返回 404；同 hash material 删除一个时，其他 material 继续引用同一 original。当前 `formal-material-management = implemented`，本阶段不提供 include_deleted、恢复、物理 GC 或回收站。

OCR、旧格式转换、provider、S1-S7、崩溃恢复和压力测试暂缓。

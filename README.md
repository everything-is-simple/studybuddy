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

材料搜索已达到局部 `real-pass`：`GET /api/materials?q=<query>` 搜索 active material 的展示名称和 extraction.text，可与 `status` 组合。ASCII token 使用 SQLite FTS5 的安全 AND 候选查询，中文或特殊 token 使用参数化 substring fallback；所有结果重新按 active source tables 过滤，返回元数据、match_fields 和最多 160 个字符的纯文本 snippet，不返回完整正文或 stored_path。浏览器搜索结果现在以安全的纯文本 DOM 节点显示命中字段和 snippet；进入 active 详情后会定位并标示首个正文命中，名称-only 命中不会伪造正文高亮；页面动态内容（批量文件名、warning、error_code、筛选按钮）统一使用安全 DOM 文本节点渲染；搜索计数和列表共用一次 API 响应；请求代数保护快速搜索、筛选和清除操作，已通过真实 Chromium 验证过期响应和过期错误不会覆盖新状态；详情请求同样受 generation 保护，快速切换材料时旧详情不会覆盖当前选择；rename、delete、restore 在 mutation 期间禁用重复操作，并使旧列表/详情响应失效；成功和失败后管理、详情与导出按钮状态会恢复一致；rename/delete/restore 的重复操作、错误状态和 active/deleted 边界已由真实 Chromium 验收；非搜索及回收站列表不显示搜索上下文。rename 同事务更新索引，delete/restore 通过 active lifecycle filter 控制可见性。本阶段不支持语义/向量/AI 搜索、搜索历史或 saved search。

材料导出现在支持 active materials 的批量 original/text/bundle ZIP，安全处理同名 entry、shared hash、路径和 SHA-256 校验；active、搜索和 deleted 列表支持可选 limit/offset 分页，返回 total/has_more，页面提供稳定翻页，旧无参数请求仍返回数组；导出不调用 parser、不修改数据库，deleted/mixed 材料整体拒绝。回收站支持显式单材料永久删除：purge 仅接受已删除材料，事务清理 material/extraction/spans/search 行；仅当没有任何其他 material 引用同一 hash 时才 best-effort 删除经路径和 SHA-256 校验的 original，共享 hash 不会误删。该操作不可恢复且不自动触发。这不代表整个 StudyBuddy 已 real-pass。页面现支持 Chromium `webkitdirectory` 文件夹选择：浏览器递归枚举用户选定目录及子目录中的实际文件，并复用 `POST /api/materials/batch` 的逐文件 partial-success 语义；服务端绝不扫描用户目录、不接收服务器/客户端路径输入，也不保存 `webkitRelativePath`。材料名仍是安全 basename；同一批中嵌套目录的同 basename 文件按发送顺序独立导入，不会覆盖。页面仅在本次 batch 结果中以安全纯文本显示浏览器提供的相对路径，导入后回到 active 列表第一页并刷新分页；导入 busy guard 会阻止重复请求。未实现 ZIP 导入、文件夹导出、后台队列或服务器路径输入。

应用启动时执行一次保守的存储 recovery：只清理 data root 顶层遗留的 `.incoming-*` 普通文件，并只删除严格 hash-derived layout 中、内容 hash 正确且没有 active/deleted SQLite material 引用的 orphan original；hash mismatch 与 unexpected-layout 文件保留，缺失 original 只记录诊断、不删除 material。临时写入、original 落盘和 SQLite 持久化失败均返回安全错误并清理新建且无引用的文件；单文件仍保持 413，batch 仍保持 item-level partial-success。故障注入测试使用 monkeypatch 模拟 OSError/数据库失败，不等于真实磁盘填满或网络盘验收。SQLite 中 material、extraction、spans 与 FTS search row 在同一导入事务内；batch 每个 item 独立 rollback。materials/extractions 是 source of truth，connect 会幂等补齐缺失的 FTS row 并删除孤立 FTS row，rename 与 search 替换、purge 与 search 删除也在事务内。所有 physical original 读写要求位于 configured originals_root，root、hash directory 和 original symlink 均不跟随；只有 hash 正确的 regular original 才复用，hash mismatch 与 unexpected layout 保留。download/export 对 unsafe、missing 或 mismatch original 安全失败，text export 仍可独立读取 SQLite extraction；purge 在数据库提交后才 best-effort 清理 physical original。路径竞态测试使用 controlled monkeypatch，不等于真实并发证明。同一应用进程内以 SHA-256 keyed synchronization 协调同 hash import；critical section 覆盖 original store、Parser、SQLite persist 与 newly-created original cleanup，因此失败导入不会删除 waiting/successful 同 hash import 的 original；不同 hash 不使用全局上传锁，且 multipart 网络读取不持锁。该机制不支持多个进程或多个服务实例共享 data_root。进程级崩溃恢复通过 controlled subprocess 验证：SQLite 未提交事务不会恢复半成品，original 已落盘但无引用时按 strict orphan 规则处理，已提交 material/original 在重启后继续可读；这不宣称真实断电、硬件损坏、磁盘损坏或网络文件系统故障恢复。启动顺序保持 `data_root mkdir → SQLite connect/schema/index init → db_audit.run_audit() → recovery.reconcile → yield`。SQLite audit 是一次性 diagnostic-only：检查 `integrity_check`、`foreign_key_check`、required objects 和核心关系，不自动修复业务数据；可连接但诊断非 ok 时记录安全事件并继续启动，connect 彻底失败时不伪造 healthy。SQLite 保持 WAL、foreign keys 与 2000 ms busy_timeout；controlled `BEGIN IMMEDIATE` write-contention 测试验证 lock timeout 的 import/mutation 安全失败、transaction rollback、batch item-level failure、new original cleanup 和 shared original 保护，lock release 后后续请求恢复。purge physical cleanup 与 import 使用相同 SHA-256 process-local lock；purge commit 后在锁内重新查询 active/deleted 引用，再执行 safe best-effort unlink，避免 purge/import race 误删 original。固定生命周期状态机回归覆盖 active/deleted/purged、shared hash、parser success/empty/rejected、搜索、分页、导出、失败后续操作和 restart 不变量；这是 deterministic system regression，不是性能基准，也不支持多进程共享 data_root。HTTP API 输入边界也通过固定矩阵覆盖 malformed multipart/JSON、非法 filename/ID、分页/status/export 参数、method/content-type 和 mutation 状态错误；单文件 413、batch partial-success、正常 response contract 与 list/search 隐私边界保持。recovery 不运行后台任务；ZIP、队列、AI/provider 仍不支持。

整个 StudyBuddy 仍不是全局 `real-pass`；磁盘满真实压力、网络盘和长时间压力测试仍暂缓。

测试使用 `H:\studybuddy-test` 下的合成 fixture、runs 和脱敏 artifact，不写入本目录运行数据库或原文件副本。

# StudyBuddy

个人学习系统主目录。

远端仓库：`https://github.com/everything-is-simple/studybuddy.git`

本目录只存正式产品源码、正式测试和必要文档。组件必须先在 `H:\studybuddy-composer` 完成独立测试，再在 `H:\studybuddy-integration` 完成组合测试，最后由主系统重新实现或装配。不得从参考项目直接复制源码作为正式实现。

## 当前正式实现

正式文件解析 Adapter 位于 `backend/app/adapters/file_parsers/`，依据已通过的 Composer smoke 和 Integration 契约独立重实现。当前覆盖 TXT、Markdown、PDF、DOCX、PPTX；RTF、旧 DOC、旧 PPT 明确拒绝。Adapter 返回 SHA-256、版本、状态、结构化 page/slide span、warning、错误码和耗时，并执行文件大小与 ZIP/XML 容器资源限制。

默认单文件上传上限为 50 MiB，可通过 `STUDYBUDDY_MAX_UPLOAD_BYTES` 调整；这不是免费版或解析组件的硬限制。ZIP/XML 容器仍执行 member 数量、解压总量和压缩比限制。`backend/app/storage.py` 提供最小原文件保存边界，`backend/app/repository.py` 提供最小 SQLite extraction/span 事务边界。`backend/app/main.py` 现在提供最小 FastAPI multipart 上传、材料查询和静态文件选择器页面：上传文件会保存原文件、调用 Parser、在同一 SQLite 事务写入 extraction/spans，并可在服务重启后通过 API 回读。

正式文件导入基础链路已达到局部 `real-pass`，最终证据位于 `H:\studybuddy-test\artifacts\formal-file-import-final\latest.json`。真实 Chromium 已覆盖 TXT/Markdown/中文 TXT、合法空文件、PDF、DOCX、PPTX、损坏容器、RTF/旧 DOC/旧 PPT rejection；50 MiB 边界、重复 hash、原文件清理、刷新回读和服务重启回读均已通过。

这不代表整个 StudyBuddy 已 real-pass。当前没有完整多文件业务流程、OCR、转换器、真实 provider 或 S1-S7 业务实现；崩溃恢复、磁盘满、网络盘和长时间压力测试仍暂缓。

测试使用 `H:\studybuddy-test` 下的合成 fixture、runs 和脱敏 artifact，不写入本目录运行数据库或原文件副本。

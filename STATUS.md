# StudyBuddy Status

| Area | Status | Evidence |
|---|---|---|
| Main directory | prepared | `H:\studybuddy` |
| Composer contract | smoke_passed | `H:\studybuddy-test\artifacts\backend-file-parsers\latest.json` |
| Integration foundation | integration_passed | `H:\studybuddy-test\artifacts\file-storage-foundation\latest.json` |
| Formal file parser Adapter | implemented | `H:\studybuddy-test\artifacts\formal-file-parsers\latest.json` |
| Formal storage boundary | implemented | `backend/app/storage.py` tests |
| Formal SQLite extraction boundary | implemented | `backend/app/repository.py` tests |
| Formal file import user path | real-pass | `H:\studybuddy-test\artifacts\formal-file-import-final\latest.json` |
| Formal multi-file import and material list | real-pass | `H:\studybuddy-test\artifacts\formal-multi-file-import\latest.json` |
| Formal folder import | real-pass | `H:\studybuddy-test\artifacts\formal-folder-import\latest.json` |
| Formal material management | real-pass | `H:\studybuddy-test\artifacts\formal-material-management\latest.json` |
| Formal material recycle bin | real-pass | `H:\studybuddy-test\artifacts\formal-material-recycle-bin\latest.json` |
| Formal material export | real-pass | `H:\studybuddy-test\artifacts\formal-material-export\latest.json` |
| Formal material search | real-pass | `H:\studybuddy-test\artifacts\formal-material-search\latest.json` |
| Import recovery consistency | implemented | `backend/app/recovery.py` and Python tests |
| Import failure boundaries | implemented | `backend/tests/test_import_failure_boundaries.py` |
| SQLite transaction consistency | implemented | `backend/tests/test_sqlite_transaction_consistency.py` |
| Storage path security | implemented | `backend/tests/test_storage_path_security.py` |
| S1-S7 / AI / provider | not started | explicitly deferred |

状态含义：`not started`、`researching`、`implemented`、`real-pass`。正式文件导入基础链路保持局部 `real-pass`。多文件能力当前为局部 `real-pass`：batch endpoint、逐文件事务、部分成功、真实 multiple file input、完整 parser fixture 浏览器批次、列表筛选、详情和刷新/重启回读均已通过。材料管理当前为局部 `real-pass`：重命名、逻辑删除、deleted_at 迁移、同 hash 保留、刷新/重启回读和真实浏览器流程均已通过。材料回收站当前为局部 `real-pass`：deleted list、元数据保护、restore、同 hash 保留、刷新/重启回读和真实浏览器流程均已通过。材料导出当前为局部 `real-pass`：active 原文件下载、extraction.text 正文导出、rename 文件名变化、删除/恢复生命周期、路径/hash 校验、空材料导出和真实浏览器下载均已通过。材料搜索当前为局部 `real-pass`：名称/正文搜索、中文受控 fallback、多词 AND、status 组合、rename/delete/restore 一致性、索引初始化和真实浏览器搜索均已通过；浏览器结果显示后端 snippet 与 match_fields；进入 active 详情后安全定位并标示首个正文命中，名称-only 命中不伪造高亮；纯文本安全渲染；批量文件名、warning、error_code 和 filters 均安全渲染；搜索计数与列表共用一次响应，过期搜索/筛选/清除响应及其错误被忽略，详情旧响应也被忽略；mutation 期间重复操作被禁用，详情/导出按钮状态保持一致；mutation 成功、失败、重复操作和 stale 响应均已真实 Chromium 验收（真实 Chromium 已验收），列表不泄露完整正文。材料导出现已包含 active-only 的批量 original/text/bundle ZIP，真实浏览器验证了 entry 内容、错误状态和安全边界。材料 active/search/deleted 列表已增加 limit/offset 分页、total/has_more、稳定排序和真实 Chromium 翻页验证；无分页参数保持旧数组响应。回收站现已包含显式单材料 purge：永久清理 deleted material 的 extraction/spans/search 数据，共享 hash original 采用引用计数保护，active 或 missing purge 返回 404；真实 Chromium 已覆盖成功、失败和重复点击。文件夹导入当前为局部 `real-pass`：真实 Chromium 的 `webkitdirectory` 控件将所选目录和子目录中的文件提交给既有 batch endpoint；服务端不扫描目录、不接收或保存客户端路径，材料仍以 basename 持久化。相对目录名只在当前 batch 结果中安全显示；嵌套同 basename 均独立导入，partial-success、列表刷新、分页重置和重复请求保护已经验收。

整个 StudyBuddy 仍不是 `real-pass`；后台任务队列、批量恢复、物理 GC、语义/向量/AI 搜索、S1-S7、AI、provider、OCR、旧格式转换和压力测试尚未完成。导入 recovery 仅在启动时一次性执行，严格保护 hash mismatch、unexpected layout 和 missing original；不提供后台定时清理或多进程共享 data_root。导入故障边界已通过可控 OSError/SQLite failure 注入测试；SQLite material/extraction/span/search transaction、FTS 补齐与孤立索引清理、rename/purge rollback 也已覆盖。Storage path security 已覆盖 root containment、root/hash-directory/original symlink 跳过、hash mismatch 保留、download/export 安全失败、text export 独立可用和 shared original 保护；path-race 使用 controlled monkeypatch，不等于真实并发验收。这不等于真实磁盘填满或网络盘压力验收。

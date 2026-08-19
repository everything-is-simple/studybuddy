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
| Formal material management | real-pass | `H:\studybuddy-test\artifacts\formal-material-management\latest.json` |
| Formal material recycle bin | real-pass | `H:\studybuddy-test\artifacts\formal-material-recycle-bin\latest.json` |
| Formal material export | real-pass | `H:\studybuddy-test\artifacts\formal-material-export\latest.json` |
| Formal material search | real-pass | `H:\studybuddy-test\artifacts\formal-material-search\latest.json` |
| S1-S7 / AI / provider | not started | explicitly deferred |

状态含义：`not started`、`researching`、`implemented`、`real-pass`。正式文件导入基础链路保持局部 `real-pass`。多文件能力当前为局部 `real-pass`：batch endpoint、逐文件事务、部分成功、真实 multiple file input、完整 parser fixture 浏览器批次、列表筛选、详情和刷新/重启回读均已通过。材料管理当前为局部 `real-pass`：重命名、逻辑删除、deleted_at 迁移、同 hash 保留、刷新/重启回读和真实浏览器流程均已通过。材料回收站当前为局部 `real-pass`：deleted list、元数据保护、restore、同 hash 保留、刷新/重启回读和真实浏览器流程均已通过。材料导出当前为局部 `real-pass`：active 原文件下载、extraction.text 正文导出、rename 文件名变化、删除/恢复生命周期、路径/hash 校验、空材料导出和真实浏览器下载均已通过。材料搜索当前为局部 `real-pass`：名称/正文搜索、中文受控 fallback、多词 AND、status 组合、rename/delete/restore 一致性、索引初始化和真实浏览器搜索均已通过。整个 StudyBuddy 仍不是 `real-pass`；文件夹导入、后台任务队列、批量恢复、物理 GC、批量/ZIP 导出、语义/向量/AI 搜索、S1-S7、AI、provider、OCR、旧格式转换、崩溃恢复和压力测试尚未完成。

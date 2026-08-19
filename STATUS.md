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
| S1-S7 / AI / provider | not started | explicitly deferred |

状态含义：`not started`、`researching`、`implemented`、`real-pass`。正式文件导入基础链路已达到局部 `real-pass`：FastAPI multipart 上传、原文件保存、Parser、SQLite 写入、Chromium 真实选择器操作、全部 fixture 失败矩阵、50 MiB 边界、重复 hash、数据库失败清理、路径穿越、超限清理、刷新和服务重启后页面回读均已通过。整个 StudyBuddy 仍不是 `real-pass`；S1-S7、AI、provider、多文件业务、崩溃恢复和压力测试尚未完成。

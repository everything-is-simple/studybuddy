# StudyBuddy Status

| Area | Status | Evidence |
|---|---|---|
| Main directory | prepared | `H:\studybuddy` |
| Composer contract | smoke_passed | `H:\studybuddy-test\artifacts\backend-file-parsers\latest.json` |
| Integration foundation | integration_passed | `H:\studybuddy-test\artifacts\file-storage-foundation\latest.json` |
| Formal file parser Adapter | implemented | `H:\studybuddy-test\artifacts\formal-file-parsers\latest.json` |
| Formal storage boundary | implemented | `backend/app/storage.py` tests |
| Formal SQLite extraction boundary | implemented | `backend/app/repository.py` tests |
| Formal file import user path | implemented | `H:\studybuddy-test\artifacts\formal-file-import\latest.json` |
| S1-S7 / AI / provider | not started | explicitly deferred |

状态含义：`not started`、`researching`、`implemented`、`real-pass`。当前已通过 FastAPI multipart 上传、原文件保存、Parser、SQLite 写入、服务重启后 API 回读；默认单文件上传上限为 50 MiB，可配置调整。由于尚未完成完整浏览器验收、多文件流程和异常恢复测试，仍只能标记为 `implemented`，不能标记 `real-pass`。

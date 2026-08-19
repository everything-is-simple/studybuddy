# StudyBuddy Status

| Area | Status | Evidence |
|---|---|---|
| Main directory | prepared | `H:\studybuddy` |
| Composer contract | smoke_passed | `H:\studybuddy-test\artifacts\backend-file-parsers\latest.json` |
| Integration foundation | integration_passed | `H:\studybuddy-test\artifacts\file-storage-foundation\latest.json` |
| Formal file parser Adapter | implemented | `H:\studybuddy-test\artifacts\formal-file-parsers\latest.json` |
| Formal storage boundary | implemented | `backend/app/storage.py` tests |
| Formal SQLite extraction boundary | implemented | `backend/app/repository.py` tests |
| Real user path | not started | no upload/restart UI path |
| S1-S7 / AI / provider | not started | explicitly deferred |

状态含义：`not started`、`researching`、`implemented`、`real-pass`。只有真实用户路径和重启回读通过，才允许使用 `real-pass`。本阶段只能标记为 `implemented`，不能标记 `real-pass`。

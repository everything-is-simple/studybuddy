# 9C-3 Repository 与 domain transaction

## 执行记录

状态：`implemented/backend-pass`。

- 基于 v11 `phase9c_exercise_feedback_schema`，在 `backend/app/repository.py` 实现 S3/S4/S5 共用 domain transaction：practice/cram goal/session、immutable item snapshot、服务端 start/deadline/expiry/finish、session-item submit、append-only attempt/review/feedback、mistake case/occurrence 和实时 weak-point projection。
- 所有 session、exercise、attempt、review、mistake、cram 写入按服务端 project scope 验证；创建快照只接受同 project `ready` exercise。MC/TF 使用 snapshot answer key 确定性评分，short answer 保持 `pending_review`，客户端 score/deadline/elapsed 不被采纳。
- session item 只接受首次提交；重复 item 或 submission key 返回安全 replay，不创建新 attempt。review 不改写 attempt，duplicate review 被拒绝；incorrect occurrence 按 attempt/reason 幂等，fixed case 的新错误进入 `reopened`。
- cram session 复用 practice session/attempt/grading，且测试确认不写 9A `study_progress_events`。source delete/re-index/purge 只降级历史 snapshot/occurrence 的安全 source status；公开 domain payload 不返回 answer key、submitted answer、source full text 或 stored path。
- 新增 `backend/tests/test_phase9c_domain.py`，覆盖 project/state、snapshot/privacy、MC/short answer/review、duplicate submit、mistake dedup/fixed/reopen、cram、expired session、source delete/purge 和 rollback。
- 实际命令与结果：`C:/miniconda/py310/python.exe -m pytest backend/tests/test_phase9c_domain.py -q` 为 `7 passed`；相关 focused regression 为 `46 passed`；完整 `C:/miniconda/py310/python.exe -m pytest backend/tests/ -q` 为 `306 passed, 2 skipped`。两个 skip 是 opt-in real-provider smoke，不构成 9C 证据。
- 本任务未提供 FastAPI routes、Chromium workspace、9C source-lifecycle 专项 acceptance、backup/restore 专项 acceptance 或 Phase 9C closeout。


```text
执行 Phase 9C-3：实现 S3/S4/S5 共用 repository/domain transaction，不实现正式 HTTP/UI 用户路径。

以 9C-1 契约和 9C-2 实际 schema 为准。实现 server-side project ownership、exercise/card 状态和 source/citation 验证、session/item snapshot、服务端时间边界、append-only attempt/review/feedback、错题和 weak-point 确定性投影、cram 关系、幂等和事务 rollback。计时不得信任客户端 elapsed/score；重做必须创建新 attempt；projection 不得修改旧事实。

复用 Phase 8 的 deterministic grading 和 privacy helper，但不能泄露 answer key/submitted answer。short answer 必须保持 pending_review，人工复核要显式记录 reviewer decision/feedback，不能伪造 deterministic。AI 生成的解析/反馈/变题先 draft，citation 在持久化前复验；不持久化 raw provider response/prompt 或 source full text。

覆盖 unit/integration tests：同 project/状态边界、expired session、duplicate submit、rollback、attempt append-only、MC/TF/short answer、review transition、mistake dedup/reopen、source stale/deleted/purged、cram 不改 plan/progress、privacy。只修改 backend/app/repository.py、必要的 domain module 和 backend/tests/test_phase9c_domain.py 等；不实现 routes/UI。

focused 通过后状态为 implemented/backend-pass；不要声称 API、Chromium、backup/restore 或 Phase 9C completed。
```
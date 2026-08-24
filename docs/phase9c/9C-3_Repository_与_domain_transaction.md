# 9C-3 Repository 与 domain transaction

```text
执行 Phase 9C-3：实现 S3/S4/S5 共用 repository/domain transaction，不实现正式 HTTP/UI 用户路径。

以 9C-1 契约和 9C-2 实际 schema 为准。实现 server-side project ownership、exercise/card 状态和 source/citation 验证、session/item snapshot、服务端时间边界、append-only attempt/review/feedback、错题和 weak-point 确定性投影、cram 关系、幂等和事务 rollback。计时不得信任客户端 elapsed/score；重做必须创建新 attempt；projection 不得修改旧事实。

复用 Phase 8 的 deterministic grading 和 privacy helper，但不能泄露 answer key/submitted answer。short answer 必须保持 pending_review，人工复核要显式记录 reviewer decision/feedback，不能伪造 deterministic。AI 生成的解析/反馈/变题先 draft，citation 在持久化前复验；不持久化 raw provider response/prompt 或 source full text。

覆盖 unit/integration tests：同 project/状态边界、expired session、duplicate submit、rollback、attempt append-only、MC/TF/short answer、review transition、mistake dedup/reopen、source stale/deleted/purged、cram 不改 plan/progress、privacy。只修改 backend/app/repository.py、必要的 domain module 和 backend/tests/test_phase9c_domain.py 等；不实现 routes/UI。

focused 通过后状态为 implemented/backend-pass；不要声称 API、Chromium、backup/restore 或 Phase 9C completed。
```
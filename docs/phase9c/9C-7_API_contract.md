# 9C-7 API contract

```text
执行 Phase 9C-7：将已通过 domain 的 S3/S4/S5 能力暴露为最小安全 FastAPI API，不在本任务新增业务规则或 UI。

先审计 main.py 的异常映射、Pydantic 输入、project scope、JSON 边界、现有 cards/exercises routes，再设计并实现 session、attempt、review、mistake/weak-point、cram goal/session/result 的最小资源。所有 project/user/score/deadline/answer-key 权限字段由服务端控制；客户端不得提交可信评分、计时、source status 或任意 project_id。保持稳定 400/404/409/422/500/503 语义，不返回 raw exception/provider response。

普通 list/detail 不返回 answer key、内部 grading key、提交答案原文或不必要 source text；submit/review 只返回安全结果和可见反馈。支持契约规定的 Idempotency-Key、retry、stale/expired conflict。导出若已冻结则复用安全 bounded download contract，否则只提供明确 deferred response。

新增 test_phase9c_api.py，覆盖输入边界、越权、错误映射、隐私、重复点击和生命周期。允许修改 backend/app/main.py、schemas/错误 helper 与 API tests；不新增 UI。完成后运行 focused 和相关 Phase 8/9A/9B regression。状态为 implemented/backend-pass。
```
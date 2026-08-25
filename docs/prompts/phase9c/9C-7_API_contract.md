# 9C-7 API contract

## 执行记录

状态：`implemented/backend-pass`。

- 在已通过的 S3/S4/S5 domain 上新增最小安全 FastAPI API，project scope 由服务端 `AppConfig.project_id` 注入；请求体不接受可信 score、elapsed、deadline、correctness、answer key、source status 或任意 project scope。
- S3 路由覆盖 practice session create/list/read/start/item submit/finish/archive/result；`Idempotency-Key` 映射到 domain submission key，重复同答案 replay，不同答案返回稳定 409 mismatch。
- S4 路由覆盖 mistake list/detail、attempt review、explicit mark-mistake、feedback、redo、archive、weak-points；review 和普通 detail 不返回 submitted answer 或 answer key。
- S5 路由覆盖 cram goal list/create/read/activate/completed/archived、cram session create 和 result；复用现有 domain，不新增 API 业务规则。
- ValueError 使用稳定安全 HTTP 映射：越权/不存在为 404，状态/过期/重复/idempotency/source scope conflict 为 409，输入边界为 400，Pydantic malformed payload 为 422，持久化异常为 500；不返回 raw traceback/provider/SQL/path。
- 新增 `backend/tests/test_phase9c_api.py`，覆盖 S3 round-trip/privacy/idempotency、S4 review/mark/feedback/redo/project scope、S5 goal/session/result、输入边界和安全错误。
- 实际命令与结果：`C:/miniconda/py310/python.exe -m pytest backend/tests/test_phase9c_api.py -q` 为 `3 passed`；相关 focused regression 为 `32 passed`；完整 `C:/miniconda/py310/python.exe -m pytest backend/tests/ -q` 为 `317 passed, 2 skipped`。两个 skip 是 opt-in real-provider smoke，不构成 9C 证据。
- 本任务未实现 Chromium UI、9C source-lifecycle 专项 acceptance、backup/restore closeout 或 Phase 9C completed。

```text
执行 Phase 9C-7：将已通过 domain 的 S3/S4/S5 能力暴露为最小安全 FastAPI API，不在本任务新增业务规则或 UI。

先审计 main.py 的异常映射、Pydantic 输入、project scope、JSON 边界、现有 cards/exercises routes，再设计并实现 session、attempt、review、mistake/weak-point、cram goal/session/result 的最小资源。所有 project/user/score/deadline/answer-key 权限字段由服务端控制；客户端不得提交可信评分、计时、source status 或任意 project_id。保持稳定 400/404/409/422/500/503 语义，不返回 raw exception/provider response。

普通 list/detail 不返回 answer key、内部 grading key、提交答案原文或不必要 source text；submit/review 只返回安全结果和可见反馈。支持契约规定的 Idempotency-Key、retry、stale/expired conflict。导出若已冻结则复用安全 bounded download contract，否则只提供明确 deferred response。

新增 test_phase9c_api.py，覆盖输入边界、越权、错误映射、隐私、重复点击和生命周期。允许修改 backend/app/main.py、schemas/错误 helper 与 API tests；不新增 UI。完成后运行 focused 和相关 Phase 8/9A/9B regression。状态为 implemented/backend-pass。
```

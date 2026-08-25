# 9D-7 S6 对外交付（默认关闭 + dry-run + 授权 + 审计）

```text
执行 Phase 9D-7：完成 S6 家长报告对外交付层，默认关闭、以 dry-run 为可重复路径，不实现自动定时推送、API 收口或 UI。

使用 ../00_COMMON_CONTEXT.md、9D-1 交付契约、9D-6 报告聚合。这是高风险子任务：交付会把数据发往第三方端点，接收方可能是家长、涉及未成年人。默认交付层只做本地可审计 dry-run（构造并记录将发送的内容摘要与目标，但不真正外发）；真实发送（SMTP/飞书等）必须是显式配置 + 显式开关 + 显式授权 + 收件白名单，且默认关闭；实现真实发送前须在报告中标注高风险并要求人确认。

必须遵守：
- 默认关闭：无显式启用时任何交付调用只走 dry-run，绝不真正外发；
- 授权与白名单：真实发送需显式授权且目标在白名单内，越权/非白名单目标稳定拒绝；
- secret 安全：渠道凭证只经配置读取，不入库、不入日志、不入 backup 明文、不进返回值；
- 审计：每次交付（含 dry-run）append-only 记录时间、渠道、目标（可脱敏）、内容摘要和结果；失败可重试但不静默重发，重复请求按幂等去重；
- 内容仍受 9D-6 脱敏约束，交付内容不得包含黑名单敏感数据；
- 不实现 scheduler/worker/自动定时推送；交付只能由显式请求触发；
- restore/startup/read/verify 不触发任何交付。

新增 focused backend tests（如 test_phase9d_delivery.py），覆盖默认关闭只 dry-run、启用后授权/白名单校验、越权拒绝、secret 不泄露、审计 append-only、失败重试与幂等去重、脱敏内容和无自动推送。真实端点发送默认 skip 或以 opt-in gate 标注，不纳入通用 real-pass。运行 focused、相关 regression 和完整 backend，用 C:\\miniconda\\py310\\python.exe -m pytest 报告数字。

只允许修改交付层 repository/domain/adapter、配置读取与对应测试；不实现 API 或 Chromium。验收：默认关闭、dry-run、授权/白名单、审计、secret 安全、幂等和无自动推送通过。状态为 implemented/backend-pass；真实外发标注为 not_verified / opt-in gate，不代表 API/UI、lifecycle/restore gates 或 Phase 9D completed。
```

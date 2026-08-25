# 9D-3 Repository 与 domain transaction

```text
执行 Phase 9D-3：只在新 schema 上实现 S6/S7 共享的 repository/domain transaction 层，不实现 S7 采集完整闭环、S6 交付、API 或 UI。

使用 ../00_COMMON_CONTEXT.md、9D-1 契约和 9D-2 schema。实现共享领域事务与投影：capture session 与转写 operation 记录的创建/读取、置信度与 uncertain 事实、report 聚合的可重算 projection、report 交付审计记录的 append-only 写入。所有写操作在单事务内保证原子性，失败可回滚，遵守 scope/ownership。

必须实现并测试的边界：
- append-only 事实（转写 operation、交付审计）不可覆盖；重算 projection 不伪造事实、不改写 9A/9B/9C 学习事实；
- 服务端注入 owner/scope；幂等键处理与重复请求安全 replay；
- 隐私与脱敏在领域层生效：report 聚合只取契约白名单字段，禁止把答案 key、提交原文、Q&A 原文、原文全文、路径、raw provider response 带入 projection 或返回值；
- 交付渠道 secret 只经配置读取，不落库、不进日志、不进返回值；
- 采集原件通过既有 originals/material lifecycle 引用，delete/purge 时按 source lifecycle 安全降级，不伪造正文或路径。

新增 backend/tests 中的 domain 测试（如 test_phase9d_domain.py），覆盖事务原子性/回滚、append-only 保护、projection 重算、幂等、scope、脱敏边界和 secret 不泄露。运行 focused 测试、相关 focused regression 和完整 backend 套件，用 C:\\miniconda\\py310\\python.exe -m pytest 报告数字。

只允许修改 repository/domain 与对应测试；不实现 S7 OCR/ASR 调用闭环、S6 真实/dry-run 交付执行、FastAPI 路由或 Chromium。验收：领域事务、投影、幂等、脱敏和 append-only 保护通过。状态为 implemented/backend-pass，不代表 S7/S6 workflow、API/UI、lifecycle/restore gates 或 Phase 9D completed。
```

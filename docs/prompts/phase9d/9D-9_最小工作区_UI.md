# 9D-9 最小工作区 UI

```text
执行 Phase 9D-9：实现 S6/S7 最小 Chromium workspace，不做 source lifecycle/backup 专项收口或 Phase 9D 收口。

使用 ../00_COMMON_CONTEXT.md 和 9D-8 API。实现最小可用工作区：S7 采集会话创建、原件上传、触发转写、查看带置信度/uncertain 的转写、把转写接入 S2 并 confirm/reject/archive；S6 生成/预览报告、导出、触发交付（默认 dry-run，明确显示未真实外发）、查看交付审计。UI 只调用 9D-8 API，不绕过后端业务规则。

必须覆盖的路径（在 backend/tests 的 browser_phase9d.spec.js，串行隔离 data root）：
- happy path：采集→转写→接入→confirm；报告生成→预览→导出→dry-run 交付→审计；
- 失败/边界：provider_not_configured、malformed/network failure、转写低置信/uncertain 提示、citation/source unavailable、交付默认关闭且不真实外发、越权/非白名单交付拒绝；
- duplicate click / 重复提交按幂等安全处理；
- reload recovery、390x844 窄屏 overflow、keyboard/focus 可达；
- 安全 DOM：普通 DOM 不出现 answer key、提交原文、Q&A 原文、原文全文、原件路径、secret、raw provider response 或收件人隐私。

运行 focused Chromium（browser_phase9d.spec.js）与相关 UI failure contract，报告 passed 数字；真实 OCR/ASR 与真实外发 spec 默认 skip 或以 opt-in gate 标注，不宣称通用 real-pass。

只允许修改前端 workspace 资源与 browser spec；不改 domain/migration/API 语义，不做 lifecycle/backup 专项或收口文档。验收：desktop/narrow/keyboard/reload/failure/privacy 路径通过，交付默认关闭在 UI 明确可见。状态为 browser-pass，不代表 real-pass、lifecycle/restore gates 或 Phase 9D completed。
```

# 9C-8 最小 Chromium workspace

## 执行记录

状态：`browser-pass`。

- 在已通过的 9C-7 API 上扩展当前 `backend/app/main.py` 单页 workspace，新增“练习反馈”视图和安全 DOM：S3 practice session 创建/选择/start/逐题 submit/finish/result，S4 错题安全查看/反馈/redo，S5 cram goal/session/result。
- UI 只显示服务端安全字段和 source warning；不显示 answer key、submitted answer 原文、stored path、provider raw data 或私有后端错误。所有文本使用 `textContent`，结果和失败状态使用现有 status/alert 约定。
- 覆盖 reload 后从服务端恢复 session list、duplicate/idempotency API 路径、500/network failure retry、默认 provider 不配置安全失败、keyboard/focus、390x844 无横向 overflow 和 S3/S4/S5 happy paths。
- 新增 `backend/tests/browser_phase9c.spec.js`，3 条 Chromium focused paths 全部通过；相关 frontend failure contract 一并通过。
- 实际命令与结果：`npx playwright test backend/tests/browser_phase9c.spec.js --workers=1` 为 `3 passed`；与 failure contract 合并为 `9 passed`；完整 backend 为 `317 passed, 2 skipped`。两个 backend skip 是 opt-in real-provider smoke。
- 本任务未实现生产级前端、后台任务、真实 Provider UI、9C source-lifecycle/backup/restore 专项 acceptance 或 Phase 9C closeout；browser-pass 不推导 real-pass。


```text
执行 Phase 9C-8：在已验收 S3/S4/S5 API 上实现最小本地 Chromium workspace，不实现生产级前端、后台任务或真实 Provider UI。

复用当前 main.py 单页 workspace 的安全 DOM、状态/alert/toast、busy/retry、generation/stale-response、键盘焦点和窄屏约定。提供可理解的路径：选择练习→开始限时 session→逐题作答→超时/提交→结果；结果→错题→查看错因/反馈→重做/人工复核；选择冲刺目标→模拟 session→结果/薄弱点。UI 不显示 answer key、submitted answer 原文（除非契约明确的本人 review 安全界面）、provider raw data 或 source path。

Chromium tests 必须覆盖 fake/default provider、happy path、expired/duplicate click、network/500/retry、refresh/reload、stale response、source unavailable、390x844 overflow、keyboard/focus 和隐私 DOM。不要用 browser pass 推导 real-pass。

只修改允许的 frontend/main.py 静态模板/脚本/style 和新增 browser_phase9c.spec.js；不改 schema/domain。运行 focused Playwright 与相关 UI failure regression。状态为 browser-pass。
```
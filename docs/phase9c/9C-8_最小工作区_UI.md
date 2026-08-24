# 9C-8 最小 Chromium workspace

```text
执行 Phase 9C-8：在已验收 S3/S4/S5 API 上实现最小本地 Chromium workspace，不实现生产级前端、后台任务或真实 Provider UI。

复用当前 main.py 单页 workspace 的安全 DOM、状态/alert/toast、busy/retry、generation/stale-response、键盘焦点和窄屏约定。提供可理解的路径：选择练习→开始限时 session→逐题作答→超时/提交→结果；结果→错题→查看错因/反馈→重做/人工复核；选择冲刺目标→模拟 session→结果/薄弱点。UI 不显示 answer key、submitted answer 原文（除非契约明确的本人 review 安全界面）、provider raw data 或 source path。

Chromium tests 必须覆盖 fake/default provider、happy path、expired/duplicate click、network/500/retry、refresh/reload、stale response、source unavailable、390x844 overflow、keyboard/focus 和隐私 DOM。不要用 browser pass 推导 real-pass。

只修改允许的 frontend/main.py 静态模板/脚本/style 和新增 browser_phase9c.spec.js；不改 schema/domain。运行 focused Playwright 与相关 UI failure regression。状态为 browser-pass。
```
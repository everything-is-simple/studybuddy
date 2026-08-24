# 9B-7：最小 S1/S2 工作区 UI

> 先使用 `00_COMMON_CONTEXT.md`、9B API contract 和现有前端 workspace 结构。本任务只实现本地 Chromium 可验收的最小工作区。

```text
执行 Phase 9B-7：实现 S1/S2 最小 Chromium workspace，不实现 S3/S4/S5、9D 或生产级前端扩展。

至少覆盖两条连续路径：
S2：选择材料 → 查看 ready/index/source 状态 → 创建 note → 关联 citation/source → 编辑 note → 创建或生成 knowledge-module draft → 查看 citation → confirm/reject/archive → 刷新恢复；
S1：进入 Phase 9A plan → 设置节奏 → 分配/调整 item → 查看时间线/负载/summary → 完成一个 item → 查看 progress → 刷新恢复。

复用现有统一导航、页面 status/alert、toast、busy guard、stale response guard、retry、安全 DOM 文本、citation dialog/定位和导出模式。明确显示 draft、user-edited、confirmed、archived、stale/unavailable 等状态；不得显示 source path、SQL、traceback、secret、raw provider output 或不在 API contract 中的完整正文。source unavailable/purged 必须显示安全状态，不伪造可点击引用。

新增 `backend/tests/browser_phase9b.spec.js`，串行、隔离临时 data root。覆盖 desktop、390x844 narrow、键盘 focus/操作、reload/history、重复点击、500/network/malformed response、provider_not_configured、empty retrieval、citation unavailable、编辑保护和 export failure。必要时补充 DOM contract，但不要依赖系统级 screen reader 或 axe 作为已通过证据。

验收：S1/S2 happy path 和 failure path 通过；窄屏无关键 overflow；刷新后状态从服务端恢复；状态只能写 `browser-pass` 或局部准确措辞，不能写 `real-pass` 或 Phase 9B completed。
```
# 9A-5：最小计划工作区 UI

> 先使用 `00_COMMON_CONTEXT.md` 作为前置 prompt，再使用本文件。


```text
执行 Phase 9A-5：实现能够证明 9A 核心闭环的最小 Chromium workspace，不实现 9B/9C/9D 体验。

用户路径必须覆盖：创建 goal → 创建 module → 创建 plan draft → 添加/编辑/排序 item → 添加 dependency → 非法环依赖安全失败 → confirm → activate → 完成一个 item → 查看 append-only progress/summary → 查看 source citation 状态 → 刷新后恢复。

复用现有统一导航、页面 status/alert、toast、busy guard、stale response guard、retry、safe DOM text rendering、citation dialog/定位模式。必须有 draft/active 明显区分，用户编辑保护提示，source deleted/purged/stale/unavailable 的安全显示。不得渲染 source path、SQL、traceback、provider raw response 或超出 contract 的正文。

新增 browser_phase9a.spec.js，并覆盖桌面、390x844 窄屏、键盘 focus/操作、重复点击、网络/500/ malformed response failure contract。测试必须使用隔离临时 data root，并串行运行。

验收：Chromium happy path 和 failure path 通过；refresh/history 状态正确；窄屏无关键 overflow；不把 browser-pass 写成 real-pass。
```
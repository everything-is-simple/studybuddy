# Practice Workflow 第二阶段验收证据

> 状态：`scoped-closeout / 2026-08-30`

## 范围

本阶段仅完成既有 Practice API 的原生静态前端工作区，不新增 endpoint、schema、migration、错误码或后端业务语义。范围限定为 local single-process、SQLite、deterministic fake-provider 及本地 Chromium。

## 实现

- `practice.html`：会话和错题入口分别导航到独立页面，并通过 URL 传递非敏感 `session_id`/`mistake_id`。
- `practice-session.html`：公开题目、start、submit、finish、nested result、expired/source warning、retry/stale。
- `practice-result.html`：使用 `summary.score_total` 和 `summary.total_item_count`，不显示答案 key。
- `review.html`：详情、feedback、review、mark-mistake、redo、archive；写操作使用共享 API 层、JSON Content-Type、busy/retry 和服务端刷新。

## 测试证据

Focused browser：

```text
npm run test:browser -- --workers=1 --reporter=line backend/tests/browser_practice_workflow.spec.js
7 passed
```

Focused Phase 9C backend：

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_phase9c_api.py backend/tests/test_phase9c_domain.py backend/tests/test_phase9c_source_lifecycle.py -q
19 passed
```

完整 backend：

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
422 passed, 2 skipped
```

完整 browser 最终运行结果：`127 passed, 3 skipped`（130 项）。4 个涉及服务重启/停止的测试已通过串行生命周期修复收口：`browser_file_import.spec.js`、`browser_material_search.spec.js`、`browser_phase9b.spec.js`、`browser_phase9c.spec.js`。Practice 独立静态页面 focused suite 为 `7 passed`。3 个 skip 均为 opt-in real-provider browser smoke；该结论仍仅为本地限定范围 scoped closeout，不是全量 production real-pass。

契约审计：

```text
21 pages, 152 routes, 0 findings
```

源码尺寸：`passed`。

## 隐私和安全断言

- 页面只渲染后端批准的公开字段。
- `answer_key_json`、用户提交答案、内部 grading payload、traceback、SQL、secret 和路径不进入 DOM、URL 或浏览器存储。
- 页面操作通过 `sbApi` 并保留 page scope；异步详情和列表使用 generation 保护，旧响应不覆盖新上下文。
- Review 来源不可用/已删除状态显示安全用户文案，不伪造来源有效。

## 未验证边界

- 真实 Provider generation；
- 系统级 screen reader；
- 极端长内容和长时稳定性；
- 后台 worker、流式输出、多进程和多用户部署；
- 自适应出题、间隔重复、人工简答复核等后续业务能力；这些能力进入 Practice 第三阶段需求审计/契约冻结，尚未实现。

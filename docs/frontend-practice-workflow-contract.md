# Practice Workflow 前端行为契约

> 状态：`frozen / user-approved`
> 更新：2026-08-30
> 范围：仅冻结既有 Practice API 的前端行为，不新增 endpoint、schema、migration、错误码或后端业务语义。

## 1. 依据与边界

本契约依据：

- [`ROADMAP_CAPABILITIES.md`](ROADMAP_CAPABILITIES.md) 的“后续前端能力切片 / Practice workflow”；
- [`TODO.md`](TODO.md) 的 Practice workflow 页面切片待办；
- [`frontend-plan.md`](frontend-plan.md) 的前端 API、状态、隐私和 browser evidence 规则；
- [`frontend-contract-audit.md`](frontend-contract-audit.md) 的页面职责与安全审计规则；
- 现有后端路由 `backend/app/api/study_practice.py`；
- 当前只读页面：`practice-session.html`、`practice-result.html`、`review.html`。

本阶段只消费已存在的正式 API。`/legacy` 仅作为行为回归参考，不复制其实现。fake-provider 或 deterministic 数据通过不等于 real-pass。

## 2. 页面职责

### `practice-session.html`

- 读取会话详情；
- 展示会话状态、题目顺序和当前题目；
- 对 `draft` 会话提供开始入口；
- 对 `active` 会话提供逐题答题和提交入口；
- 展示每题允许公开的提交结果；
- 提供完成会话入口；
- 完成后进入 `practice-result.html`。

### `practice-result.html`

- 读取已完成会话结果；
- 展示分数、总题数和允许公开的反馈；
- 不展示答案 key、内部 grading payload 或未批准的题目正文；
- 提供进入 `review.html` 的入口（若已有可用上下文）。

### `review.html`

- 读取错题和薄弱点；
- 展示允许公开的错误原因、薄弱点和来源状态；
- 提供 feedback、mark-mistake、review、redo 的后续迁移入口；
- 对不可用或已归档内容显示安全状态，不伪造 redo 成功。

## 3. 已存在 API 映射

| 行为 | Method | Endpoint | 前端页面 |
|---|---|---|---|
| 会话列表 | GET | `/api/study/practice-sessions` | `practice.html` |
| 会话详情 | GET | `/api/study/practice-sessions/{session_id}` | `practice-session.html` |
| 开始会话 | POST | `/api/study/practice-sessions/{session_id}/start` | `practice-session.html` |
| 提交题目答案 | POST | `/api/study/practice-sessions/{session_id}/items/{item_id}/submit` | `practice-session.html` |
| 完成会话 | POST | `/api/study/practice-sessions/{session_id}/finish` | `practice-session.html` |
| 会话结果 | GET | `/api/study/practice-sessions/{session_id}/result` | `practice-result.html` |
| 错题列表 | GET | `/api/study/mistakes` | `review.html` |
| 错题详情 | GET | `/api/study/mistakes/{mistake_id}` | `review.html` |
| 复核 attempt | POST | `/api/study/attempts/{attempt_id}/review` | `review.html` |
| 标记错题 | POST | `/api/study/attempts/{attempt_id}/mark-mistake` | `review.html` |
| 错题反馈 | POST | `/api/study/mistakes/{mistake_id}/feedback` | `review.html` |
| 错题 redo | POST | `/api/study/mistakes/{mistake_id}/redo` | `review.html` |
| 错题归档 | POST | `/api/study/mistakes/{mistake_id}/archive` | `review.html` |

请求字段、响应字段和错误码必须以现有正式 API schema/测试为准；页面不得根据 `/legacy` 文本猜字段。

### 已核对的响应形状

- `GET /api/study/practice-sessions/{session_id}` 返回会话对象，包含 `items` 和 `summary`；每个 item 可公开 `prompt`、`options`、`exercise_type`、`citation_status` 等字段，但不含 `answer_key_json`。
- `GET /api/study/practice-sessions/{session_id}/result` 返回 `{session, summary}`，分数从 `summary.score_total` 读取，题目总数从 `summary.total_item_count` 读取；不得按扁平的 `score`/`total` 字段猜测。
- `GET /api/study/mistakes` 返回错题列表；答案 key、提交答案和内部 grading payload 不属于页面显示合同。
- submit 的请求体为 `{answer: object}`；`review` 使用 `{decision, feedback}`；`mark-mistake` 使用 `{feedback}`；mistake feedback 使用 `{event_kind, content}`。

### 评审结论

用户已确认以下实现约束：

1. 结果页使用真实响应结构 `summary.score_total` 和 `summary.total_item_count`，不假设扁平 `score`/`total` 字段；
2. 题目页只渲染 `prompt`、`options`、`exercise_type`、`citation_status` 等后端公开字段；
3. `answer_key_json`、提交答案和内部 grading payload 永不进入页面 DOM、URL、浏览器存储或普通日志。

契约现已冻结，可以进入实现和 browser evidence 阶段。

## 4. 状态合同

### 会话状态

```text
draft → active → finished
              └→ expired
finished → archived
```

用户可见状态统一通过 `sbState.label()` 映射。至少覆盖：

```text
draft / active / finished / expired / archived
```

API 失败状态统一使用 `sbApi.safeError()`，不得显示原始错误、路径、SQL、traceback 或 Provider 响应。

### 题目提交状态

前端必须区分：

```text
未提交
提交中
已提交
提交失败，可重试
会话已过期
会话状态不可操作
```

如果后端只返回安全 grading 结果，页面只展示该结果；不得从响应推导或补全答案 key。

### 错题状态

至少覆盖：

```text
可复习
已复核
来源过期
来源已删除
来源不可用
已归档
redo 失败，可重试
```

来源生命周期继续使用 `sbState.source()`，不把内部状态码作为唯一文案。

## 5. 答案 key 与隐私

- 普通会话列表、会话详情、结果页和错题列表不得渲染答案 key；
- 用户答案可以发送到既有 submit API，但不得写入 URL、localStorage、sessionStorage 或调试日志；
- DOM、页面错误、错误提示和测试 artifact 不得包含答案 key、内部 grading payload 或未批准的完整正文；
- 结果页只显示允许公开的 score、total 和 grading note；
- 刷新、返回、retry、切换题目和导航不得导致答案 key 泄露；
- 不通过前端隐藏元素来“保护”不应从 API 返回的敏感字段；后端响应本身仍必须是安全契约。

## 6. 幂等、重复点击与取消

- 所有写操作使用共享 `sbApi` 请求层；JSON 请求使用 `Content-Type: application/json`；
- `submit` 使用 `Idempotency-Key`；同一提交可安全 replay；不同答案不得错误复用旧结果；
- `start`、`finish`、`review`、`mark-mistake`、`feedback`、`redo`、`archive` 按正式 API 的状态/冲突语义显示结果；
- 操作进行中禁用对应按钮，重复点击不增加请求；
- 失败后恢复按钮并提供安全 retry；不通过重复点击伪造成功；
- 页面使用 `setPageScope()` 和 `pageRequest.signal`；离开页面时取消尚未完成的前端请求。

## 7. stale response 与上下文

以下响应必须在上下文已改变时被丢弃：

- 切换 session；
- 切换题目；
- submit 后重新读取详情；
- finish 后进入结果页；
- 从 result 返回 review；
- 点击 redo 后刷新错题；
- 页面导航、reload 或 `pagehide`。

实现使用独立 generation/context 标识，不使用会被自身覆盖的比较表达式。URL 只保留非敏感的 `session_id` 或 `mistake_id`。

## 8. Loading / empty / ready / failed / retry

每个独立页面必须有可定位的页面级状态：

- `loading`：请求进行中；
- `empty`：没有会话、结果或错题；
- `ready`：安全数据已渲染；
- `failed`：安全错误文案和稳定页面状态；
- `retry`：失败后可重复执行且控件恢复；
- `expired` / `source_unavailable` 等领域状态不得被普通 empty 覆盖。

## 9. Browser evidence 矩阵

正式实现前必须新增或扩展独立 browser spec，至少覆盖：

| 类别 | 证据 |
|---|---|
| 读取 | session detail、result、mistake list/detail 成功路径 |
| 状态 | draft、active、finished、expired、archived、source unavailable |
| 写操作 | start、submit、finish、review、mark-mistake、feedback、redo、archive；当前页面已实现 start/submit/finish/redo/archive，review/mark-mistake/feedback 仍待独立控件迁移 |
| 失败 | 404、409、5xx、malformed response、network abort |
| 重试 | failed → retry → ready；按钮恢复可用 |
| 幂等 | submit duplicate click、same key replay、不同提交不串结果；当前浏览器证据覆盖 duplicate-click single request，API 层既有测试覆盖 replay/mismatch |
| stale | session/question/result/review 切换后旧响应不渲染 |
| 隐私 | DOM/URL/日志不含答案 key、路径、SQL、traceback、secret/raw response |
| 可用性 | 360/390/430/600/768/820/1024/1366/1440/1920、键盘、可见焦点 |
| 导航 | practice → session → result → review 以及返回路径 |

## 10. 门禁与交付顺序

1. 评审并冻结本文件；
2. 只根据冻结契约实现页面，不修改后端；
3. 新增独立 browser evidence；
4. 运行 focused backend/API tests 和 browser tests；
5. 运行完整 backend/browser、contract audit、source-size、diff check；
6. 更新 `STATUS.md`、`TODO.md`、`ROADMAP_CAPABILITIES.md`、`frontend-plan.md` 和矩阵；
7. 单独提交并推送。

契约已获用户确认并标记为 `frozen / user-approved`。现在可以开始 submit/finish/redo 页面实现，但必须严格遵循本文件，不修改后端 API、schema、migration、错误码或业务语义。

## 11. 明确不在本契约

- Provider 配置写入、密钥保存、连接测试；
- 报告导出、完整审计工作区和 live delivery；
- 真实 ASR/OCR；
- 新 endpoint、schema、migration、错误码或外部 Provider；
- 多用户、云同步、后台 worker 或多进程协调；
- 将 fake/loopback/dry-run 结果标记为 real-pass。

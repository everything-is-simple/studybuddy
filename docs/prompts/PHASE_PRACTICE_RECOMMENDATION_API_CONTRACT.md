# Practice 推荐功能 API 与数据契约

> 状态：`implemented / scoped-browser-pass / 2026-08-30`
>
> 推荐 API 与 Practice 前端最小闭环已实现；本文件同时记录实现后的验证结果。
> 前置：Practice 第三阶段现状审计与契约冻结
> 范围：自适应出题的只读推荐契约；不包含实现、migration、后台调度或 Provider generation。

## 1. 目标与产品选择

推荐功能采用 `recommendation-first`：服务端返回可解释的候选题目建议，用户确认后通过既有 `POST /api/study/practice-sessions` 创建练习会话。推荐请求本身不创建 session、不创建 attempt、不写 mistake、不修改 plan/progress/rhythm。

本契约只冻结第一版 deterministic recommendation API。推荐不是学习事实，不作为 confirmed artifact 持久化；每次读取都基于当前 project 的正式事实重新计算。

## 2. API 总览

### 2.1 推荐列表

```text
GET /api/study/practice-recommendations
```

Query 参数：

| 参数 | 类型 | 默认值 | 约束 |
|---|---|---:|---|
| `limit` | integer | `10` | `1..20`；超界返回 `400 practice_recommendation_invalid_query` |
| `weak_point` | string | 空 | 可选，trim 后 `1..200` 字符；只作为安全的服务端筛选提示，不接受 SQL/表达式 |

不接受：`project_id`、`user_id`、`answer`、`score`、`source_revision`、`due_at`、`algorithm`、Provider/model 配置或任意排序表达式。project scope 由服务端注入。

### 2.2 确认与创建

推荐响应中的 `exercise_id` 仅作为用户确认后的输入。客户端必须调用既有接口：

```text
POST /api/study/practice-sessions
```

请求仍使用当前 `PracticeSessionRequest`：

```json
{
  "title": "复习推荐",
  "exercise_ids": ["exercise_..."],
  "duration_seconds": 600,
  "timezone": "UTC",
  "local_date": "2026-08-30"
}
```

推荐 API 不新增确认 endpoint。session 创建时必须重新验证 exercise 的 project、`ready`、题型、source 和去重约束；推荐结果过期或来源变化时，创建接口可以安全拒绝。

## 3. 响应契约

成功响应：

```json
{
  "status": "ready",
  "algorithm_version": "practice-recommendation-v1",
  "generated_at": "2026-08-30T12:00:00Z",
  "limit": 10,
  "items": [
    {
      "exercise_id": "exercise_...",
      "exercise_type": "multiple_choice",
      "prompt": "公开题目文本",
      "options": ["选项 A", "选项 B"],
      "status": "ready",
      "source_status": "valid",
      "weak_point": "主题标签或 null",
      "attempt_summary": {
        "attempt_count": 3,
        "incorrect_count": 2,
        "pending_review_count": 0,
        "last_attempt_at": "2026-08-29T10:00:00Z"
      },
      "reason_codes": ["recent_incorrect", "weak_point_match"],
      "reason_labels": ["近期答错较多", "匹配当前薄弱点"]
    }
  ]
}
```

无候选时仍返回 `200`：

```json
{
  "status": "empty",
  "algorithm_version": "practice-recommendation-v1",
  "generated_at": "2026-08-30T12:00:00Z",
  "limit": 10,
  "items": []
}
```

`generated_at` 仅标识本次读取时间，不是推荐事实的持久化时间。响应不得包含 `answer_key_json`、`answer_json`、submitted answer、grading payload、raw source text、stored path、secret 或内部 SQL/异常。

## 4. 候选池与硬过滤

候选池来自当前 project 的 `exercises`，仅允许：

1. `status='ready'`；
2. `exercise_type` 为 `multiple_choice`、`true_false` 或 `short_answer`；
3. exercise 未归档；
4. 所有关联 source 满足 current/active/ready 语义；无 source 的 user-created exercise 可以作为候选，AI exercise 必须存在可验证 citation；
5. source status 为 `valid`；`stale`、`source_deleted`、`source_unavailable` 直接排除；
6. 与服务端 project scope 一致；
7. `weak_point` 参数存在时，只保留服务端可安全匹配的 weak-point/题目标签；参数不参与原始 SQL 拼接；
8. 同一 `exercise_id` 只出现一次。

候选池过滤在排序前执行。任何候选在响应生成后发生变化，都不保证推荐仍然有效；用户确认时由 session 创建流程再次验证。

## 5. Deterministic 排序

排序必须在服务端完成，客户端不能重新排序后宣称为服务端推荐。排序键按以下顺序升序/降序固定：

1. `source_status='valid'` 优先；无 source 的 user-created exercise 作为安全可用候选，但不获得 AI source 优先级；
2. 未归档且当前可用的 exercise 优先；
3. `weak_point` 精确匹配优先（仅在请求提供 `weak_point` 时）；
4. `incorrect_count` 降序；
5. `pending_review_count` 降序，但 pending review 不能被标记为掌握；
6. `last_attempt_at` 降序；从未作答的题目排在有历史题目之后还是之前必须固定为：**从未作答优先**，用于扩大覆盖；
7. `attempt_count` 升序，用于避免只重复高频题；
8. `exercise_id` ASCII 升序作为最终 tie-breaker。

为避免规则自相矛盾，正式实现时使用两个分组：

- 第一组：从未作答的 ready 候选，按 weak-point match、exercise_id 排序；
- 第二组：已有 attempt 的 ready 候选，按 source/weak-point、incorrect_count、pending_review_count、last_attempt_at、attempt_count、exercise_id 排序；
- 返回结果先填充第一组，再填充第二组，直到达到 `limit`。

### 5.1 reason codes

第一版只允许以下安全 reason code：

| code | 用户文案 | 触发条件 |
|---|---|---|
| `never_attempted` | 尚未练习 | 没有任何 attempt |
| `recent_incorrect` | 近期答错较多 | 最近有效 attempt 为 deterministic incorrect 或人工 review incorrect |
| `pending_review` | 等待人工复核 | 存在 pending short-answer attempt |
| `weak_point_match` | 匹配当前薄弱点 | 与 query 的 weak-point 安全匹配 |
| `source_valid` | 来源当前可用 | 服务端确认 source valid |

reason code 列表去重，并按固定顺序输出：`never_attempted`、`recent_incorrect`、`pending_review`、`weak_point_match`、`source_valid`。没有额外 reason 时至少返回 `source_valid` 或 `never_attempted`。

## 6. 字段公开边界

允许返回：

- `exercise_id`；
- `exercise_type`；
- `prompt`；
- MC 的公开 `options`；
- `status`；
- 安全 `source_status`；
- 安全 weak-point 标签（若已有正式投影且不含正文）；
- count/time metadata；
- 固定 reason code 和用户文案。

禁止返回：

- `answer_key` / `answer_key_json`；
- `answer_json` / 用户答案原文；
- explanation 中未经批准的敏感正文；
- source quote/full text/path；
- provider prompt/response、模型输出或内部 ranking payload；
- 未验证的 citation identity；
- project 内部不应公开的 actor/user 字段。

## 7. 错误与边界

| HTTP | detail | 场景 |
|---:|---|---|
| 400 | `practice_recommendation_invalid_query` | limit、weak_point 或 query 结构无效 |
| 404 | `practice_recommendation_not_found` | 仅用于明确指定但不存在的未来资源；第一版 GET 不因无候选返回 404 |
| 409 | `practice_recommendation_stale` | 仅在未来显式确认资源引入版本 token 时使用；第一版不新增确认 endpoint |
| 500 | `practice_recommendation_failed` | 数据库读取或安全投影失败 |

无候选、全部 source 失效、没有足够历史数据都不是错误，返回 `status='empty'`。不得返回原始数据库/provider 错误。

## 8. 幂等、缓存与一致性

- GET 无副作用，不需要 `Idempotency-Key`；
- 第一版不持久化 recommendation，不建立 replay 记录；
- 不使用浏览器 storage；
- 允许短时 HTTP cache 的决定留给正式 API 实现，默认不设置共享缓存，避免 source lifecycle 变化造成错误建议；
- session 创建时重新验证所有推荐的 exercise ID 和 source 状态；
- delete/restore/purge/re-index 不修改历史 attempt/mistake/feedback，只影响下一次推荐读取；
- 推荐读取、session 创建、backup/restore 不触发 Provider、评分、排程或自动 repair。

## 9. 数据库与 migration 结论

第一版推荐 API：

- 不新增表；
- 不新增字段；
- 不新增 migration；
- 不新增 recommendation snapshot、algorithm event 或 schedule projection；
- 复用现有 exercises、exercise_attempts、exercise_attempt_reviews、mistake_cases、mistake_occurrences、mistake_feedback_events 和 weak-point read projection。

若后续需要保存用户确认的推荐、个性化 schedule 或解释历史，必须另立数据契约和连续 migration/rollback/backup/restore 方案，不能把 transient recommendation 写入现有 attempt/mistake 表。

## 10. 实现前验收门槛

- [x] endpoint、query、response、empty 和错误契约已冻结；
- [x] 候选池、source lifecycle 和 project scope 已冻结；
- [x] deterministic 排序、分组和 tie-breaker 已冻结；
- [x] reason code 与用户文案已冻结；
- [x] 隐私字段禁止清单已冻结；
- [x] 确认复用既有 session 创建，不新增确认 endpoint；
- [x] 明确无 schema/migration/持久化/worker 变更；
- [x] 明确失败、空结果、stale、backup/restore 和未验证边界。

只有本文件评审通过后，才能创建 API schema、repository 查询、focused backend tests 和 browser evidence。实现必须保持 `algorithm_version='practice-recommendation-v1'`，任何排序或公开字段改变都需要更新契约版本与证据。

## 11. 实现与验证记录

已实现：

- `GET /api/study/practice-recommendations`；
- 既有 `practice.html` 推荐选择工作区；
- 显式选择后复用 `POST /api/study/practice-sessions`；
- 创建的 session 保持 `draft`，不自动 start；
- 独立服务、隔离 data root 的 Browser evidence。

验证：

```text
backend/tests/test_practice_recommendations_api.py: 4 passed
backend/tests/browser_practice_recommendations.spec.js: 3 passed
backend/tests/browser_practice_workflow.spec.js: 7 passed
full backend: 426 passed, 2 skipped
full browser: 130 passed, 3 skipped
contract audit: 21 pages, 153 routes, 0 findings
source-size: passed
```

Browser 使用单 worker 串行执行；3 个 skip 均为 opt-in real-provider browser smoke。

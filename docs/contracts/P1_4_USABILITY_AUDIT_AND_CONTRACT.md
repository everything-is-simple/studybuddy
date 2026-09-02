# P1-4 可用性审计与契约（阶段 A：代码真相盘点）

> 状态：`phase-a-audited / 2026-08-31`
> 
> 本文是 P1-4 阶段 A 的审计结果，不是功能完成声明。结论严格区分 L1（存在）、L2（可达）和 L3（可复现）。本阶段没有修改 `backend/app/`，没有新增 schema、migration、endpoint 或业务功能。

## 1. 证据边界与运行记录

| 项目 | 结果 | 层次 | 证据/限制 |
|---|---|---|---|
| 后端 API/模型静态盘点 | 完成 | L1 | 扫描 `backend/app/api/*.py`、`backend/app/schemas/*.py` 与 repository 调用。下表共 153 条 `/api/**` 路由（另有 3 条 web/兼容路由）。 |
| 前端调用静态盘点 | 完成 | L2（静态） | 扫描 21 个 `backend/app/static/*.html` 以及 `static/js/api.js`、`shell.js`、`state.js`。静态对照不是浏览器实跑的替代品。 |
| focused backend | 通过 | L1 | `C:/miniconda/py310/python.exe -m pytest backend/tests/test_file_parsers.py backend/tests/test_frontend_contract_audit.py backend/tests/test_governance_consistency.py -q`：`25 passed`。 |
| focused browser | 通过 | L2（限定路径） | `npx playwright test backend/tests/browser_p1_2_plans_notes_migration.spec.js backend/tests/browser_p1_3_cards_exercises_review_migration.spec.js backend/tests/browser_static_core.spec.js --workers=1 --reporter=line`：`12 passed`。 |
| 全量 L3 重启复现 | 未完成 | L3 | 本阶段尚未对每一条已达写操作逐条执行“写入→停服→重启→页面回读”；已有专项测试证据只覆盖其声明范围，不能外推为全局 daily-usable。 |
| A4 真实文件链 | 未完成 | L1/L2/L3 | 当前仓库 fixture 可验证 parser 结构，但 `sample.pdf`、`sample.docx`、`sample.pptx` 的测试命名/内容带有 synthetic 证据；本阶段没有把它们冒充真人真实资料。 |

## 2. A1：后端 API 清单

说明：请求必填字段来自 Pydantic request model 或路径/文件参数；无 body 的 route 写“—”。稳定错误码按 handler 中的 `HTTPException/detail` 和 repository 错误映射记录；未在 handler 明确列出的校验失败统一为 FastAPI/Pydantic `422`。`Idempotency-Key` 的“是”表示 handler 明确接收并参与幂等；`自动层`表示共享前端请求层会默认补 header，但后端不一定以该键作业务幂等事实。

| Method | Path | 必填请求字段 | 响应关键字段 | 稳定错误码/校验 | Idempotency-Key | 写库 | data_root |
|---|---|---|---|---|---|---|---|
| GET | `/api/liveness` | — | status | — | 否 | 否 | 否 |
| GET | `/api/health` | — | status | — | 否 | 否 | 否 |
| GET | `/api/readiness` | — | status | — | 否 | 否 | 否 |
| GET | `/api/metrics` | — | metrics | — | 否 | 否 | 否 |
| GET | `/api/ai/capabilities` | — | llm/embedding/capture readiness | — | 否 | 否 | 否 |
| GET | `/api/materials` | query 可选：status/query/limit/offset | material list、pagination | 参数边界 | 否 | 否 | 否 |
| GET | `/api/materials/deleted` | 分页可选 | deleted material list | 参数边界 | 否 | 否 | 否 |
| POST | `/api/materials` | multipart `file` | material id/status/original_name | `invalid_filename`、`unsupported_format`、`file_too_large`、`material_persist_failed` | 自动层；业务未显式键 | 是 | 是 |
| POST | `/api/materials/batch` | multipart `files[]` | batch_id、counts、items | 同单文件逐项错误 | 自动层；业务未显式键 | 是 | 是 |
| GET | `/api/materials/{id}` | path id | material、text、warnings、spans | `material_not_found` | 否 | 否 | 否 |
| GET | `/api/materials/{id}/original` | path id | file stream | `material_not_found`、source unavailable | 否 | 否 | 读 |
| GET | `/api/materials/{id}/text` | path id | extracted text | `material_not_found` | 否 | 否 | 否 |
| PATCH | `/api/materials/{id}` | `original_name` | material | `invalid_filename`、`material_not_found`、`material_update_failed` | 自动层；未显式业务幂等 | 是 | 否 |
| DELETE | `/api/materials/{id}` | path id | 204 | `material_not_found`、`material_delete_failed` | 自动层；未显式业务幂等 | 是 | 否 |
| POST | `/api/materials/{id}/restore` | path id | material | `material_not_found`、`material_not_deleted`、`material_restore_failed` | 自动层；未显式业务幂等 | 是 | 否 |
| POST | `/api/materials/{id}/purge` | path id | purged/material_id | `material_not_found`、`material_purge_failed` | 自动层；未显式业务幂等 | 是 | 是（删除原件） |
| POST | `/api/materials/export` | `material_ids` | ZIP/file response | `export_failed`、not found | 自动层；未显式业务幂等 | 否 | 读 |
| POST | `/api/materials/{id}/ai-index` | path id；`retry` 可选 | status/index state | `material_not_found`、`retrieval_not_ready` 等 | 自动层；同步 index 未显式键 | 是 | 否 |
| POST | `/api/materials/{id}/ai-index/tasks` | path id；`retry` 可选 | task_id/status | task validation/stale codes | 是（显式接收） | 是 | 否 |
| GET | `/api/materials/{id}/ai-index` | path id | status | `material_not_found` | 否 | 否 | 否 |
| POST | `/api/retrieval` | `query`；其余可选 | hits、run_id | `retrieval_invalid_mode`、`retrieval_empty` | 否 | 条件（检索事实） | 否 |
| POST | `/api/context/assemble` | `hit_ids` | context_blocks、citations | validation/retrieval errors | 否 | 否 | 否 |
| POST | `/api/citation/validate` | `key` | valid/status/location | citation validation errors | 否 | 否 | 否 |
| GET | `/api/qa/threads` | — | threads | — | 否 | 否 | 否 |
| GET | `/api/qa/threads/{id}` | path id | messages、citations | `thread_not_found` | 否 | 否 | 否 |
| GET | `/api/qa/citations/{key}` | path key | material_id/status/start_offset/end_offset/excerpt | citation not found/lifecycle status | 否 | 否 | 否 |
| POST | `/api/qa/ask` | `question`,`material_ids` | answer_text、citations、thread_id | `qa_invalid_materials`、`retrieval_empty`、provider/idempotency errors | 是（显式接收） | 是 | 否 |
| GET/POST | `/api/study/decks[/{id}]` | POST `title`；description 可选 | deck id/status | `deck_not_found`、validation | POST 自动层；后端未统一显式接收 | POST 是 | 否 |
| GET | `/api/study/cards` | `deck_id` 可选 | cards、status、citations | — | 否 | 否 | 否 |
| GET | `/api/study/cards/{id}` | path id | card（不含 answer key） | `card_not_found` | 否 | 否 | 否 |
| POST | `/api/study/decks/{id}/cards` | `front`,`back`；其余默认；`card_type`/`citations` 可选 | card id/status | `card_invalid_state`,`citation_invalid` | 自动层；未显式接收 | 是 | 否 |
| POST | `/api/study/decks/{id}/generate` | `topic`,`material_ids` | generation/status/items | provider/retrieval/generation codes | 是 | 是 | 否 |
| PATCH | `/api/study/cards/{id}` | `front`,`back`；编辑字段 | card | card state/citation errors | 自动层；未显式接收 | 是 | 否 |
| POST | `/api/study/cards/{id}/confirm|reject|archive` | path id | card/status | `card_invalid_state`,`card_not_found` | 自动层；未显式接收 | 是 | 否 |
| POST | `/api/study/cards/{id}/reviews` | `result` | review/status | card/review validation | 自动层；未显式接收 | 是 | 否 |
| GET/POST | `/api/study/exercise-sets[/{id}]` | POST `title`；description 可选 | set id/status | set not found/validation | POST 自动层 | POST 是 | 否 |
| GET | `/api/study/exercises[/{id}]` | `set_id` 可选 | exercises；public fields | `exercise_not_found` | 否 | 否 | 否 |
| POST | `/api/study/exercise-sets/{id}/exercises` | `exercise_type`,`prompt`,`answer_key`；其余默认 | exercise id/status | set/exercise state/validation | 自动层；未显式接收 | 是 | 否 |
| POST | `/api/study/exercise-sets/{id}/generate` | `topic`,`material_ids` | generation/status/items | provider/retrieval/generation codes | 是 | 是 | 否 |
| PATCH | `/api/study/exercises/{id}` | `prompt`；options/explanation/citations；answer_key 可省略 | exercise public fields | state/citation errors | 自动层；未显式接收 | 是 | 否 |
| POST | `/api/study/exercises/{id}/confirm|reject|archive` | path id | exercise/status | `exercise_invalid_state`,`exercise_not_found` | 自动层；未显式接收 | 是 | 否 |
| GET | `/api/study/exercises/{id}/attempts` | path id | attempts public fields | `exercise_not_found` | 否 | 否 | 否 |
| POST | `/api/study/exercises/{id}/attempts` | `answer` | attempt/grading_status | attempt/state errors | 自动层；未显式接收 | 是 | 否 |
| GET/POST | `/api/study/goals[/{id}]` | POST `title`；description 可选 | goal | goal not found/state | 自动层 | POST 是 | 否 |
| GET/POST | `/api/study/modules[/{id}]` | POST `title`；description 可选 | module | module not found/state | 自动层 | POST 是 | 否 |
| GET/POST/PATCH | `/api/study/plans[/{id}]` | POST `goal_id`,`title`；PATCH fields optional | plan/items/status | plan/goal/state errors | 自动层 | 写操作是 | 否 |
| POST | `/api/study/plans/{id}/confirm|activate|pause|complete|archive` | path id | plan/status | plan state errors | 自动层 | 是 | 否 |
| POST/PATCH | `/api/study/plans/{id}/items[/{item_id}]` | POST `title`；module/deck/exercise_set optional | item/status | plan/item/state errors | 自动层 | 是 | 否 |
| POST/DELETE | `/api/study/plans/{id}/dependencies[/{dependency_id}]` | POST predecessor/successor | dependency | cycle/duplicate/not found | 自动层 | 是 | 否 |
| GET | `/api/study/plans/{id}/progress` | path id | progress/events | plan not found | 否 | 否 | 否 |
| POST | `/api/study/plans/{id}/items/{item_id}/progress` | `event_type` | progress event | progress/state errors | 自动层 | 是 | 否 |
| POST | `/api/study/modules/{id}/sources` / `...items/{item_id}/sources` | material/revision/chunk ids | source link/status | source lifecycle/link errors | 自动层 | 是 | 否 |
| GET/POST | `/api/study/sources[ /refresh]` | refresh ids optional | count/status | source lifecycle errors | 自动层 | refresh 是 | 否 |
| GET/PUT | `/api/study/plans/{id}/rhythm` | PUT cadence/timezone/period_start/target_minutes | settings | timezone/rhythm validation | 自动层 | PUT 是 | 否 |
| GET/POST/PATCH/DELETE | `/api/study/plans/{id}/rhythm/allocations[/{allocation_id}]` | POST item_id/local_date/planned_minutes | allocation | allocation/state errors | 自动层 | 写操作是 | 否 |
| GET | `/api/study/plans/{id}/rhythm/summary|export` | path id | summary/file | plan not found | 否 | 否 | 读 |
| GET | `/api/study/practice-recommendations` | limit 可选 | status/items/reasons | recommendation empty/blocked | 否 | 否 | 否 |
| GET/POST | `/api/study/practice-sessions` | POST title/exercise_ids；其余可选 | session/items/status | exercise/session validation | POST 自动层；handler未显式键 | POST 是 | 否 |
| GET/POST | `/api/study/practice-sessions/{id}[/{action}]` | submit `answer` | session/result/grading_status | session/item/state/idempotency codes | submit 显式；其它自动层 | 写操作是 | 否 |
| GET | `/api/study/practice-sessions/{id}/result` | path id | summary.score_total/total_item_count | result not found | 否 | 否 | 否 |
| GET | `/api/study/mistakes[/{id}]` | path optional | mistakes/occurrences/weak point | mistake not found | 否 | 否 | 否 |
| POST | `/api/study/attempts/{id}/review|mark-mistake` | review decision/feedback；mark feedback | review/mistake status | `review_not_allowed`,`review_duplicate` | review handler接收；mark未统一 | 是 | 否 |
| GET | `/api/study/weak-points` | — | weak points | — | 否 | 否 | 否 |
| POST | `/api/study/mistakes/{id}/feedback|redo|archive` | feedback event_kind/content；其它无 body | event/session/status | mistake state/validation | feedback/redo/archive 自动层 | 是 | 否 |
| GET/POST | `/api/study/cram-goals[/{id}]` | POST title/target_date；其余可选 | goal/status | cram validation/state | 自动层 | POST 是 | 否 |
| POST | `/api/study/cram-goals/{id}/active|completed|archived` | path id | goal/status | cram state | 自动层 | 是 | 否 |
| POST/GET | `/api/study/cram-goals/{id}/sessions[/{session_id}/result]` | POST title/exercise_ids；其余可选 | session/result | cram/session errors | 自动层 | POST 是 | 否 |
| POST/GET | `/api/study/capture-sessions[/{id}/...]` | create asset_kind/original_name/media_type；upload file；edit/action draft_id/text | capture/transcript/status | capture state、invalid_idempotency_key、provider errors | transcribe/report 显式；其它不统一 | 是 | 是（临时/媒体原件） |
| POST/GET | `/api/study/reports[/{id}/...]` | create report_kind/timezone/period；delivery channel/target_label | safe_payload/export/delivery attempts | report/delivery/provider boundary codes | create/delivery 显式 | create/delivery 是 | 否/仅适配器边界 |
| GET/POST | `/api/tasks/{task_id}[ /cancel|/retry]` | path id | public task/status | task not found/state | 自动层；后端未统一键 | cancel/retry 是 | 否 |

> 上表把高度同构的 action route 合并展示，但每个 `|` 里的独立 action 都是已扫描到的独立路由；完整逐行源码 inventory 以 `backend/app/api/*.py` 为准。A1 的主要风险不是“没有 API”，而是写操作幂等声明不统一、同步索引与任务索引并存，以及多个后端 route 没有 `/app` 调用方。

## 3. A2：前端绑定矩阵

### 3.1 逐页实际调用与响应字段

| `/app` 页面 | 实际请求（method + path） | 对应 A1 | 页面读取字段 | 结论 |
|---|---|---|---|---|
| `index.html` | 无业务 API | 无 | — | L2：只作入口/导航；首页聚合未暴露。 |
| `today.html` | GET `/api/study/plans`; GET `/api/study/plans/{id}/rhythm/summary` | 对应 | plans、items、status、source_link_status、summary | L2：可达；字段与现有响应静态对照通过。 |
| `materials.html` | POST `/api/materials` 或 `/batch`; GET `/api/materials`, `/deleted`; DELETE material; POST restore | 对应 | items、counts、id、original_name、status | L2：可达；正式页面导入/列表/回收站。 |
| `material-detail.html` | GET material/index/citation；POST index；GET original/text | 对应 | text、warnings、spans、status、citation offsets/excerpt | L2：可达；索引与引用定位均有调用。 |
| `qa.html` | GET capabilities/threads/thread；POST material ai-index、`/api/qa/ask` | 对应 | answer_text/answer、messages/content/citations、citation fields | L2：可达；请求字段含 `retrieval_mode`、`allow_retrieval_fallback`、`top_k`，与 `QaAskRequest` 对得上。 |
| `plans.html` | GET/POST/PATCH goals/modules/plans/items/dependencies/progress/rhythm/allocations；POST transitions | 对应 | id/title/status/items/source_link_status/settings/allocations | L2：可达；P1-2 focused browser 通过。 |
| `plan-detail.html` | GET `/api/study/plans/{id}` | 对应 | title/status/items/source status | L2：只读独立详情；写操作仍在 `plans.html`。 |
| `notes.html` | GET/POST/PATCH notes；POST module link/generate/refresh/confirm/reject/archive | 对应 | note blocks/modules/status/source_citation_status | L2：可达；P1-2 focused browser 通过。 |
| `note-detail.html` | GET note | 对应 | title/status/blocks/modules/source status | L2：只读独立详情。 |
| `cards.html` | GET decks/cards/detail；POST deck/card/generate/confirm/reject/archive/reviews；PATCH card | 对应 | card/deck id/title/front/back/status/citations | L2：可达；未发现旧的 `/decks/{id}/cards` 错路径。 |
| `exercises.html` | GET sets/exercises/detail/attempts；POST set/exercise/generate/confirm/reject/archive/attempt；PATCH exercise | 对应 | prompt/options/explanation/status；不读 answer key | L2：可达；创建请求明确含 `exercise_kind`，P1-3 focused browser 通过。 |
| `practice.html` | GET recommendations/sessions/mistakes/session/result；POST session/start | 对应 | items、reasons、status、summary、mistakes | L2：读取/推荐创建可达；完整逐题流程在独立页。 |
| `practice-session.html` | GET session；POST start/submit/finish | 对应 | items.prompt/options、grading_status、summary、source_warning_count | L2：可达；请求 body 为 `{answer}`。 |
| `practice-result.html` | GET session result | 对应 | `summary.score_total`、`total_item_count`、`scored_count`、`submitted_count` | L2：可达；响应嵌套字段与页面实现对得上。 |
| `review.html` | GET mistakes/detail；POST review/mark-mistake/feedback/redo/archive | 对应 | question/mistake_fact/weak_point/occurrences/source_status | L2：可达；发现风险：`reviewAttempt` 的 POST 未显式添加 `Idempotency-Key`，依赖后端是否要求；需阶段 C 台账跟踪。 |
| `capture.html` | GET capabilities/sessions/detail/transcript；POST create/upload/transcribe/edit/confirm/reject | 对应 | capture/transcript/status/source status | L2：可达；archive 控件不伪造。 |
| `classroom.html` | GET capture sessions/detail/reports/report detail/preview；少量只读 | 对应 | source_status、safe payload、report status | L2：只读课堂/报告入口；报告正式写入不由此页完成。 |
| `reports.html` | GET reports/detail；GET export（download） | 对应 | safe_payload.period/source_quality/quality_flags | L2：可达；导出是文件响应，不应按 JSON 字段解析。 |
| `tasks.html` | GET task；POST cancel/retry | 对应 | task status/progress/public fields | L2：单任务可达；没有全局列表 API，页面说明此边界。 |
| `settings-provider.html` | GET capabilities/readiness | 对应 | provider/readiness/capabilities | L2：只读；配置写入不暴露。 |
| `settings.html` | GET capabilities/readiness | 对应 | provider/status | L2：只读聚合。 |

### 3.2 静态响应漂移和错误路径

| 检查项 | 结果 | 层次 | 说明 |
|---|---|---|---|
| 不存在的 cards 路由 | 当前未发现 | L2 | `cards.html` 使用 `/api/study/cards?deck_id=...` 和 `/api/study/decks/{id}/cards`，均存在。 |
| 缺 `card_type` / `exercise_kind` | 当前静态请求已补齐默认/显式字段 | L2 | `CardRequest` 有默认 `card_type`；exercise 创建显式发送 `exercise_kind:user_created`。 |
| `practice-result` summary 漂移 | 未发现 | L2 | 页面读取 nested `summary`，与 route 输出约定一致。 |
| citation 定位字段 | 未发现静态字段缺失 | L2 | 页面读取 `material_id/status/start_offset/end_offset/excerpt`，与 citation detail 实现一致。 |
| 通用错误文案 | 存在 | L2/P1 | `sbApi.safeError` 对未知 code 回退为“请求失败，请重试”；若后端新增稳定 code 未加入映射，用户无法定位问题。 |
| review 幂等 header | 风险 | L2/L3 | review/mark 的 `mutateAttempt` 只设置 Content-Type；与全局“写操作应幂等”的 contract 不一致，尚未以重启/重复点击实跑确认。 |

### 3.3 反向清单：A1 中没有 `/app` 调用的路由

| 路由/族 | 分类 | 是否只在 `/legacy` | 判断 |
|---|---|---|---|
| `/api/retrieval`、`/api/context/assemble`、`/api/citation/validate` | 后台/组合内部 API | 否 | `qa.html` 直接调用 `/api/qa/ask`；这些是服务内部或测试级细粒度契约，不是缺陷。 |
| `/api/materials/export` | `/legacy`/兼容能力 | 是（正式 `/app` 未提供批量导出控件） | P1-4 候选缺口；后端存在但用户必须回退旧页才能完成批量导出。 |
| `/api/materials/{id}/ai-index/tasks`、`/api/tasks/{id}` cancel/retry | 后台/任务专用 | 否（`tasks.html` 仅通过 task id 读取） | 页面没有从材料索引按钮进入 task queue；不是丢失 API，但任务可见性不闭环。 |
| `/api/study/decks/{id}` | 详情后端 route | 否 | `cards.html` 通过 list/card route 工作；兼容保留。 |
| cards/exercises 的 archive/reject/generate/reviews/attempts 部分 | `/app` 已调用 | 否 | 不属于 unreachable。 |
| `/api/study/notes/{id}/blocks*`、note source link delete | 未暴露独立控件 | 否 | `notes.html` 使用 note PATCH 聚合保存；细粒度 route 是兼容/后台契约，不自动判缺陷。 |
| `/api/study/sources`、module/item source link | 部分后台/legacy | 是/部分 | `/app` 能刷新来源，但没有完整手工 source-link 工作区。属于能力缺口候选。 |
| cram-goals 全族 | legacy/后台专用 | 是 | `/app` 未调用；不等于 defect，`frontend-static-capability-matrix` 未声明正式迁移。 |
| capture archive | 明确 not_exposed | 否 | API 被固定为 invalid state；静态页不伪造按钮，符合边界。 |
| report create/delivery/delivery-attempts | CLI/后台专用及安全边界 | 否 | `/app/reports.html` 只读和导出；delivery=off，不应自行暴露。 |
| `/api/metrics`、`/api/liveness`、`/api/health` | 运维/后台专用 | 否 | 壳只读 readiness；不是用户流程缺陷。 |
| `/api/study/practice-sessions/{id}/archive` | 未在正式页面调用 | 否 | 兼容保留；practice 页面尚未提供会话归档控件。候选 P2。 |

对照矩阵：[`docs/frontend-static-capability-matrix.md`](../frontend-static-capability-matrix.md)。其 `legacy_only`/`not_exposed` 分类仅作线索，本审计以源码和后续实跑为准。

## 4. A3：持久化与重启复现

本阶段没有把既有 gate evidence 改写成全局 L3 结论。下面区分“已有局部证据”和“本次尚未验证”。

| 写操作族 | L2 状态 | 已有局部 L3 证据 | 本次结论 |
|---|---|---|---|
| 单/批量材料导入、原件/文本、删除/恢复、重启后读取 | 可达（`materials.html`） | `browser_file_import.spec.js`、`browser_material_export.spec.js` 等包含隔离 data root 和重启片段 | 局部 L3 通过；尚未覆盖混合真实资料全链。 |
| 目标/模块/计划/学习项/节奏/分配/进度 | 可达（`plans.html`） | P1-2 browser spec 真实写入；focused 12-test slice 通过 | 写后当前进程可回读；本次未重新停服/重启逐项复核，标 `L3 未独立复核`。 |
| 笔记创建/编辑/确认/拒绝/归档/模块 | 可达（`notes.html`） | P1-2 browser spec 通过 | 同上：已有专项证据，不扩大为本次全链 L3。 |
| 卡组/卡片与 review | 可达（`cards.html`） | P1-3 browser spec 通过 | 同上；重点风险是重复 review 幂等未由页面显式传键。 |
| 练习集/题目/attempt | 可达（`exercises.html`） | P1-3 browser spec 通过 | 同上；完整 session finish/redo 的重启复现未在本次执行。 |
| practice session start/submit/finish/result | 可达（practice 三页） | 既有 workflow spec 有限定 evidence | L3 未独立复核；不能据浏览器页面成功断言重启后状态正确。 |
| mistake review/feedback/redo/archive | 可达（`review.html`） | 既有 workflow evidence | L3 未独立复核；review header 风险待切片。 |
| Q&A thread/citation/index | 可达（`qa.html`/detail） | citation lifecycle/retrieval backend 测试；静态 QA focused 通过 | 后端事实有 L1，页面有 L2；“问答写入→重启→citation 跳回”完整 L3 未本次执行。 |
| capture/transcript/report | 部分可达 | Phase 9D/B 系列 scoped evidence | 受 fake/demo/provider 范围限制，不能声明普通真实资料 daily-usable。 |

**A3 当前硬结论：** 未发现已知的“成功响应后立即不写库”证据；但“每个 `/app` 写操作逐条重启回读”尚未完成，所以本审计把未覆盖项标为 `L3 未独立复核`，而不是 `durable`。

## 5. A4：文件处理链真相

代码边界来自 `backend/app/adapters/file_parsers/adapter.py`：UTF-8 `.txt/.md/.markdown`、严格 `pypdf` PDF、段落级 DOCX、slide XML 级 PPTX；解析结果包含 `text` 与 `TextSpan`。`storage.py` 按 SHA-256 hash-derived original storage 保存原件，`save_extraction` 写 extraction/text spans，索引/检索/citation 由后续 repository/API 消费。

| 扩展名 | parser 实际行为 | 已验证产出 | 层次/结论 |
|---|---|---|---|
| `.txt` | UTF-8 单 document span；空文件为 empty；非 UTF-8 为 invalid_utf8 | text、1 span、hash、SQLite text_spans | L1 通过；focused parser test 通过。 |
| `.md` | 与 text 同一 formal-text parser，不做 Markdown AST | text、document span | L1 通过；真实 Markdown 样本链尚未独立跑完。 |
| `.pdf` | `PdfReader(strict=True)`；每页一个 page span；无文字层为 empty，不做 OCR | page spans、joined text | L1 通过；当前 fixture 测试内容标 synthetic，**A4 真实 PDF 未验证**。 |
| `.docx` | ZIP 资源限制后读取 paragraph.text；复杂文本框/嵌入对象不纳入 | document span、paragraph text | L1 通过；当前 fixture 为测试样本，**真实 DOCX 未验证**。 |
| `.pptx` | ZIP 资源限制后解析 slide XML；每页一个 slide span | slide spans、joined text | L1 通过；当前 fixture 为测试样本，**真实 PPTX 未验证**。 |
| `.doc` | 明确拒绝 `requires_converter` | rejected + stable error | L1 通过；不声明支持。 |
| `.ppt` | 明确拒绝 `requires_converter` | rejected + stable error | L1 通过；不声明支持。 |
| `.rtf` | 明确拒绝 `unsupported_rtf` | rejected + stable error | L1 通过；不声明支持。 |
| `.xml` | 未列入 dispatch，走 `unsupported_format` | rejected + stable error | L1 通过；不声明支持。 |

### 5.1 链条各环节状态

| 环节 | 当前事实 | 层次 |
|---|---|---|
| 导入→原件 hash storage | `materials` + hash-derived original path；重复 hash 复用原件 | L1；材料 browser 有局部 L2/L3 |
| 解析→文本抽取 | `ParseResult.text` | L1；`.txt/.md` 及测试 fixture 有 focused 证据 |
| text span | `ParseResult.spans`，随后 `save_extraction` 写 `text_spans` | L1；focused test 通过 |
| chunk/index | AI indexing repository/API 有实现，sync `/ai-index` 与 task route 并存 | L1；QA 页面 L2；真实重启链未本次复核 |
| retrieval | `/api/retrieval` 和 `/api/qa/ask` 有实现/测试 | L1；QA 页面 L2（需 Provider/fixture 条件） |
| citation 定位回原文 | `/api/qa/citations/{key}` 返回 offsets/status；`material-detail.html` 用 offsets render body | L1 + L2；完整真实资料 L3 未本次复核 |

**A4 结论：** 代码支持的格式集合比用户直觉更窄；`.doc/.ppt/.rtf/.xml` 不可导入，PDF 图片文字不 OCR。当前没有足够证据把“真实 PDF/DOCX/PPTX 混合资料→索引→检索→citation 回原文”标成 daily-usable。

## 6. 最短可用链结论

> 当前一个用户在 `/app` 里，不碰 `/legacy`、不用命令行，能完整走通的最长路径是什么？在哪一步断掉？

**最长已被代码与限定 browser evidence 支撑的路径是：** `/app/materials.html` 导入 UTF-8 文本/已支持的测试级文件 → `/app/material-detail.html` 阅读和建立同步 AI index → `/app/qa.html` 选择材料提问 → 在问答历史看到回答与 citation → 点击 citation 返回 `material-detail.html` 的正文 offset → `/app/plans.html` 建目标/计划/学习项/节奏 → `/app/notes.html` 建用户笔记，或 `/app/cards.html`/`exercises.html` 建草稿并确认 → `/app/practice.html` 读取/创建 session → `practice-session.html` 作答 → `practice-result.html` 看结果 → `review.html` 看错题。

它在两个地方断成“限定可用”而不是 daily-usable：

1. **资料侧断点（A4/L3）：** 混合真实 PDF/DOCX/PPTX、长/重名/超大文件的“每种真实样本 + 索引 + 检索 + citation + 重启”尚未完成实证；不能把测试 fixture 和 既有 gate 通过当成全链保证。
2. **学习侧断点（A3/L3 与能力边界）：** `/app` 对常用计划、笔记、卡片、题目和限定 practice 已有可达路径，但每个写操作的重启回读没有在本次逐条复核；批量导出、完整 task 列表、cram workflow 等仍需 `/legacy` 或未暴露，不应被描述为已完成。

因此阶段 A 的状态是：**L1 大体完整，L2 主路径大体连通但存在幂等/错误文案摩擦，L3 只有分域局部 evidence；整体尚不能宣称“每天真的能用”。**

## 7. 阶段 B：真实学习流程剧本

> 阶段 B 以一个使用者的一天/一周为组织方式，而不是以 API 或页面为组织方式。每一步标注事实层：`L2` 表示页面调用已由源码和 focused browser 证据支持；`L3` 只有在写入后重启并重新打开页面验证过时才使用。本节不把静态页面通过等同于全链 real-pass。

### B1 入库：周一拿到一批资料

**输入假设：** 一批真实 PDF/DOCX/PPTX/MD，包含中文文件名、长文件名、同名不同内容、同内容不同名和一个超大文件；另准备 0 字节、损坏文件和不支持格式作异常样本。

1. 打开 `/app/materials.html`，点击“点击或拖放文件以导入”并选择多文件；预期页面显示“正在导入”，随后显示批量导入结果和每个文件的状态。`L2`：混合批量控件与 `/api/materials/batch` 已有页面/测试证据；真实 PDF/DOCX/PPTX 输入本次 `not_verified`。
2. 检查结果中的原始文件名、success/empty/rejected/failed 数量；中文名和长名应保持可识别，重复内容不同文件名应各有材料记录但共享 hash 原件。`L2/L3`：共享 hash 有后端测试，批量真实文件组合尚未完成。
3. 对 success 文件点击列表项进入 `/app/material-detail.html`，查看标题、正文和“来源/解析警告”；预期正文可读，空文件诚实显示空正文，损坏或不支持文件显示安全失败状态。`L2`：页面路径已验证；具体真实格式结果 `not_verified`。
4. 在“搜索材料”输入中文名或长文件名，点击“应用筛选”；预期列表只显示匹配项，分页可继续浏览。`L2`：materials search/pagination browser evidence 通过。
5. 对错误或超大文件确认页面不会显示路径、traceback 或原始 provider 错误，并可重新选择文件重试；对误删材料进入“查看回收站”，点恢复后回到材料列表。`L2`：失败/恢复已有局部 evidence；磁盘满、只读目录、强杀等为 `not_verified`。
6. 需要批量导出原件/文本时，当前 `/app` 没有正式控件；用户必须打开 `/legacy` 使用旧工作区导出，或使用命令行/后台接口。`L2`：`/api/materials/export` 存在但正式静态页未调用，属于当前 P0/P2 候选，不能假装已迁移。

**B1 退回边界：** `.doc/.ppt/.rtf/.xml` 当前明确拒绝；扫描 PDF、图片页 PPTX、复杂 DOCX 是否可读需要真实样本验证，不能退回 `/legacy` 后宣称 parser 已支持。批量导出必须回退 `/legacy`；Provider/真实 OCR 不通过当前 `/app` 完成。

### B2 理解：周一/周二读懂一份资料

1. 在 `/app/materials.html` 搜索并打开目标材料，进入 `/app/material-detail.html`；预期看到材料正文、解析警告和进入问答的“围绕材料提问”链接。`L2`：静态 core browser evidence 通过。
2. 点击“建立 AI 索引”或在 `/app/qa.html?material=<id>` 点击“索引当前材料”；预期显示“正在建立 AI 索引”，完成后显示“AI 索引已建立，可用于问答”。`L2`：页面调用同步 `/api/materials/{id}/ai-index`，已由静态 QA/detail 测试支持；task queue 路径不是同一条链。
3. 在问答页确认 Provider 状态，再在“你的问题”输入问题，材料范围填写目标材料 ID，保留“混合检索（推荐）”，点击“提交问题”；预期看到“回答已生成”，问题出现在问答历史。`L2`：`qa.html` browser focused evidence 通过；Provider 未配置时应看到安全不可用提示。
4. 展开问答历史中的线程，查看回答文本和“引用来源”；预期 citation 至少包含材料名称/位置，失效来源显示“来源不可用”且不可点击。`L2`：页面读取 `messages`/`citations`，citation lifecycle 有后端 evidence。
5. 点击有效 citation；预期跳回 `/app/material-detail.html?material=...&citation=...`，正文中按 `start_offset/end_offset` 定位并显示“已定位引用来源”。`L2`：代码链与 citation detail 测试存在；真实混合资料定位仍 `not_verified`。
6. 对照引用高亮/摘录与原文，确认引用落在原文而非仅凭回答推断；若来源已删除、purge 或不可用，预期页面明确显示降级状态而不是恢复正文。`L2`：生命周期规则已存在；完整用户可视重启后复核为 `not_verified`。

**B2 退回边界：** 当前 `/app` 已有问答与 citation 的页面入口，不需回退 `/legacy`；但 Provider 配置写入/密钥保存没有公共契约，必须由受支持的外部配置/运维方式完成。真实 Provider、扫描件 OCR 和跨时区/断网中的问答为 `not_verified`，不能用 fake/demo evidence 替代。

### B3 产出：周二/周三把资料变成可复习内容

1. 打开 `/app/cards.html`，在“新卡片组名称”输入名称，点击“创建卡片组”；预期左侧列表出现卡片组。`L2`：P1-3 browser evidence 通过。
2. 选中卡片组，在“问题”“答案”填写内容，点击“创建卡片”；预期卡片出现在列表，详情只显示公开字段。`L2`：创建请求与现有 `CardRequest` 对齐；answer key 隐私边界有测试。
3. 选择卡片，修改问题/答案，点击“保存卡片”；预期显示“卡片已保存”，列表标题更新；点击“确认卡片”后预期显示“卡片已确认”。`L2`：P1-3 focused browser 通过。
4. 若 Provider 和来源满足条件，在卡片组中填写“AI 草稿主题”和材料 ID，点击“生成卡片草稿”；预期生成 draft，先编辑再确认，不应直接成为 confirmed。`L2`：请求路径存在；真实 Provider 生成流程受配置边界限制，`not_verified`。
5. 打开 `/app/exercises.html`，创建练习集；选中练习集，填写题型、题面和答案，点击“创建题目”；预期题目进入草稿/可编辑状态。`L2`：P1-3 browser evidence 通过；创建 body 含 `exercise_kind`。
6. 编辑题目内容/解析，点击“保存题目”，再点“确认题目”；预期显示保存/确认状态，页面和 DOM 不出现 `answer_key`。`L2`：P1-3 privacy evidence 通过。
7. 对 ready exercise 点击“开始作答”，进入 `/app/practice.html`；选择或创建练习会话后进入 `/app/practice-session.html`，点击“开始练习”，逐题填写/选择答案并点击“提交答案”；最后点击“完成会话”，进入 `/app/practice-result.html` 查看得分与提交统计。`L2`：页面链与既有 workflow evidence 存在；本次没有重新做逐写操作重启复现。
8. 当前仅卡片/题目创建、编辑、确认和限定复习路径由 `/app` 有 focused evidence；需要完整生成、练习会话管理或旧 cram 工作区时，按实际能力可能需回退 `/legacy`，Provider 配置则必须走外部配置/命令行边界。`L2`：以阶段 A 实测为准，不以矩阵文字推断。

### B4 纠错：周三/周四处理一次错误

1. 在 `/app/practice-session.html` 提交一个错误答案并完成会话；预期确定性题目产生可评分结果，简答题显示“答案已提交，等待复核”。`L2`：session 页面读取 `grading_status`；真实短答人工复核需实际输入验证。
2. 打开 `/app/review.html`，等待错题列表加载；预期看到题面、错误原因、薄弱点和来源状态，来源失效时显示“来源已删除/来源不可用”。`L2`：review browser evidence 通过。
3. 点击“查看详情”，在详情中填写反馈；点击保存/提交反馈；预期显示“复盘反馈已保存”，错题事实仍保留而不是被覆盖。`L2`：后端 append-only 契约和页面调用存在；review 写请求幂等 header 风险仍未修复。
4. 点击“再次练习”；预期创建新的练习会话并可进入练习，不修改旧 attempt 的答案或评分事实。`L2`：页面有 redo 调用和局部 evidence；L3 重启后新 session 回读本次未验证。
5. 若错误已被处理，点击“归档”；预期列表显示归档状态，归档错题不能继续产生新的反馈事实。`L2`：API/页面路径存在；状态转换全链尚未逐项实跑。
6. 需要人工复核 short-answer 时，进入错题详情并执行“正确/错误/不确定”决策；预期只有 `incorrect` 形成错题投影，`uncertain` 不显示为已掌握。当前控件与重复提交保护需单独验证，标 `P1/L2` 风险。

**B4 退回边界：** 当前 review 页面已覆盖读取、详情、反馈、redo、archive 的限定路径，不需因普通错题查看回退 `/legacy`；完整 practice/cram 操作和人工简答复核的可靠重复提交若页面实跑失败，则只能回退旧工作区或命令行，并应记录为缺口而非默认为可用。

### B5 节奏：周四建立一周计划并每天执行

1. 打开 `/app/plans.html`，在目标表单输入目标名称，点击“创建目标”；在模块表单输入模块名称，点击“创建模块”；预期两侧列表出现目标和模块。`L2`：P1-2 browser evidence 通过。
2. 输入计划名称并选择目标，点击“创建计划草稿”；选中计划后在计划详情编辑标题/描述，点击“保存计划编辑”；预期状态为草稿且内容保持。`L2`：P1-2 browser evidence 通过。
3. 点击“添加学习项”，填写标题并选择模块，点击“添加学习项”；如有两个学习项，选择前置/后继并点击“添加依赖”；预期列表出现学习项、模块和依赖关系。`L2`：页面调用字段与 `StudyPlanItemRequest`/`StudyDependencyRequest` 对齐。
4. 在“学习节奏”中选择每日/每周，填写时区、起始日、目标分钟，点击“保存节奏设置”；再填写日期和分钟，点击“添加分配”；预期显示保存成功和分配记录。`L2`：P1-2 browser evidence 通过；午夜、改系统时区和跨天结果 `not_verified`。
5. 点击“确认草稿”“激活计划”，打开 `/app/today.html`；预期今天页面读取计划节奏摘要和计划项，显示今天要做的学习项及来源状态。`L2`：today 页面读取 `/rhythm/summary`，空计划也应诚实显示空状态。
6. 完成学习项后回到 `/app/plans.html`，在对应学习项点击“完成学习项”；预期进度保存并可重新加载。`L2`：页面调用 progress route；重启后进度回读本次未独立验证。
7. 一周后再次打开 `/app/today.html` 与计划详情，比较已完成项、分配分钟和计划状态；预期能看到变化。当前缺少一项正式的周视图/趋势聚合证据，故“看得出变化”只能标 `L2/P2` 候选，不能从单日摘要推断。

**B5 退回边界：** 目标、模块、计划、学习项、节奏与 today 的基础路径可在 `/app` 完成；完整周趋势、全局计划筛选/排序、批量操作未暴露。Provider 配置写入、全局任务列表和未迁移 cram workflow 不应由页面伪造，必要时走命令行/旧工作区或保持 `not_exposed`。

## 8. 阶段 B 总结与停止条件

| 主线 | `/app` 当前可走到的最远步骤 | 明确断点 | 层次 |
|---|---|---|---|
| 入库 | 导入、搜索、详情、解析状态 | 真实复杂文件链与批量导出 | L2 已有；A4/L3 `not_verified` |
| 理解 | 索引、提问、回答、citation、正文定位 | 真实 Provider/复杂文件/重启后 citation 全链 | L2 局部；L3 `not_verified` |
| 产出 | 卡片/题目草稿、编辑、确认、限定作答结果 | 完整生成与 session 重启复现、Provider 配置 | L2 局部；L3 `not_verified` |
| 纠错 | 错题读取、详情、反馈、redo、archive | review 幂等与全链重启复现 | L2 局部；L3 `not_verified` |
| 节奏 | 目标、模块、计划、节奏、today、进度 | 跨天/时区/周变化可视化和重启逐项验证 | L2 局部；L3 `not_verified` |

**阶段 B 结论：** `/app` 已能把多个领域的局部路径连接起来，但“一个真人照着做一周”仍被三类证据缺口限制：真实格式输入真实性、每个写操作的进程重启复现、以及明确 deferred/not_exposed 能力。下一步必须把这些观察合并成 P0/P1/P2/P3 缺口台账，不能直接开始修复。

按任务约定，阶段 B 已完成；现进入阶段 C，整理缺口台账，不直接开始修复。

## 9. 阶段 C：缺口台账与排序

> 排序原则：P0 是主线阻断、数据不持久或基本操作必须离开 `/app`；P1 是已经能走通但会造成误解、重复操作风险或失败后无法定位；P2 是明确缺少但不阻断当前最短链；P3 是本任务明确不做或需要独立安全/产品立项的事项。每条都标注事实层，避免把 L1 存在误写成 L2/L3 通过。

### 9.1 P0 阻断

| ID | 现象 | 层 | 影响剧本步骤 | 分级 | 修复动作 | 验证方式 |
|---|---|---|---|---|---|---|
| P14-P0-01 | 真实混合资料（尤其复杂 DOCX、图片/扫描 PDF、图片页 PPTX）尚未证明能完成解析→索引→检索→citation 回原文；当前 gate fixture 不能代表真实输入。 | L2/L3 | B1-1~B1-5、B2-1~B2-6 | P0 | 先建立真实、脱敏、可重复的样本与验收剧本；只修复被实测证明的 parser/链路断点，不扩大格式承诺。 | 隔离 data root；逐种真实文件执行导入、详情、索引、检索、citation 定位；记录每环产出和失败码；停服重启后重新打开页面。 |
| P14-P0-02 | `/app` 没有批量材料导出控件，用户完成入库后若要导出一批原件/文本必须回退 `/legacy` 或使用后台接口。 | L2 | B1-6 | P0 | 若确认批量导出属于基本日常链，在不改已有 export contract 的前提下迁移一个正式 `/app` 操作入口；否则把该边界明确降为 P2/兼容能力。 | Playwright 从 `/app/materials.html` 选择多项并导出；验证 ZIP 内容、失败重试、隐私边界及重启后的材料可导出。 |
| P14-P0-03 | `/app` 领域写操作虽有局部 browser evidence，但本次没有覆盖每个已达写操作的“写入→停服→重启→页面回读”；整体不能证明每天使用的数据状态可复现。 | L3 | B1-2、B2-6、B3-3~B3-7、B4-3~B4-5、B5-6~B5-7 | P0 | 建立按写操作族拆分的重启验收矩阵；发现实际丢失或状态错乱后，只修复对应最小边界。未发现问题前不得为了“补测试”改业务代码。 | 每族使用独立临时 data root，启动两次服务；第二次通过对应 `/app` 页面读取 id/title/status/source status/progress/result；记录 `durable` 或 `NOT_DURABLE`。 |
| P14-P0-04 | `/app` 的完整理解链对真实 Provider、真实格式和 source lifecycle 的组合没有一次完整 real-pass；回答成功不等于 citation 真定位、重启后仍可读。 | L2/L3 | B2-2~B2-6 | P0 | 先做真实 Provider/测试替身的链路验收；若断点是页面字段漂移或路由错误，再做最小修复；不以 fake/demo 结果扩大声明。 | 真实或明确标注的 Provider 配置下，索引→提问→线程→citation→原文 offset；删除/purge 后检查 `source_deleted/source_unavailable`；重启复读。 |
| P14-P0-05 | 同内容不同文件名的第二个材料无法建立索引：`/api/materials/{id}/ai-index` 与 `/ai-index/tasks` 固定返回 `400 revision_fingerprint_conflict`，该材料因此无法用于检索/问答/citation（`/api/qa/ask` 返回 `409 retrieval_not_ready`）；删除第一个材料不释放指纹，只有 purge 才释放。 | L2/L3 | B1-2、B2-2~B2-6 | P0 | 需要单独决定 revision 指纹契约：要么改为每材料一条 revision（涉及连续 migration 与回滚），要么在导入层明确共享 revision 并保证两份材料可检索。C0 已把当前真相固定为测试，不在 C0 内改行为。 | 已有：`test_shared_hash_second_material_cannot_be_indexed_today`。修复时需补：migration/rollback、两份材料各自可检索与 citation 定位、重启复读、backup/restore 不自动修复。 |

### 9.2 P1 摩擦与可靠性风险

| ID | 现象 | 层 | 影响剧本步骤 | 分级 | 修复动作 | 验证方式 |
|---|---|---|---|---|---|---|
| P14-P1-01 | `review.html` 的 `reviewAttempt` 与 `markAttempt` 请求只设置 `Content-Type`，没有显式 `Idempotency-Key`；快速重复点击时的服务端幂等语义未确认。 | L2/L3 | B4-3、B4-6 | P1 | 对照后端现有 review/mark contract，补齐或明确幂等策略；不得改变 URL、method、状态码或响应字段。 | Playwright 监听请求确认 header；双击/并发触发只产生一个事实；失败后重试不重复写 review/mistake；后端 focused test。 |
| P14-P1-02 | 页面写操作成功后多依赖局部刷新或重新加载；快速切页、刷新中途和返回键的 stale response 虽有部分 generation guard，但没有逐页全覆盖。 | L2/L3 | B3-3~B3-7、B4-2~B4-5、B5-2~B5-6 | P1 | 逐页补齐请求代次、取消和成功后目标列表/详情的一致刷新；只修复实测 stale 更新，不做无关前端重构。 | Playwright 快速连续选择、点击、reload、返回；断言旧响应不覆盖新选择，成功状态和列表最终一致。 |
| P14-P1-03 | 未知后端错误码在 `sbApi.safeError` 中统一显示“请求失败，请重试”，用户无法知道是来源失效、状态冲突、Provider 超时还是输入错误。 | L2 | B1-5、B2-2、B2-6、B3-3、B4-3、B5-2 | P1 | 盘点实际稳定错误码，补充安全、用户可理解的映射；未识别 code 仍不得暴露 raw provider/traceback/path。 | API failure fixture + browser assertions：每个已批准 code 显示对应文案；未知 code 显示安全通用文案；DOM 无敏感信息。 |
| P14-P1-04 | 来源状态在不同页面使用 `source_status`、`source_link_status`、`source_citation_status` 等多个字段名。**C0 已实测确认**：计划学习项响应没有任何来源状态字段（只存在于 `source_links`），因此 `plans.html` 与 `today.html` 在来源已删除时仍显示“来源有效”；`not_indexed` 在 `state.js` 也无文案。 | L2 | B1-3、B2-4~B2-6、B3-3、B4-2、B5-5 | P1 | 不改既有响应字段名；让页面从 `source_links` 正确映射到学习项，并补齐缺失的状态文案。 | 对 valid/stale/source_deleted/source_unavailable/pending_review fixtures 逐页断言文案、禁用链接和安全降级；现有基线：`test_plan_item_source_state_lives_on_source_links_not_items`。 |
| P14-P1-05 | 解析结果对用户不够可解释：PDF 无文字层、DOCX 复杂对象未提取、PPTX 图片页等情况虽有 warning/empty 语义，但没有通过真实样本确认页面是否足够指导下一步。 | L2 | B1-3、B2-1~B2-6 | P1 | 以真实样本为依据改善安全提示和下一步操作指引；不把提示改成虚假的成功。 | 真实文件浏览器验证；断言 warning、empty、rejected、failed 的可读性和可重试性。 |
| P14-P1-06 | `materials.html` 的文件选择 accept 列表包含 `.doc`，但 parser 明确以 `requires_converter` 拒绝；用户会误以为该格式受支持。 | L2 | B1-1、B1-3 | P1 | 让文件选择提示与实际 parser contract 一致，或明确显示“旧格式需转换”；不得静默改变后端支持范围。 | 页面 accept/帮助文案与 `.doc/.ppt/.rtf/.xml` 实测结果一致；浏览器上传显示稳定拒绝码。 |
| P14-P1-07 | 练习生成、Provider 未配置、AI 超时、来源失效等场景有安全错误边界，但真实用户能否从页面判断“可重试/需配置/需换材料”尚未形成统一反馈。 | L2 | B2-2、B3-4、B4-1、B5-1 | P1 | 统一按稳定错误码提供“重试/配置/更换来源”的动作语义；不暴露 Provider 原始响应。 | route fixture + Playwright：失败后控件恢复可用、重试不重复写入、错误文案安全且可操作。 |

### 9.3 P2 明确缺失

| ID | 现象 | 层 | 影响剧本步骤 | 分级 | 修复动作 | 验证方式 |
|---|---|---|---|---|---|---|
| P14-P2-01 | `/app` 没有批量导出正式入口（若 P0-02 经评审不视为基本链，则在此保留）。 | L2 | B1-6 | P2 | 迁移现有 `/api/materials/export` 到正式页，复用既有 ZIP/隐私 contract。 | `/app` 多选导出 browser spec + export backend regression。 |
| P14-P2-02 | `tasks.html` 只有已知 task id 的读取、取消、重试，没有全局任务列表、筛选和排序。 | L2 | B1-1、B2-2 | P2 | 先冻结全局 task-list 公共 contract，再实现页面；不得用前端扫描或 mock 伪造列表。 | 新 contract 的 API 输入边界、分页/筛选、页面空/失败/重试和真实 task 流程。 |
| P14-P2-03 | `/app` 没有完整手工 source-link 工作区；模块/学习项的 source linking 主要依赖上下文或后端细粒度 route。 | L2 | B2-6、B5-3 | P2 | 明确 source link 的用户场景和安全字段后再接正式控件；复用 revision/chunk/span/citation contract。 | 页面创建/删除 link 后刷新、来源生命周期刷新、无越权材料/路径泄露。 |
| P14-P2-04 | cram-goals / cram sessions 仍无正式 `/app` 页面；当前普通 practice 路径不能代表冲刺学习工作流。 | L2 | B3-7、B4-4 | P2 | 单独立项迁移 cram workflow，冻结页面/状态/幂等/隐私 contract。 | `/app` 完整 cram browser path、重启回读、错误/过期/来源生命周期。 |
| P14-P2-05 | 一周后“看得出变化”缺少正式周趋势/聚合视图；`today.html` 主要是当天摘要。 | L2 | B5-7 | P2 | 在不新增 schema 的前提下评估现有 progress/report 聚合是否足够；若需新公共数据，另立 contract。 | 跨天、跨时区、改系统时区、周起止边界和历史数据增长 browser/API evidence。 |
| P14-P2-06 | 资料页没有面向用户的批量结果筛选/排序、失败项重试队列和大批量导入进度视图。 | L2 | B1-1、B1-2、B1-5 | P2 | 先用真实规模基线确认是否达到摩擦阈值，再设计不新增 schema 的页面能力。 | 真实资料数量增长、页面加载时间、失败重试、重复点击和取消行为测量。 |
| P14-P2-07 | Provider 配置写入、密钥保存和连接测试没有获批的安全公共契约。 | L1/L2 | B2-2、B3-4 | P2（当前保持不暴露） | 不在本任务实现；若重新立项，必须先冻结密钥边界、存储、验证、日志脱敏和备份规则。 | 安全 contract、密钥不进 DOM/URL/log/backup artifact、连接测试失败边界和重启验证。 |

### 9.4 P3 不做或保持 not_verified

| ID | 现象/需求 | 层 | 影响剧本步骤 | 分级 | 修复动作 | 验证方式 |
|---|---|---|---|---|---|---|
| P14-P3-01 | Windows ACL/只读目录、磁盘满、真实断电、网络盘、文件系统损坏。 | L3 | B1、B2、B5 | P3 | 保持 `not_verified`；若需支持，单独提出部署/故障恢复立项。 | 专项环境和破坏性演练；本任务不假装覆盖。 |
| P14-P3-02 | 多进程/多 worker 共享 data_root、云同步、多用户部署、生产规模容量。 | L1/L3 | 全部 | P3 | 保持单进程、单实例、本地磁盘边界；不得扩展声明。 | 架构评审和独立容量/部署项目。 |
| P14-P3-03 | 通用真实 OCR/ASR 能力、所有语言/模型/硬件环境。 | L1/L2 | B1、B2 | P3 | 本任务只记录真实样本结果；B1/B2 已有 scoped evidence 不扩大为通用 real-pass。 | 每种 provider/model/语言另立验收；当前保持 `not_verified`。 |
| P14-P3-04 | 真实对外交付、SMTP/Feishu 通用兼容、系统级读屏器兼容。 | L1/L2 | B2、B5 | P3 | 保持 `delivery=off` 与现有 scoped boundary；读屏器另立无障碍项目。 | 独立授权、适配器和无障碍测试；本任务不改 delivery。 |
| P14-P3-05 | 自动 scheduler/worker、提醒、推送、日历同步、自动修改计划/节奏/进度。 | L1 | B5-4~B5-7 | P3 | 按既有 practice contract 明确不做；只保留显式页面操作。 | 代码/路由审计确认无后台自动调度；不新增 schema 或 worker。 |
| P14-P3-06 | 桌面化、前端框架迁移、业务 schema 扩张。 | L1 | 全部 | P3 | 本任务明确禁止；若未来需要，另立架构/迁移项目。 | 治理测试、source-size、migration review；本阶段不实现。 |

## 10. 阶段 C 排序结论与建议切片

台账建议按以下顺序进入阶段 D，但本节不是授权实现；每个切片仍需单独确认，并遵守“一次一个切片、一次一个提交”：

1. **C0 证据补齐切片（优先 P0-P0-01/P0-03/P0-04）：** 不先改业务代码，建立真实文件、真实输入和逐写重启矩阵；把每个结果明确为 `L1/L2/L3`、`durable`、`NOT_DURABLE` 或 `not_verified`。如果证据证明存在断点，再按最小范围修复。
2. **C1 幂等与反馈切片（P14-P1-01/P1-02/P1-03）：** 先处理 review/mark-mistake 的重复点击风险，再收口 stale response 和稳定错误码映射；必须保留现有 API contract。
3. **C2 来源与解析可解释性切片（P14-P1-04/P1-05/P1-06）：** 以真实文件结果为依据统一状态显示和文件格式提示。
4. **C3 `/app` 批量导出切片（P14-P0-02 或 P2-01）：** 只有确认它是基本日常链后才按 P0 处理；否则排到 P2。
5. **C4 规模与完整工作流切片（P14-P2-02~P2-06）：** 需要各自 contract 和真实规模/跨天证据，不与可靠性修复混合。
6. **P3 项目：** 不进入本任务阶段 D。

### 阶段 C 停止条件
- 阶段 A、B 问题已合并为单一台账；
- 每项具有 ID、现象、事实层、剧本步骤、分级、修复动作和验证方式；
- `UNREACHABLE` 已区分兼容保留、后台/CLI 专用、deferred 和 not_exposed；
- P0/P1/P2/P3 已排序，并明确 P0-02 的分类取决于“批量导出是否属于基本日常链”的产品确认；
- 未修改 `backend/app/`，未新增 schema/API，未进入阶段 D。

按任务约定，阶段 C 已完成。

## 11. 阶段 D 进展

| 切片 | 状态 | 说明 |
|---|---|---|
| C0 真实输入与重启复现证据补齐 | `implemented + scoped real-pass` | 不修改 `backend/app/`；新增 `test_p1_4_real_input_chain.py`、`test_p1_4_restart_durability.py`、`browser_p1_4_real_input_restart.spec.js`。真实 PDF/DOCX/PPTX/MD/中文长名 TXT 全链已实测；`/app` 主要写操作族重启后均 `durable`；新发现 P14-P0-05。证据：[`../evidence/P1_4_USABILITY_CLOSEOUT_EVIDENCE.md`](../evidence/P1_4_USABILITY_CLOSEOUT_EVIDENCE.md)。 |
| C1 幂等与反馈 | 未开始 | P14-P1-01/P1-02/P1-03 |
| C2 来源与解析可解释性 | 未开始 | P14-P1-04/P1-05/P1-06，C0 已固定具体事实 |
| C3 `/app` 批量导出 | 未开始 | P14-P0-02 或 P2-01 |
| C4 规模与完整工作流 | 未开始 | P14-P2-02~P2-06 |
| P14-P0-05 revision 指纹修复 | 待单独决策 | 需连续 migration 与 API 决定，不得在可用性切片中附带完成 |

# Phase 10-1 Operation/Task 正式契约与状态机

> 状态：`planned/contract-frozen`（Gate B：通过）  
> 前置：Phase 10-0 `planned/audit-draft`，Gate A `scoped go`  
> 当前基线：schema v13；10-2 已落实最小 task/attempt schema，尚未实现 task runner 或业务接入。

## 1. 契约目标

Phase 10 将“业务操作记录”和“执行任务”分成两个概念：

- **Operation**：某次有业务含义的请求或副作用审计记录，例如一次 Q&A、卡片生成、embedding indexing 或课堂转写；保留现有 `ai_operations` 作为兼容的 operation 审计事实。
- **Task**：一次由本地执行器调度、执行、汇报进度和恢复的执行 envelope。一个逻辑 operation 最多绑定一个当前 task；一次 task 可以有多个显式执行 attempt。

这样既不破坏既有同步 API 和 Phase 4–9 的 operation 记录，又允许 Phase 10 将明确批准的长操作接入 runner。Task 不是新的业务 source of truth，不得覆盖材料、用户编辑、确认状态、attempt 或报告事实。

## 2. 现状审计与兼容结论

### 2.1 当前 `ai_operations` 实际能力

当前 `ai_operations` 正式表由 `backend/app/migrations/runner.py` v2/v3/v4/v12 逐步建立和扩展，已有字段包括：

- identity：`id`、`operation_type`、`project_id`；
- source/scope：`material_id`、`thread_id`、`source_revision`、Phase 9D 的 `capture_session_id`；
- 幂等与输入：`input_fingerprint`、`idempotency_key`；
- 运行状态：`status`、`retry_count`、`created_at`、`started_at`、`finished_at`、`error_code`；
- provider/结果审计：`provider_id`、`model_id`、`provider_request_id`、token/latency/finish metadata、`output_artifact_id`、`retrieval_run_id`、prompt/retrieval version。

当前状态 CHECK 是：

```text
queued | running | succeeded | failed | cancelled | stale
```

实际使用证据：

- Q&A：`backend/app/repository.py:create_qa_request` 创建 `qa_answer` operation 为 `running`；`persist_qa_answer` 成功收口；`fail_qa_operation` 失败收口；`reclaim_stale_qa_operations` 通过请求触发过期租约回收。
- Cards/Exercises：`create_generation_operation` 创建 `generate_card`/`generate_exercise`，失败由 `fail_generation_operation` 收口，成功将 draft 与 operation 原子关联。
- Notes：`create_note_generation_operation` / `generate_note_draft` 使用 `generate_note`，保持 draft 和 citation 保护。
- Embedding：`create_embedding_index_operation` 创建 `embedding_index` 为 `running`；`finish_embedding_index_operation` 只允许成功/失败/stale 收口；`reclaim_stale_embedding_operations` 为显式调用的过期检查。
- S7：`create_transcription_operation` / `complete_transcription_operation` / `fail_transcription_operation` 使用 `class_capture_transcription`，raw provider response 不持久化，结果为 draft/confirmed 需显式处理。
- S6 delivery：交付事实在 `report_delivery_attempts`，不是 `ai_operations`；当前 delivery 默认 off，dry-run，不做真实发送。

### 2.2 当前明确不存在的能力

- 没有统一 task 表、task handler registry 或后台执行循环；
- 没有统一 progress、stage、heartbeat、lease owner 或 cancel request 字段；
- 没有独立后台 stale 扫描；已有 stale reclaim 是 Q&A/embedding 的请求或显式调用路径；
- 没有跨进程协调、多 worker 共享 `data_root` 或真正的 Provider HTTP 强制取消；
- operation 主要在 HTTP 请求内同步执行，不能据此宣称长任务可恢复；
- report snapshot 创建是只读聚合，不自动触发 delivery；delivery 没有后台调度。

证据入口：`backend/app/main.py:lifespan`、`backend/app/main.py:create_app`、`backend/app/observability.py`、`backend/app/repository.py` 上述函数以及 `backend/tests/test_ai_indexing.py`、`test_qa_api.py`、`test_phase8_generation.py`、`test_phase9b_notes.py`、`test_phase9d_capture.py`、`test_phase9d_delivery.py`。

### 2.3 兼容策略冻结

1. 既有 `ai_operations` 保留，不在 10-1 删除、重命名或改变既有字段语义。
2. 既有历史 operation 不强制回填为 task；没有 task 记录的历史 operation 仍按原有查询、backup/restore 和 source lifecycle 语义读取。
3. 新 runner-backed operation 使用 task 执行层；10-2 v13 已通过 `operation_tasks.operation_id`（每 operation 最多一个 task）及 project-scoped composite FK 固化关联，历史 operation 不回填。
4. 既有同步 API 只有在 10-4 对某一 operation 明确批准后，才允许返回 task handle 或改为排队；没有批准的 endpoint 保持同步行为。
5. 既有 `stale` 只表示该 operation 的当前执行事实失效或租约过期，不自动等价于成功、失败可重试或 artifact 可用；具体 retryability 由 operation policy 决定。
6. 旧 operation 的 `retry_count` 保留其现有含义；统一 task attempt 计数不得静默覆盖旧历史。迁移时必须明确旧字段到新字段的映射。

## 3. 统一身份与 scope

### 3.1 Identity

- `operation_id`：现有业务 operation ID；可安全出现在受限 API 响应、UI 状态和日志关联中。
- `task_id`：未来 runner task 的稳定 ID；一个逻辑任务在 retry 时保持不变，attempt 使用独立序号/记录。
- `attempt_id`：一次实际执行尝试的 ID；Provider/handler 每次产生外部或高成本副作用时必须能够关联到 attempt。
- `parent_task_id`：可选的非敏感父任务 ID，用于明确的任务分解；子任务不能越过父任务的 project scope。
- `request_id`：HTTP 请求关联 ID，仅用于 correlation；不是任务身份，不保证跨重启持久可用。

ID 必须是不透明、不可猜测的系统生成值。API/UI 不返回 input fingerprint、内部锁 token、数据库路径或任意 raw payload。

### 3.2 Scope 和 owner

每个 task 必须绑定一个 `project_id`，由服务端注入，不信任客户端传入的 project scope。task 只能读取和写入同一 project 允许的 source/artifact；跨 project、跨 capture、跨 material 的引用必须在 domain 层拒绝。

`owner` 表示逻辑来源（例如 `api`、`operator`、`runner`），不是用户认证身份。当前本地 v1 没有多用户认证；不得把 owner 字段扩展解释为授权系统。

## 4. Task 状态机

### 4.1 状态集合

统一 task 状态冻结为：

```text
queued
running
cancel_requested
succeeded
failed
cancelled
stale
```

说明：

- `queued`：已持久化、等待当前进程的 runner 获取；尚未执行副作用。
- `running`：某个 attempt 已取得执行权并定期更新 lease。
- `cancel_requested`：已收到合法取消请求；runner 会在安全检查点处理。不是强制中断保证。
- `succeeded`：最终业务结果已原子持久化，且 operation/artifact 状态一致。
- `failed`：本次逻辑任务以稳定 error code 失败；只有 policy 允许时才可显式 retry 回到 queued。
- `cancelled`：任务未产生未声明的最终副作用，并已安全停止；不能作为成功或失败的别名。
- `stale`：执行租约失效、进程停止或恢复检查发现该执行不再可信；不能自动提升为 succeeded。

`cancel_requested` 是非终态；其余六类中 `succeeded`、`cancelled`、`stale` 是终态，`failed` 是可终止也可按显式 retry 重新排队的状态。最终 task 是否允许 retry 必须由 operation policy 和错误码共同决定。

### 4.2 合法转换

| 当前状态 | 允许的目标状态 | 触发条件 | 必须条件 |
|---|---|---|---|
| `queued` | `running` | runner 原子领取 | 创建 running attempt，取得 lease |
| `queued` | `cancelled` | 排队取消 | 未执行 handler，无外部副作用 |
| `running` | `cancel_requested` | 显式取消 | 只设置请求，不伪造已停止 |
| `running` | `succeeded` | handler 成功 | artifact/source/user state 与 operation 原子一致 |
| `running` | `failed` | 稳定不可恢复或耗尽 retry | 写安全 error code，关闭 attempt |
| `running` | `cancelled` | handler 在安全点确认取消 | 证明无未提交副作用 |
| `running` | `stale` | lease 过期/进程恢复判定失效 | 保留审计，不提升 artifact |
| `cancel_requested` | `cancelled` | 安全点完成 | 不得声称强制取消 Provider HTTP |
| `cancel_requested` | `succeeded` | handler 已不可逆完成且结果已原子提交 | 取消请求不能回滚已提交结果，记录 late cancel |
| `cancel_requested` | `failed` | 取消期间发现稳定失败 | 保留真实失败 code |
| `cancel_requested` | `stale` | lease 过期 | 依旧不得提升为成功 |
| `failed` | `queued` | 用户/operator 显式 retry 且 policy 允许 | retry_count/attempt 递增，幂等副作用受保护 |
| `stale` | `queued` | 用户/operator 显式 reclaim/retry 且 policy 允许 | 必须确认旧 attempt 不再持有执行权 |

未列出的转换一律拒绝并返回稳定错误：`task_invalid_state_transition`。尤其禁止：

- `succeeded`、`cancelled`、`stale` 直接回到 `running`；
- 终态被普通 update 覆盖；
- `failed` 或 `stale` 无显式 retry 自动重跑；
- restore/startup 自动将 `stale`/`failed` 改为成功；
- cancel 请求直接把 `running` 改成 `cancelled` 而不经过 handler 安全点。

### 4.3 Operation 与旧状态的映射

旧 `ai_operations.status` 映射到统一 task 语义时：

| 旧 operation status | task 只读兼容含义 |
|---|---|
| `queued` | `queued` |
| `running` | `running`，但没有 lease 证据时不得宣称 runner 正在管理 |
| `succeeded` | `succeeded` |
| `failed` | `failed` |
| `cancelled` | `cancelled` |
| `stale` | `stale` |

历史 operation 没有 `progress`、`cancel_requested`、`lease` 或 `attempt` 时，公开为 `null`/`not_available` 或保持旧 API contract，不补造值。

## 5. Progress、lease 和 attempt

### 5.1 Progress

- `progress_percent` 使用 `0..100` 整数；排队默认为 0。
- 无法可靠估计进度时允许 `null`，同时提供固定白名单 `stage_code`，不写自由文本正文。
- 同一 attempt 内 progress 不得倒退；成功只能以 100 收口；失败、取消和 stale 不强行改为 100。
- progress 是诊断信息，不是业务事实，不用于推断 artifact 已存在。
- stage code 必须是预先注册的低基数值，例如 `queued`、`reading_source`、`indexing`、`provider_call`、`persisting`、`finalizing`；不能包含 filename、query、正文、路径、URL、secret 或异常原文。

### 5.2 Lease

- runner 获取 task 时必须原子设置 attempt/lease owner、`lease_started_at`、`lease_expires_at`；owner token 只保存在运行时，不返回 API、不写日志。
- runner 必须在执行安全点 heartbeat；heartbeat 只能延长自己持有的 lease。
- lease 过期后，旧 runner 不得继续提交成功 artifact；提交必须进行 compare-and-set 状态/lease 校验。
- 单进程 v1 不提供跨进程 lease 协议；如果发现另一个进程使用同一 data root，只能拒绝/诊断，不得宣称协调成功。
- lease reclaim 后默认标记 `stale`；只有 operation policy 明确幂等且旧副作用不会重复时，才允许显式 retry。

### 5.3 Attempt 与 retry

- `task_id` 表示逻辑任务；每次 retry 创建新的 `attempt_id`，不创建新的逻辑 task。
- retry 必须显式触发，且只能对 operation policy 标记为 retryable 的稳定错误码执行。
- retry 递增 retry/attempt 计数，保留旧 attempt 的终态、错误码和时间；不得删除或重写历史 attempt。
- 同一 input fingerprint、source revision、operation kind 和 idempotency scope 下，retry 必须避免重复生成 artifact、重复写入确认状态或重复真实外部副作用。
- Provider timeout、暂时不可用、rate limit 等可候选 retry；schema invalid、citation invalid、project scope violation、source deleted、用户输入错误等默认不可 retry。最终列表由 10-4/业务 policy 冻结。
- 达到最大 retry 次数后必须进入 `failed`，不得循环排队。

## 6. 取消语义

### 6.1 默认取消模型

Phase 10 只承诺 **cooperative cancellation**：

- `queued` 任务可直接取消；
- `running` 任务先进入 `cancel_requested`；handler 在读取批次、chunk、provider 调用前后、持久化前等安全点检查；
- 如果底层 Provider HTTP 或 parser 不可中断，系统只能在请求返回后丢弃结果或根据 source/lease compare-and-set 拒绝提交；不能宣称已强制取消网络请求；
- `cancelled` 只表示本地任务已安全停止，不代表外部服务没有继续处理请求；
- cancel 不删除 operation、attempt、错误审计或已存在的用户事实。

### 6.2 取消边界

取消不得：

- 回滚已经向用户明确确认的 card/exercise/note/plan/progress/attempt；
- 删除 source、material、capture 原件或报告历史；
- 把部分生成结果静默发布为 ready/confirmed；
- 触发自动 retry、自动 delivery 或自动 source refresh。

## 7. 幂等、副作用和最终一致性

### 7.1 幂等键和 fingerprint

- `idempotency_key` 是调用方提供的 opaque 值，只用于同一 project scope 内匹配；不出现在日志、metrics、普通响应或 backup manifest。
- `input_fingerprint` 是服务端对规范化输入、scope、source revision、policy version 等计算的 hash；可用于匹配，不可作为正文或安全授权凭证。
- 同 key + 同 fingerprint：queued/running 返回当前 task/operation 状态；succeeded 返回已持久化结果；failed/stale 只有显式 retry policy 才能重试。
- 同 key + 不同 fingerprint：拒绝并返回 `task_idempotency_key_mismatch` 或既有业务专用稳定错误；不得覆盖原 task。
- 无 key 的相同请求不是自动 replay；必须依赖业务明确的 fingerprint/idempotency policy。

### 7.2 副作用保护

每个 runner handler 必须声明：

1. 读取的 project/source scope；
2. 可写的表和 artifact；
3. 是否调用 Provider/外部 adapter；
4. 是否可 retry；
5. cancel 安全点；
6. final write 的 compare-and-set 条件；
7. 重复执行如何避免重复副作用。

所有最终业务写入必须在同一明确事务中完成状态校验和 artifact 写入。对于 provider、OCR/ASR 和 delivery：

- raw prompt/raw response、原始音频/图片内容、secret、路径不进入 task record、日志或 API；
- AI/OCR/ASR 结果先保持 draft/建议；
- citation/source revision 必须由服务端复验；
- delivery 默认 off，dry-run 不联网；真实 live delivery 不因 task runner 自动获得批准；
- backup/restore/startup/read 不执行 task handler。

## 8. Operation policy 分类（供 10-4 逐项批准）

10-1 不直接批准所有业务后台化，只冻结 policy 分类：

| 操作 | 当前状态 | 10-1 契约处理 | 10-4 决定 |
|---|---|---|---|
| `qa_answer` | 同步请求内执行 | 保持旧兼容；可未来 task-backed | 是否异步化、同步兼容方式 |
| `generate_card` / `generate_exercise` | 同步生成 draft | 必须保留 draft/citation/user-edit protection | 是否后台化及 Provider 副作用策略 |
| `generate_note` | 同步生成 draft | 同上 | 逐项审批 |
| `embedding_index` | 显式同步 indexing，已有局部 stale/retry | 最适合优先 task 化候选 | 需验证 progress、取消和恢复 |
| `class_capture_transcription` | fake/loopback 同步转写 | 结果必须保持 draft/uncertain | 需确认长任务及原件读取策略 |
| report snapshot | 只读聚合、显式创建 | 不自动调度 | 可作为只读 projection task 候选 |
| report delivery | 默认 off/dry-run，live 固定拒绝 | 不因 runner 获得发送权 | 仅可在批准范围内 dry-run |
| material CRUD、rename/delete/restore/purge、attempt submit | 短同步事务 | 不后台化 | 保持同步，除非另有契约 |

10-4 不得把“候选”解释为已批准；任何需要真实网络、真实外发、跨进程或多用户的操作必须回到范围评审。

## 9. 错误码与公开 contract

### 9.1 任务层稳定错误码

至少冻结以下任务层错误：

- `task_not_found`
- `task_project_scope_violation`
- `task_invalid_state_transition`
- `task_already_running`
- `task_idempotency_key_mismatch`
- `task_retry_not_allowed`
- `task_retry_limit_reached`
- `task_cancel_not_allowed`
- `task_cancel_requested`
- `task_lease_lost`
- `task_lease_expired`
- `task_handler_not_registered`
- `task_handler_failed`
- `task_recovery_required`
- `task_result_unavailable`

具体业务错误（如 `provider_timeout`、`retrieval_not_ready`、`source_deleted`、`delivery_disabled`）保留在 operation/error_code 层，不被泛化成丢失原因的 `task_handler_failed`；对外只返回安全稳定的 code。

### 9.2 安全公开字段

允许 task/operation status API 返回：

```text
id / task_id / operation_id
project-scoped status
operation kind
progress_percent / stage_code
retry_count / attempt_count
created_at / started_at / updated_at / finished_at
error_code（稳定且已脱敏）
output_artifact_id（若业务允许）
provider_id / model_id（非 secret）
replay / cancel_requested（必要时）
```

禁止返回：

```text
input_fingerprint
raw idempotency key
lease owner/token
SQLite SQL/path
stored_path/data_root
source text/full report content
raw provider request/response
API key/Authorization/SMTP password/Feishu secret
answer key/user submitted answer
```

## 10. Backup、restore、startup 和读取语义

- backup 必须保存 operation/task/attempt 的业务审计事实和终态；v13 保存 attempt 的 lease 时间事实，但不保存 lease owner/token；恢复后不能让旧 lease 继续有效。
- restore 后 queued/running/cancel_requested 的任务不得自动执行；默认按 `stale`/`recovery_required` 方式安全处理，保留原审计并要求显式 operator action。
- restore/startup/read 不调用 provider、OCR/ASR、parser、index、report 或 delivery handler；不自动 repair、rebuild 或发送。
- restored succeeded/failed/cancelled/stale 事实必须保持原状态；source deleted/unavailable/stale 不能被 task 恢复为 valid。
- 失败数据库和已验证 backup 必须保留；恢复到新空 target，不覆盖 live data。

## 11. Gate B 验收与测试计划

Gate B 通过标准：

1. operation 与 task 的边界、兼容策略和 ID/scope 语义无歧义；
2. 状态转换表覆盖 queued/running/cancel/cancelled/succeeded/failed/stale；非法转换和终态保护明确；
3. progress、lease、attempt、retry 和 cooperative cancellation 的限制明确；
4. 幂等、重复副作用、source revision、draft/user edit、delivery off 和隐私边界明确；
5. backup/restore/startup/read 的 non-repair/non-run 语义明确；
6. 10-2 已据此完成最小 v13 migration；10-3 可以据此实现 runner，10-4 可以据此逐项接入业务；
7. 10-1 本身未修改旧 API；10-2 未改变旧同步 operation 语义。

10-2 以后必须新增正式测试覆盖：

- 状态转换白名单和非法转换；
- 终态不可覆盖；
- project scope 和 ID boundary；
- progress 单调性和 0/100 边界；
- lease compare-and-set、过期和旧 worker 提交拒绝；
- retry/attempt 保留历史和上限；
- queued/running cooperative cancel；
- idempotency replay/mismatch 和副作用不重复；
- restore 后不自动运行、不伪造成功；
- API/UI/log/metrics 的隐私边界。

本任务现有回归基线：

```powershell
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q -p no:cacheprovider
```

10-1 文档变更后运行治理一致性 focused test；不因契约冻结虚构 runner 测试通过。

## 12. 10-1 完成声明

> Phase 10-1 已完成 operation/task 正式契约、状态机、兼容策略、progress/lease/retry/cancel/幂等和隐私边界冻结；Gate B 通过。10-2 已完成 v13 最小 task/attempt schema，Gate C 通过。task runner、后台执行、取消、长任务恢复和业务接入仍尚未实现；Phase 10 和 StudyBuddy 本地 v1 尚未完成上线。

下一步：执行 `docs/prompts/phase10/10-3_单进程_task_runner_与恢复.md`。

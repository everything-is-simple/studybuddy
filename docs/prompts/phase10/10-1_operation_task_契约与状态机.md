# 10-1 operation/task 正式契约与状态机

```text
请在 H:\\studybuddy 执行 Phase 10-1。先读取 00_COMMON_CONTEXT.md、10-0 的审计产物和现有 operation 代码/测试。只冻结正式 operation/task 契约，不实现 runner，不修改业务 API。

设计并冻结统一长任务模型：task/operation identity、project scope、kind、owner/request ID、created/started/updated/finished time、status、progress、message 的安全摘要、retry_count、idempotency key/fingerprint、lease、cancel_requested、error code、provider/model metadata 和 parent/child 关系。定义 queued/running/succeeded/failed/cancel_requested/cancelled/stale 等状态的合法转换、终态不可变性、重试是否新 attempt、重复请求 replay/conflict 和副作用边界。

明确 cooperative cancellation：排队任务可取消；执行中任务只能在安全检查点停止；不可中断的 Provider HTTP 不得虚假宣称强制取消。定义进程重启、超时、lease 过期、失败重试、无 key 请求和恢复后的 stale 状态。明确哪些既有 ai_operations 可以兼容复用，哪些字段/表不得破坏；不把所有同步 API 自动异步化。

为每条状态转换给出 repository/domain 不变量、稳定错误码、日志脱敏字段、API 可见字段和测试例子。禁止持久化 raw prompt/raw response/secret/source text/path/答案 key/用户提交原文。若契约需要 schema 变化，只提出 v13 迁移清单，不在本任务实现。

允许修改 docs/prompts/phase10/、必要的 docs/ai-learning-architecture.md 和 TODO/STATUS 的契约状态；新增测试仅限契约/状态表测试，不能实现 runner。验收：状态转换表无歧义、同步兼容策略明确、恢复/取消/幂等可测试、Gate B 通过。推荐提交：`docs: freeze operation task contract`。准确状态：`planned/contract-frozen`。
```

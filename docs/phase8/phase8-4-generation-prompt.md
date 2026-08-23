# Phase 8.4：AI Draft Generation 与 Citation-Safe Integration Prompt

## 目标
把 Cards/Exercises 接入现有 RAG 和 Provider 链路，形成可审计的 AI draft 生成，不把模型输出直接当作可信学习内容。

## 上下文
复用 context assembly、lexical/vector/hybrid retrieval、citation candidate、server-side citation validation、ai_operations、provider capabilities 和稳定 provider 错误。provider 未配置时应用正常启动，生成安全失败。

## 任务
1. 冻结 card/exercise generation input：material scope、query/topic、类型、数量、retrieval policy、source revision 和 optional idempotency key。
2. 生成前显式要求材料已 indexing/ready；不自动索引或自动修复。
3. 生成结构化 draft，严格校验 schema、字段长度、题型和 citation key；模型伪造/缺失/越界 citation 必须拒绝 artifact ready。
4. 原子保存 operation、draft、citation metadata；失败只保留安全 operation/draft failure 状态，不能留下半成品 ready。
5. 记录 provider/model/request/usage/latency/retrieval policy/source revision 等 metadata；不持久化 raw prompt/provider response 或 secret。
6. 实现重复请求、running conflict、成功 replay、失败 retry 和 source changed/stale 语义；不得覆盖 user-edited/confirmed artifact。
7. 对 prompt injection、恶意 source text、超长回答和 malformed structured output 做边界处理。

## 验收
fake provider 下 backend 完整测试覆盖成功、empty retrieval、not configured、timeout/malformed/schema/citation failure、idempotency、rollback、stale source 和 draft-only invariant。真实 Provider 不在本子任务扩大验收范围。

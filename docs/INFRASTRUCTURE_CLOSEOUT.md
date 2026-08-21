# 基础设施真实状态与收尾计划

> 更新：2026-08-25  
> 本文只评估 StudyBuddy 的**本地单进程文件材料基础设施**；不把 AI、学习工作流、多用户、云同步或分布式部署计入完成范围。
>
> **结论：** I1 migration/schema versioning、I2 backup/restore 运维闭环、I3 最小可观察性与 I4 真实环境/容量基线（时间盒）均已完成。StudyBuddy 的**本地单进程文件材料基础设施 v1 已基本完工**，可作为 AI MVP 的数据基础。
>
> I4 中 Windows ACL/只读目录、真实磁盘满或配额、S4 更高压力规模、peak memory、断电、网络盘、硬件/文件系统损坏等项已明确记录为 `not_verified`，并作为 v1 运行边界接受；这些未验证项不在当前基础设施 v1 的验收范围内。

## 1. 已完成能力

### 文件材料核心路径（局部 `real-pass`）

- 单文件、多文件 batch、文件夹选择导入。
- TXT、Markdown、PDF、DOCX、PPTX 解析；明确拒绝 RTF、旧 DOC、旧 PPT。
- 列表、详情、筛选、分页、rename、逻辑删除、回收站、restore、purge。
- 原文件、正文与批量 ZIP 导出；FTS5 词法搜索和中文/特殊字符 fallback。
- Chromium 对导入、管理、搜索、导出及主要失败路径的真实验收。

### 已实现的安全与一致性边界

- SQLite WAL、foreign keys、busy timeout、事务与 FTS 一致性。
- hash-derived local originals、atomic replace、shared-hash 引用保护。
- storage containment、symlink、regular-file、hash mismatch 安全边界。
- startup preflight、ready/health、diagnostic audit、保守 recovery。
- controlled OSError / SQLite failure、write contention、subprocess crash/restart 验证。

### I1（完成）：Migration / schema versioning

- 当前 `schema version = 2`，迁移链为 `v1 canonical_material_schema` → `v2 ai_phase0_schema`。
- `schema_migrations`、`PRAGMA user_version`、连续历史校验和 `BEGIN IMMEDIATE` 原子迁移已实现。
- 覆盖新库、legacy/v1 升级、幂等、future version、失败 rollback、backup/restore 版本一致性测试。
- operator 升级与失败恢复流程见 [`OPERATOR_UPGRADE.md`](OPERATOR_UPGRADE.md)。

### I2（完成）：Backup / restore 运维闭环

- `backup`、`verify-backup`、`restore --confirm` 与 SQLite Online Backup API 已实现。
- backup manifest 校验 database hash、integrity、foreign keys、schema version 与 originals hash。
- restore 使用外部 staging，目标只允许不存在或空目录；不会启动服务、迁移或 repair。
- `verify-restored-data` 覆盖 offline/online 恢复后验收；保留策略、操作说明与 restore drill 文档已提供。

## 2. 已完成 I3 与 I4（时间盒验收）

### I3（完成）：最小可观察性与运行边界

- `backend/app/observability.py` 提供 JSON structured event、request/operation correlation 与低基数进程内 counters。
- HTTP middleware 为每个响应回写 `X-Request-ID`；非法或超长输入会安全替换。operation ID 仅用于 request-scoped 日志关联，未写入数据库。
- `/api/liveness` 表示进程可响应；`/api/health` 继续表示 readiness。preflight、migration/connect 失败时不 ready；diagnostic audit/recovery 的非阻断诊断事件不将服务误报为不可用。当前没有独立 degraded runtime 状态：不可安全运行即 not ready；仅诊断事件记录为 warning，不降低已 ready 服务为不可写状态。
- `/api/metrics` 仅返回有限的进程内聚合，不含正文、路径、ID、query、文件名、secret、SQL 或异常文本；重启后归零且不支持跨进程聚合。
- startup、audit、recovery、backup 事件写入安全 structured event；日志失败不阻断业务。
- `backend/tests/test_observability.py` 覆盖 request ID、metrics、liveness/readiness、startup 与 backup verify 脱敏边界。

### I4（时间盒验收完成）：真实环境与容量基线

**已完成并有 artifact：**

- 合成 TXT S0–S3：1 / 10 / 100 / 500 文件，约 1 KiB / 100 KiB / 1 MiB / 10 MiB。
- 记录导入、搜索、文本导出耗时、数据库大小、originals 大小和 health 状态。
- 40-cycle 导入 → rename → delete → restore → purge 生命周期 smoke，无失败。
- 固化单进程、单实例、本地磁盘和单一 data_root owner 限制。

证据（最近一次 I4 基线已重新运行并更新）：

```text
H:\studybuddy-test\scripts\i4_baseline.py
H:\studybuddy-test\artifacts\infrastructure-i4\latest.json
H:\studybuddy-test\artifacts\infrastructure-i4\latest.md
```

**时间盒验收结论：** I4 真实环境与容量基线已按时间盒验收完成。Windows ACL/只读目录真实拒绝、真实磁盘满或配额、S4 更高压力规模、peak memory、断电、网络盘、硬件/文件系统损坏等项仍为 `not_verified`，并已明确记入 v1 运行边界；这些项目不阻塞基础设施 v1 收口，也不得标记为已通过。

## 3. 完成顺序

```text
I4 真实环境与容量基线（时间盒） ✅ 已验收
→ 本地单进程基础设施 v1 基本完工 ✅ 已宣告
→ AI Phase 1：revision / chunks / retrieval / citations / Q&A（当前最高优先级）
```

I1 是 AI Phase 4（Cards / Exercises）的硬前置，现已完成；AI 功能本身尚未实现，不能因 schema 已预留而宣称已有 RAG、Q&A 或卡片能力。

## 4. 当前准确声明

基础设施 v1 已满足 I1/I2/I3 完成，且 I4 已产出实测结果与清晰未验证清单，现可准确表述为：

> StudyBuddy 的**本地单进程基础设施 v1 已基本完工**：支持单实例、本地磁盘、SQLite、versioned migration 和手工 backup/restore；文件材料管理核心路径局部 real-pass，基础安全、一致性、恢复和运维边界已实现并有明确运行限制。

仍不得宣称支持多进程共享 data root、云同步、多用户、分布式生产部署、真实断电/磁盘损坏/网络盘恢复或全局生产级 real-pass。下一优先级为 AI Phase 1：revision / chunks / retrieval / citations / Q&A。

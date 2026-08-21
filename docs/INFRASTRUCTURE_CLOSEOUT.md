# 基础设施真实状态与收尾计划

> 更新：2026-08-25  
> 本文只评估 StudyBuddy 的**本地单进程文件材料基础设施**；不把 AI、学习工作流、多用户、云同步或分布式部署计入完成范围。
>
> **结论：** I1 migration/schema versioning 与 I2 backup/restore 运维闭环已完成。基础设施已可用于当前文件材料管理系统，并可安全作为 AI MVP 的数据基础；要宣告“本地单进程基础设施 v1 基本完工”，还剩 **2 个工作包**：I3 最小可观察性（必须）与 I4 真实环境/容量基线（时间盒验收，必须给出实测结果或明确未验证边界）。

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

## 2. 剩余 2 个收尾工作包

### I3（必须）：最小可观察性与运行边界

**目的：** AI/provider/任务增加后，operator 必须能用安全的稳定信息定位失败，而非依赖 traceback 或源码。

- [ ] 定义结构化安全日志字段：`event`、`level`、时间、稳定 `error_code`、request/operation ID；禁止正文、路径、secret、SQL 与原始异常。
- [ ] 为 HTTP 请求增加 request ID；为导入和后续 AI 操作贯通 operation ID。
- [ ] 增加最小 metrics：请求量、导入成功/失败、耗时、SQLite/recovery/backup 事件。
- [ ] 明确 `liveness`、`readiness`、`degraded` 的语义和 operator 可见输出。
- [ ] 为 startup preflight、audit、recovery、backup/restore 的失败输出补稳定性和脱敏测试。

**完成标准：** 一次失败导入、启动预检失败和 backup verify 失败均可通过稳定 error code/ID 定位；日志、API 与 UI 不泄露正文、路径、secret、SQL 或 traceback。

### I4（时间盒验收）：真实环境与容量基线

**目的：** 将当前“controlled failure 已测”与“真实环境未验证”的边界量化，而不是伪称生产级通过。

- [ ] Windows 真实 ACL / 只读目录拒绝测试（隔离目录）。
- [ ] 受控磁盘空间不足或等效配额测试。
- [ ] 批量导入、搜索、导出的容量/耗时基线。
- [ ] 长时间导入/删除/恢复/导出 smoke。
- [ ] 固化单进程、单实例、local disk 部署限制；明确拒绝多 worker/shared `data_root`。

**完成标准：** 形成可复现命令、测试环境、结果与支持边界；无法完成的真实资源测试必须标记 `not verified`，不得伪造通过。

## 3. 完成顺序

```text
I3 最小可观察性（必须）
→ I4 真实环境与容量基线（时间盒）
→ 宣告本地单进程基础设施 v1 基本完工
→ AI Phase 1：revision / chunks / retrieval / citations / Q&A
```

I1 是 AI Phase 4（Cards / Exercises）的硬前置，现已完成；AI 功能本身尚未实现，不能因 schema 已预留而宣称已有 RAG、Q&A 或卡片能力。

## 4. 收尾后的准确声明

完成 I3，且 I4 已产出实测结果或清晰未验证清单后，可以准确表述为：

> StudyBuddy 的**本地单进程基础设施 v1 已基本完工**：支持单实例、本地磁盘、SQLite、versioned migration 和手工 backup/restore；文件材料管理核心路径局部 real-pass，基础安全、一致性、恢复和运维边界已实现并有明确运行限制。

仍不得宣称支持多进程共享 data root、云同步、多用户、分布式生产部署、真实断电恢复或全局生产级 real-pass。

# Operator backup / restore

StudyBuddy 的备份与恢复是显式 operator 操作，不是普通用户 API。应用启动不会自动 backup、restore 或 repair。backup、verify 与 restore 均写入仅进程内、重启归零的安全 start/success/failure metrics/events；不包含路径、SQL、原始异常、正文或 secret。

## 备份

```text
C:/miniconda/py310/python.exe -m app.cli backup \
  --data-root <data-root> \
  --output <backup-root>
```

备份目录包含：

```text
manifest.json
database.sqlite3
originals/<sha256[:2]>/<sha256[2:]>/original
```

SQLite 使用 Online Backup API 生成一致性快照，并执行 `integrity_check`、`foreign_key_check`、连续 migration history 和 schema version 校验。manifest 的 `database.schema_version` 必须同时匹配 `schema_migrations` 与 `PRAGMA user_version`，并记录 backup 时 application target schema；它不记录 live data root、`stored_path`、正文、secret、SQL、raw provider response 或异常文本。original storage 只包含 active/deleted material 引用的 hash-derived regular originals；每个文件按 SHA-256 与 size 校验，shared hash 只保存一份。

## 验证

```text
C:/miniconda/py310/python.exe -m app.cli verify-backup --backup <backup-root>
```

验证只检查 manifest、SQLite hash/integrity/foreign keys/连续 migration history/schema version、original 文件路径/类型/大小/hash 及数据库引用。验证不删除、不运行 migration、不重建 FTS、不修复数据库或修改 backup。连续 history 与 `PRAGMA user_version` 一致的旧 schema backup 可以作为升级回退证据，并可恢复到新空 target；其 restore acceptance 必须等待后续显式启动新版本完成 migration，不能把未升级 target 当作 current v1 ready。

## 恢复

恢复是破坏性操作。第一版只允许恢复到不存在或为空的目标目录；必须先停止服务，并显式提供 `--confirm`：

```text
C:/miniconda/py310/python.exe -m app.cli restore \
  --data-root <empty-target> \
  --backup <backup-root> \
  --confirm
```

流程为：验证 backup → 写入外部 staging → 再次验证 staging → 将 staging 放入目标目录。目标非空、symlink 或非目录会拒绝。恢复命令不启动服务、不调用 migration/recovery、不执行业务 repair、不重建 FTS；它保留 backup 的 schema version，不自行升级。只有后续显式启动新版本时，migration runner 才能执行受事务保护的升级。除将 material `stored_path` 重定位到新目标的 hash-derived originals 布局外，不改变 source tables 或业务状态。

恢复到新空 data root 时，restore 会将数据库中材料的 `stored_path` 重定位到新目标的 hash-derived originals 布局；这不是业务 repair，不会创建材料、计划、chunk 或 source link，也不会提升 unavailable/stale 状态。若 backup schema 旧于当前版本，先显式启动新版本让 migration runner 完成事务升级；完成后再执行：

```text
C:/miniconda/py310/python.exe -m app.cli verify-restored-data \
  --data-root <restored-root>
```

需要 HTTP 验收时追加 `--base-url`。验收覆盖 integrity、foreign keys、schema version、migration history、材料列表、原文件引用/hash、extraction、9A goals/modules/plans/items/dependencies/progress/source links、v10 Phase 9B notes/blocks/module links/note source statuses/rhythm settings/allocations、v11 Phase 9C session/item/review/mistake/cram consistency、v12 Phase 9D capture session/transcript draft/segment/report snapshot/delivery attempt 的表存在性、project scope 与 source-status consistency，以及 v13 Phase 10 task/attempt 表存在性、project scope、status 分布和 at-most-one-running-attempt 结构检查。online 模式另覆盖 health、detail、original download 和 text export。验收不会运行 migration、task runner、task handler、rebuild、Provider、OCR/ASR、report generation、delivery、source refresh 或 repair；它不会将 retained `stale`、`source_deleted`、`source_unavailable` 提升为 valid。

## 保留、轮换与升级预检

```text
C:/miniconda/py310/python.exe -m app.cli rotate-backups --backup-root <backup-root> --retain <count>
C:/miniconda/py310/python.exe -m app.cli rotate-backups --backup-root <backup-root> --retain <count> --confirm
C:/miniconda/py310/python.exe -m app.cli upgrade-preflight --data-root <live-root> --backup <verified-backup>
```

`rotate-backups` 默认 dry-run；确认后才删除超过 `retain >= 1` 的较旧 verified set。它在删除前重新验证所有候选；symlink、file、incomplete、unknown 或 invalid/corrupt backup 永远不删，并保留为隔离证据。轮换失败不会写 live data root，也不会删除未通过预验证的其他候选。calendar daily/weekly/monthly 分类与 scheduler 仍由外部 operator 负责。

`upgrade-preflight` 只读检查 live database/originals、schema history/`user_version`、integrity/FK、写入 ACL access 和指定 rollback backup 的重新 verify/schema match；不 migration、repair、rebuild、运行 task 或调用外部能力。只有 `status=ready` 且 `backup_verified=true` 才可进入明确的停机升级流程。

## 诊断与健康

```text
C:/miniconda/py310/python.exe -m app.cli diagnostics --data-root <data-root>
```

该命令以 SQLite read-only connection 输出 application/schema version、task status counts、稳定降级原因和建议动作；不会执行 migration、repair、index rebuild、Provider 或 task handler。`/api/liveness` 只表示 HTTP process 可应答；`/api/health` 与 `/api/readiness` 在 database/audit/stale-task 诊断为 degraded 时返回 503，不伪造 healthy。diagnostics 返回 degraded/unavailable 时也以非零退出，operator 应保留数据与已验证 backup 后再执行明确的恢复决策。

## 运维边界

备份保留/轮换、权限、外部 scheduler、恢复演练和失败隔离见 [`prompts/BACKUP_OPERATIONS.md`](prompts/BACKUP_OPERATIONS.md)、[`prompts/RESTORE_DRILL.md`](prompts/RESTORE_DRILL.md) 与 [`prompts/OPERATOR_UPGRADE.md`](prompts/OPERATOR_UPGRADE.md)。不要把 backup 输出放在 live data root 内，也不要在服务运行时覆盖 live data。database integrity、schema/history、original hash/size、restore acceptance 或 readiness 无法建立时，v1 不进入普通 read/write 或 runtime read-only serving：停止服务、保留证据、以 verified backup 恢复到新空目标。

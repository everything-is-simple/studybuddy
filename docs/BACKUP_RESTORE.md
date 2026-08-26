# Operator backup / restore

StudyBuddy 的备份与恢复是显式 operator 操作，不是普通用户 API。应用启动不会自动 backup、restore 或 repair。

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

SQLite 使用 Online Backup API 生成一致性快照，并执行 `integrity_check`、`foreign_key_check` 和 schema version 校验。manifest 的 `database.schema_version` 必须同时匹配 `schema_migrations` 与 `PRAGMA user_version`。original storage 只包含 active/deleted material 引用的 hash-derived regular originals；每个文件按 SHA-256 校验，shared hash 只保存一份。manifest 不记录 live data root、stored_path 或异常文本。

## 验证

```text
C:/miniconda/py310/python.exe -m app.cli verify-backup --backup <backup-root>
```

验证只检查 manifest、SQLite hash/integrity/foreign keys/schema version、original 文件路径/类型/大小/hash 及数据库引用。验证不删除、不运行 migration、不重建 FTS、不修复数据库或修改 backup。

## 恢复

恢复是破坏性操作。第一版只允许恢复到不存在或为空的目标目录；必须先停止服务，并显式提供 `--confirm`：

```text
C:/miniconda/py310/python.exe -m app.cli restore \
  --data-root <empty-target> \
  --backup <backup-root> \
  --confirm
```

流程为：验证 backup → 写入外部 staging → 再次验证 staging → 将 staging 放入目标目录。目标非空、symlink 或非目录会拒绝。恢复命令不启动服务、不调用 migration/recovery、不执行业务 repair、不重建 FTS；除将 material `stored_path` 重定位到新目标的 hash-derived originals 布局外，不改变 source tables 或业务状态。

恢复到新空 data root 时，restore 会将数据库中材料的 `stored_path` 重定位到新目标的 hash-derived originals 布局；这不是业务 repair，不会创建材料、计划、chunk 或 source link，也不会提升 unavailable/stale 状态。完成后重新启动服务并执行：

```text
C:/miniconda/py310/python.exe -m app.cli verify-restored-data \
  --data-root <restored-root>
```

需要 HTTP 验收时追加 `--base-url`。验收覆盖 integrity、foreign keys、schema version、migration history、材料列表、原文件引用/hash、extraction、9A goals/modules/plans/items/dependencies/progress/source links、v10 Phase 9B notes/blocks/module links/note source statuses/rhythm settings/allocations、v11 Phase 9C session/item/review/mistake/cram consistency，以及 v12 Phase 9D capture session、transcript draft/segment、report snapshot、delivery attempt 的表存在性、project scope 与 source-status consistency。online 模式另覆盖 health、detail、original download 和 text export。验收不会运行 migration、rebuild、Provider、OCR/ASR、report generation、delivery、source refresh 或 repair；它不会将 retained `stale`、`source_deleted`、`source_unavailable` 提升为 valid。

## 运维边界

备份保留/轮换、权限、外部 scheduler、恢复演练和失败隔离见 [`prompts/BACKUP_OPERATIONS.md`](prompts/BACKUP_OPERATIONS.md) 与 [`prompts/RESTORE_DRILL.md`](prompts/RESTORE_DRILL.md)。不要把 backup 输出放在 live data root 内，也不要在服务运行时覆盖 live data。

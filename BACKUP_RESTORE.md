# Operator backup / restore

StudyBuddy 的备份与恢复是显式 operator 操作，不是普通用户 API。应用启动不会自动 backup、restore 或 repair。

## 备份

```text
D:/miniconda/py310/python.exe -m app.cli backup \
  --data-root <data-root> \
  --output <backup-root>
```

备份目录包含：

```text
manifest.json
database.sqlite3
originals/<sha256[:2]>/<sha256[2:]>/original
```

SQLite 使用 Online Backup API 生成一致性快照，并执行 `integrity_check` 与 `foreign_key_check`。original storage 只包含 active/deleted material 引用的 hash-derived regular originals；每个文件按 SHA-256 校验，shared hash 只保存一份。manifest 记录版本、大小、hash 和数量，不记录 live data root、stored_path 或异常文本。

## 验证

```text
D:/miniconda/py310/python.exe -m app.cli verify-backup --backup <backup-root>
```

验证只检查 manifest、SQLite hash/integrity/foreign keys、original 文件路径/类型/大小/hash 及数据库引用。验证不删除、不重建 FTS、不修复数据库或修改 backup。

## 恢复

恢复是破坏性操作。第一版只允许恢复到不存在或为空的目标目录；必须先停止 StudyBuddy 服务，并显式提供 `--confirm`：

```text
D:/miniconda/py310/python.exe -m app.cli restore \
  --data-root <empty-target> \
  --backup <backup-root> \
  --confirm
```

流程为：验证 backup → 写入外部 staging → 再次验证 staging → 将 staging 放入目标目录。目标非空、symlink 或非目录会拒绝。恢复命令不启动服务、不调用 recovery、不执行 repair、不重建 FTS、不改变 source tables。完成后重新启动服务，再检查 `/api/health`、材料列表、详情、原文件下载和文本导出。

## 限制

backup/restore 不保证修复业务逻辑、schema、FTS 或损坏数据库；不覆盖真实磁盘满、网络盘、断电或多进程并发场景。不要把 backup 输出放在 live data root 内，也不要在服务运行时覆盖 live data。

# Operator upgrade runbook

本 runbook 用于 StudyBuddy 数据库 schema 升级，当前目标版本为 **schema version 9**。
升级会由 application startup 触发 migration runner；operator 不应手工修改
`schema_migrations` 或 `PRAGMA user_version`。

## 适用范围

当前迁移链为 `docs/MIGRATIONS.md` 中的连续 v1–v9 history，当前新增阶段为：

```text
7 | phase8_cards_exercises_schema
8 | phase8_exercise_provenance
9 | phase9a_learning_plan_schema
```

v9 增加 Phase 9A 的 goals、knowledge modules、study plans/items、dependencies、progress events 和 source-link schema。应用不会在导入或启动时自动创建学习计划数据、自动 repair source links、调用真实 provider 或启动后台任务。9A repository/domain、API、本地 Chromium workspace、source lifecycle 和 backup/restore 已有 scoped gate；9A-6 尚未 closeout，9A-7 restore-gates-pass 已通过，Phase 9A acceptance 仍按路线图推进。

支持的部署前提是单进程、单实例、单一 `data_root`、本地存储。升级期间不得让多个
StudyBuddy 进程或其他 SQLite writer 使用同一个数据库。

## 升级前检查

1. 停止 StudyBuddy 服务和所有可能访问该 `data_root` 的进程。
2. 确认目标目录、数据库和 originals 没有 symlink；确认备份目录位于 live data root
   之外。
3. 记录当前 schema version：

```bat
cd /d H:\studybuddy\backend
C:\miniconda\py310\python.exe -m app.cli schema-version ^
  --database <live-data-root>\studybuddy.sqlite3
```

如果命令不能返回稳定的 schema version，停止升级并保留数据库副本；不要手工修复
history。

4. 创建 live data root 的备份：

```bat
C:\miniconda\py310\python.exe -m app.cli backup ^
  --data-root <live-data-root> ^
  --output <backup-root>
```

5. 验证备份：

```bat
C:\miniconda\py310\python.exe -m app.cli verify-backup ^
  --backup <backup-root>
```

只有 `status = valid` 的备份才是升级回退依据。记录备份路径、时间、schema version
和 verification 结果。

## 执行升级

启动新版本 StudyBuddy。应用启动顺序为：

```text
preflight
-> SQLite connect
-> migration runner
-> schema/index consistency check
-> diagnostic audit
-> storage recovery
-> ready
```

对于已有 v8 数据库，runner 只执行缺失的 v9：

```text
BEGIN IMMEDIATE
-> execute phase9a_learning_plan_schema
-> insert (9, 'phase9a_learning_plan_schema') into schema_migrations
-> set PRAGMA user_version = 9
-> COMMIT
```

新数据库会按 v1–v9 的连续顺序创建。重复启动不会重复执行或新增 history row。

## 升级后验收

服务 ready 后检查 health：

```text
GET /api/health
```

期望：

```json
{"status":"ok"}
```

再次检查 schema version：

```bat
C:\miniconda\py310\python.exe -m app.cli schema-version ^
  --database <live-data-root>\studybuddy.sqlite3
```

期望：

```json
{"schema_version":9}
```

必要时直接核对 migration history：

```bat
C:\miniconda\py310\python.exe -c "import sqlite3; c=sqlite3.connect(r'<live-data-root>\studybuddy.sqlite3'); print(c.execute('SELECT version,name FROM schema_migrations ORDER BY version').fetchall()); print(c.execute('PRAGMA user_version').fetchone()[0]); c.close()"
```

期望结果：

```text
[(1, 'canonical_material_schema'), ..., (9, 'phase9a_learning_plan_schema')]
9
```

同时执行现有功能 smoke check：

- active materials list
- deleted materials list
- material detail
- original download
- extracted text export
- search

## 失败处理与半升级防护

migration DDL、history row、`PRAGMA user_version` 在同一个 SQLite migration transaction
内完成。任意一步失败都应 rollback：

- 不写入 v9 history row；
- 不将 `PRAGMA user_version` 更新为 9；
- 不把应用置为 ready；
- 不继续以普通读写模式运行；
- 不手工删除残留表或编辑版本号。

稳定错误可能包括：

```text
database_schema_unsupported
database_schema_version_unknown
database_migration_history_mismatch
database_migration_incomplete
database_migration_failed
```

失败后：

1. 停止服务并保留失败数据库及日志中的稳定错误码。
2. 不要覆盖 live data root，不要删除 `schema_migrations`，不要执行 `PRAGMA user_version`。
3. 如果数据库仍可诊断，先复制一份用于诊断；不要在原库上反复尝试未知修复。
4. 优先使用原升级前已验证的 backup，恢复到一个**新的空目录**：

```bat
C:\miniconda\py310\python.exe -m app.cli restore ^
  --data-root <new-empty-target> ^
  --backup <verified-backup-root> ^
  --confirm
```

5. 对恢复目录执行 restore acceptance，再将服务指向该新目录；不要直接覆盖正在使用
   的 live data root。

当前没有 automatic down migration。升级失败的数据库和备份必须保留，直到新目录通过
schema、完整性、材料和原文件验收。

## 完成标准

升级只有在以下条件全部满足时才算完成：

```text
schema version = 9
history = continuous v1–v9 history ending with phase9a_learning_plan_schema
PRAGMA user_version = 9
/api/health = 200 / ok
backup/restore version consistency 已通过
现有材料读写、搜索、导出 smoke check 已通过
```

通过后才能进入后续业务 gate。该升级不会自动索引历史材料，不会自动 repair source links，不会启动 Cards/Exercises/Plans 生成，也不会启动后台任务。

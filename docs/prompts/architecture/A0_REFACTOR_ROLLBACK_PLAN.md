# A0 拆分回退方案

## 回退原则

拆分是可逆的源码迁移，不是 schema/数据迁移。A1/A2 不允许数据库写入、migration、原文件布局、配置 key 或 API 语义变化。每一小步都保留旧 façade，因此发现回归时优先切回旧 import/路由绑定，而不是修补生产数据。

## 每阶段执行前

1. 工作区必须干净；记录 `git rev-parse HEAD`、pytest 全量结果、browser 环境状态。
2. 保存 route inventory（method/path/status）、公开 repository symbol inventory、CLI 命令输出和关键 JSON/error-code fixtures。
3. 确认无运行中的正式实例，使用隔离测试 data root；不得把测试数据库/原文件写入仓库。
4. 只允许一个域一个 writer；A1/A2 分支分别独立提交。

## A1 repository 拆分回退

1. 先恢复旧 `backend/app/repository.py` façade 及旧 import；目标模块可保留但不再被入口引用。
2. 回退仅限 A1 commit（例如 `git revert <A1-commit>` 或恢复 A1 分支）；不要执行数据库 restore/repair。
3. 运行完整 backend、可用时完整 browser、CLI diagnostics/backup verify smoke。
4. 若只一个域失败，撤销该域绑定，其他已验证域保持 façade；不得继续 A2。
5. 若发现 schema 或数据副作用，立即停止写入、保留失败 data root/日志，按既有 `docs/BACKUP_RESTORE.md` 验证 backup 后恢复到新的空目标；不得覆盖 live data root。

## A2 main/app factory 拆分回退

1. 恢复 `backend/app/main.py:create_app` 原绑定，保留 `backend.app.main:app` 兼容对象。
2. 恢复 `/` 对 `INDEX_HTML` 的返回；A2 不应涉及静态文件。
3. 重新运行 route inventory、health/readiness/liveness、上传/导出、Q&A、task 和 CLI serve smoke。
4. 页面或 middleware 回归时，不要通过改变 API 或错误文案“修复”；直接切回旧路由实现。

## A3/A4 之后

前端和 Provider/采集页已经不是纯源码拆分；需要独立 acceptance、artifact 和回退窗口。旧 `/` 单页应在新页面通过 gate 前保留，切换应可由单一 app-factory 绑定回旧入口。B1/B2/B3/B4 的业务能力不得和 A3/A4 同提交。

## 不得采用的回退方式

- 不手工删除/修改 `schema_migrations` 或 `PRAGMA user_version`；
- 不用 ad-hoc `CREATE TABLE` 修复拆分问题；
- 不覆盖 live data root；
- 不把数据库、originals、Playwright output、secrets 或 test artifacts 提交；
- 不宣称 browser-pass、real-pass 或生产支持，除非对应 gate 实际通过。

## 完成判定

回退后必须证明旧路径可导入、旧 API 可启动、旧错误码和 JSON 形状保持，且完整 backend 恢复为至少 A0 记录的 `413 passed, 2 skipped`。Browser 若环境仍无 Chromium，只能记录 blocked/not_verified；不能用 pytest 结果替代浏览器证据。

# 06 · 运维：启动、备份恢复、迁移、新机器、目录

命令里的 `python` 指 `D:\miniconda\py310\python.exe`，在 `backend/` 目录下执行 `-m app.cli`。

## 1. 启动与停止

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787
powershell -NoProfile -File H:\studybuddy\backend\scripts\health-studybuddy.ps1 -Port 8787
powershell -NoProfile -File H:\studybuddy\backend\scripts\stop-studybuddy.ps1 -DataRoot H:\studybuddy-data
```

隔离验证把 `-DataRoot` 换成 `H:\studybuddy-test\data_root`。启动脚本固定回环地址、单进程、外发关闭；停止只按 data_root 下的 PID 文件操作，不按端口杀进程。

健康检查：`/api/liveness`（进程能应答）、`/api/health` 与 `/api/readiness`（数据库/审计降级时返回 503）。只读诊断：`python -m app.cli diagnostics --data-root <root>`。

## 2. 备份、校验、恢复

```text
python -m app.cli backup         --data-root <root> --output <backup>
python -m app.cli verify-backup  --backup <backup>
python -m app.cli restore        --data-root <空目录> --backup <backup> --confirm
python -m app.cli verify-restored-data --data-root <restored> [--base-url http://127.0.0.1:8787]
python -m app.cli rotate-backups --backup-root <dir> --retain <n> [--confirm]
```

- 备份 = `manifest.json` + `database.sqlite3`（Online Backup API 快照）+ 按 hash 存放的原文件；不含密钥、路径、正文。
- 校验和恢复都**不修复、不迁移、不重建**。恢复只允许空目标、需先停服务、需 `--confirm`。
- 备份不要放在 live data_root 内。轮换默认 dry-run，坏备份永不删除。
- 定时备份由外部计划任务负责，系统不自动执行。

## 3. 迁移

- 唯一入口 `backend/app/migrations/runner.py`，启动时自动执行；连续、幂等、事务内原子提交，失败回滚。
- 无自动降级。出问题时保留失败库，用已校验备份恢复到新空目录。
- 升级前：停服务 → 备份并校验 → `python -m app.cli upgrade-preflight --data-root <live> --backup <verified>`，`status=ready` 后再启动新版本。
- 查看版本：`python -m app.cli schema-version --database <root>/studybuddy.sqlite3`。

## 4. 新机器

1. 装 Python 3.10、Node/npm、Git、PowerShell。
2. 克隆仓库；建 data、log、test 目录；不从旧机器复制凭据。
3. `python -m pip install -r backend/requirements.txt` → `pip check`。OCR/ASR 模型从批准的离线包恢复。
4. `npm ci`，再装 Playwright Chromium。
5. 运行 `backend/scripts/check-studybuddy-workspace.ps1` 与 `check-development-environment.ps1`。
6. 启动正式 data_root，三个健康端点返回 200。
7. 只通过设置页保存 Provider/邮件/飞书配置；不把密钥写进 Git、日志、提示词。
8. 外发保持 off；真实 Provider、邮件、飞书需单独授权验证。

## 5. 目录保留与清理

| 目录 | 必须保留 | 可清理 |
|---|---|---|
| `H:\studybuddy` | `backend/` `docs/` `.git/` `node_modules/` `.workbuddy/` | `__pycache__` `.pytest_cache` `test-results/` 临时脚本 |
| `H:\studybuddy-data` | 全部（含 `config/settings.json` 明文凭据） | 仅手动轮换 `logs/`；确认进程不存在后可删 pid/lock |
| `H:\studybuddy-test` | `verification/` `fixtures/` `artifacts/` 证据 | `runs/`、一次性 scratch data_root |
| `H:\studybuddy-composer` | `components/` `references/` `manifests/` | 已解压的原始压缩包、`.venv` |
| `H:\studybuddy-ChinaTextbook` | 全部；token 文件永不读取、清理或外传 | 无 |

清理规则：先只读列清单 → 用户逐类确认 → 显式白名单脚本分批删除（不用通配符递归）→ 落地核对 → 聚焦测试。历史清扫日志见 `archive/[架构师+运维看]WORKSPACE_DIRECTORIES.md`。

# T-M5-005 `release-evidence`

**状态**：in_progress；本任务功能/证据提交与治理事实提交均已进入 master、完整质量门既有证据通过，原生 Electron UAT 部分完成；Git 集成事实已实时核验但不替代未完成的 UAT。独立复核 A/B P0/P1=0。
**盘点日期**：2026-08-15
**任务**：T-M5-005
**填写规则**：空白字段和未覆盖路径不得解释为通过；T-M5-005 证据消费 T-M5-009 基线。


## 1. 基本信息

| 字段 | 值 |
|---|---|
| task-id / release-id | `T-M5-005` / `T-M5-005-native-uat-20260814` |
| 日期（绝对日期） | `2026-08-14` |
| 分支 / commit | `agent/T-M5-005-s6-s7-tts-backup-settings-ux` / `112da31`（已 ff-only 合并并推送 master；治理事实 `87d40f8` 已推送） |
| 数据根模式 | `isolated` |
| 运行根 | `H:\pi-studybuddy-tmp\runs\T-M5-005\` |
| 版本 / Node / pnpm / Electron | `源码工作台 / Node24.14.0 / pnpm11.20.0 / Electron36.9.5` |
| 变更范围 | renderer TTS 入口、overwrite 确认、T-M5-009 追溯消费 |
| 非范围与停止条件 | T-M5-006 依赖自包含、T-M5-007 干净机、T-M5-008 发行；真实恢复/升级/卸载未覆盖 |

## 2A. 干净 Windows 验收交接

用户将重装干净 Windows，并在新系统运行 setup。以下三条仍为未完成验收，不得解释为当前源码工作台或 renderer E2E 已通过：

| 路径 | 新系统必须完成的可见操作 | 必须保留的证据 |
|---|---|---|
| S6 报告投递后重启回读 | 已安装应用中完成报告生成、投递、退出/重启、重新进入报告并确认投递状态；必要时验证失败后的可见恢复动作 | 步骤截图/DOM/状态文件，且不含完整 UUID、绝对路径、密钥或错误栈 |
| 真实备份恢复后业务数据回读 | 已安装应用中通过原生 ZIP 选择器选择备份，执行恢复，确认业务数据回到界面，再退出/重启回读 | 原生选择器、恢复结果、重启后业务数据的步骤级截图/状态证据 |
| TTS 原生复习持久化 | 已安装应用中进入可持久化引用目标，朗读并点击“标记已复习”，退出/重启后确认状态保留 | 操作前、标记后、重启后可见 UI 证据 |

本交接不改变 T-M5-005 的 `in_progress` 状态；用户验收前不启动 T-M5-006~008。


## 2. 追溯矩阵摘要

| TRACE-ID | ACT/CTRL | ERR | DATA | TEST/E2E | UAT | OPS | 状态 |
|---|---|---|---|---|---|---|---|
| TRACE-S1-RESTART-001 | ACT-S1-002 | ERR-STATE-001 | DATA-BIZ-001/002 | native Electron | `23..28-restart-*.png` | OPS-START-001 | 已证实 |
| TRACE-SHELL-NAV-001 | ACT-SHELL-001 | ERR-UI-001 | 无直接写入 | native Electron | `30-management-maximized.png` | OPS-START-001 | 已证实 |
| TRACE-SETTINGS-001 | ACT-SETTINGS-001 | ERR-SQLITE-001 | DATA-CFG-003 | renderer/RPC + native + settings restart probe | `21-settings-opened.png`, `22-settings-save-feedback.png`, `60-argv-settings-61-after-relaunch-settled.png`, `settings-restart-e2e/case-01/phase-one.json` | OPS-SEC-001 | 已证实：后续纯 UI 重启回读显示 61；早期 `phase-two.json` 失败事实保留为历史 |
| TRACE-S7-001 | ACT-S7-001 | ERR-FILE-001/ERR-DEPENDENCY-001 | DATA-FILE-* | renderer/E2E + native | `37..39-capture-*.png` | OPS-DEP-001 | 阻塞：原生 WAV 选择已完成，成功 whisper 转写/结果重启回读未覆盖；受控 Electron 回归 2/2 通过 |
| TRACE-TTS-001 | ACT-TTS-001 | ERR-DEPENDENCY-001 | review event | renderer contract/E2E | native content entry未到达；受控 Electron TTS 1/1 | OPS-DEP-001 | 部分证据：引用目标可标记自动化通过；报告等无引用目标不再显示标记；原生已复习持久化未覆盖 |
| TRACE-BACKUP-001 | ACT-BACKUP-001 | ERR-BACKUP-001 | DATA-FILE-003 | renderer/RPC + renderer/E2E | `84..99-backup-*.png` | OPS-BACKUP-001 | 部分证据：zip/覆盖确认/历史与调度重启已有；恢复后业务数据完整性/重启回读未覆盖；受控 Electron 回归 1/1 通过 |
| TRACE-S6-001 | ACT-S6-001 | ERR-STATE-001 | DATA-BIZ-* | renderer contract/E2E + native | `70..78-s6-*.png`, `78-s6-report-detail-frozen-uia.json` | OPS-REPORT-001 | 部分证据：生成/详情/冻结/朗读已有，投递目标配置与投递重启循环未覆盖；受控 Electron 回归 2/2 通过 |

## 3. 自动化质量门

| 门禁 | 命令/证据 | 结果 | 运行根相对路径 | 备注 |
|---|---|---|---|---|
| type-check | `pnpm type-check`（Node24） | PASS | terminal evidence | 本轮 TTS 修正后 Type Errors 0 |
| unit/integration | 完整 Node24 `verify --stage=full`（此前 Git 收口）+ 本轮串行定向 | PASS：此前 132 files / 1199 tests；TTS 定向 11/11 + renderer UX 4/4 + AppShell/report RPC 合计 27/27 | terminal evidence | 既有 React `act(...)` warnings 保留；并行误用导致的 OOM 未计为业务失败 |
| Electron E2E | 本轮单 worker 逐文件过滤运行 | PASS：TTS 1/1、报告 2/2、备份 1/1、采集 2/2、设置 1/1 | `e2e-tts-review/` 等隔离根 | renderer automation 不替代原生 UAT |
| build | `pnpm build`（Node24） | PASS：61 modules transformed | terminal evidence | 并行批次中完成；未发现构建错误 |
| contract/security | 此前完整 Node24 `verify --stage=full` | PASS：128 handlers；安全 6/6 | terminal evidence | 本轮未改 contract/security |
| docs/diff-check | `node scripts/check-docs-governance.mjs`；`git diff --check` | PASS | terminal evidence | 14 份设计文档、2 Skill、2 prompt；无空白错误 |

## 4. 真机 UAT（必填，不得降级偷换）

| UAT-SHELL-SETTINGS-20260814 | 是 | 最大化→设置→保存 61→重启→设置页可见回读 61 | 是 | `native-uat-20260814/evidence/21-settings-opened.png`, `22-settings-save-feedback.png`, `60-argv-settings-61-after-relaunch-settled.png` | 无 | PASS |
| UAT-S7-CAPTURE-20260814 | 是 | 采集→勾选合规→原生 WAV 文件选择器→空态检查 | 成功转写/结果重启回读未完成 | `native-uat-20260814/evidence/37..39-capture-*.png` | 无 | 部分证据/阻塞 |
| UAT-S6-TTS-BACKUP-20260814 | 是 | 报告详情、朗读目标、备份恢复 | 投递重启和恢复后业务数据回读未完成；TTS 原生复习持久化未完成 | `70..99` 相关截图、`78-s6-report-detail-frozen-uia.json` | 无 | 部分证据 |
> 早期白屏/退出事实保留于 `native-uat-20260814/evidence/01..04-*.png`；不以该失败替代后续已可交互实例，也不删除失败证据。

## 5. 数据、安装与运维证据

> `settings-restart-e2e/case-01/phase-two.json` 的早期失败（`saved daily target was not reloaded`）保留为历史证据；后续真实 Electron 纯 UI 回读截图和隔离 `settings.json` 均显示 `61`，因此设置闭环当前按 PASS 记录。
- [ ] SQLite 建库/连接关闭/WAL/SHM 句柄证据存在。
- [ ] 文件—数据库双写、失败补偿、孤儿文件处理：显式未覆盖。
- [ ] 首次启动与再次启动有证据；异常退出后再启动：未覆盖。
- [ ] 备份、恢复、升级、卸载和数据保留策略：未覆盖。
- [x] 运行依赖边界已登记；whisper 自包含转交 T-M5-006。
- [x] 已检查应用可见区域，无完整 UUID、绝对路径、密钥、错误栈或原始异常；原生文件选择器路径仅在证据截图中可见。

## 6. Git 与治理收口

| 要件 | 证据 | 结果 |
|---|---|---|
| docs/04 任务登记 | `docs/04-任务清单-Todo-List.md:T-M5-005` | PASS（任务仍 in_progress；部分 UAT/未覆盖范围已同步） |
| master 集成与复验 | `112da31` 已 ff-only 合并 master；`C:\node-v24.14.0-win-x64\node.exe scripts/verify.mjs --stage=full` | PASS：132 files/1199 tests、33 files/141 Electron E2E、contract 128/128、安全 6/6、build/smoke/docs-governance |
| origin/master 推送核验 | `git rev-parse HEAD`、`git rev-parse origin/master`、`git merge-base --is-ancestor 112da31 HEAD` | PASS：实时 `HEAD=origin/master=2442646cfcfa07c0b1f84de882816a9990c2bd24`；`112da31` 与 `87d40f8` 均为其祖先 |
| `.record` 八章节 | `.record/T-M5-005-实施记录.md` | PASS（本轮记录） |

只有上述三项 Git/治理要件齐全，才可依据 AGENTS.md §8.4 报告任务完成。

## 7. 审查状态

独立审查已完成：第三轮代码审查与治理审查均确认 P0/P1=0；冻结缓存跨学期问题已修复。任务仍未达到收尾条件，原因是 S6 报告投递重启、真实备份恢复后业务数据回读、TTS 原生已复习持久化等原生 UAT路径未完成，且用户签收尚未取得；不得将自动化回归或审查 PASS代替原生 UAT。

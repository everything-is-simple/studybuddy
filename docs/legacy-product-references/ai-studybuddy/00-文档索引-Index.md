# AI StudyBuddy 文档索引

**版本**：v2.61
**日期**：2026-07-28
**用途**：这是本项目所有设计文档的导航中心和单一事实来源（SoT）。AI Agent 和开发者在开始任何任务前，必须先读本文件。

---

## 一、当前有效文档

| 编号 | 文档名                                                                                                                                | 状态    | 用途                                                                                   |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------- |
| 00   | [文档索引-Index.md](00-文档索引-Index.md)                                                                                             | ✅ 有效 | 本文件，文档导航、文档门禁和触发状态                                                   |
| 01   | [总PRD-产品需求-Product-Requirements.md](01-总PRD-产品需求-Product-Requirements.md)                                                   | ✅ 有效 | 系统为何存在、为谁而做、考试驱动学习闭环、MVP 与部署边界                               |
| 02   | [七子系统地图-Scenario-Systems.md](02-七子系统地图-Scenario-Systems.md)                                                               | ✅ 有效 | 七个场景子系统边界、共同业务对象、依赖关系、开发顺序                                   |
| 03   | [subsystems/03-S1学习节奏子系统PRD-StudyRhythm.md](subsystems/03-S1学习节奏子系统PRD-StudyRhythm.md)                                  | ✅ 有效 | S1 轻量 PRD，课程、考试、任务、StudyEvent 与时间线                                     |
| 03b  | [subsystems/03-S2-资料笔记子系统PRD-NoteBuilder.md](subsystems/03-S2-资料笔记子系统PRD-NoteBuilder.md)                                | ✅ 有效 | S2 轻量 PRD，资料上传/格式转换/AI 笔记/知识模块                                        |
| 03c  | [subsystems/03-S3-限时练习子系统PRD-PracticeRunner.md](subsystems/03-S3-限时练习子系统PRD-PracticeRunner.md)                          | ✅ 有效 | S3 轻量 PRD，知识模块驱动练习、客观题批改、练习记录                                    |
| 03d  | [subsystems/03-S4-错题改错子系统PRD-ErrorFixer.md](subsystems/03-S4-错题改错子系统PRD-ErrorFixer.md)                                  | ✅ 有效 | S4 轻量 PRD，错误作答事实、错因确认、重做证据、薄弱点与掌握边界                        |
| 03f  | [subsystems/08-S5-期末冲刺子系统PRD-ExamCrammer.md](subsystems/08-S5-期末冲刺子系统PRD-ExamCrammer.md)                                | ✅ 有效 | S5 轻量 PRD，模拟考、临考速背、冲刺计划与考前工作台入口边界                            |
| 03e  | [subsystems/06-S6-家长观察子系统PRD-ParentReport.md](subsystems/06-S6-家长观察子系统PRD-ParentReport.md)                              | ✅ 有效 | S6 轻量 PRD，脱敏日报/周报/月报/考前提醒与家长报告隐私边界                             |
| 03g  | [subsystems/07-S7-课堂录音子系统PRD-ClassCapture.md](subsystems/07-S7-课堂录音子系统PRD-ClassCapture.md)                              | ✅ 有效 | S7-MVP：受控本地 WAV、同步本机 ASR、可编辑文本与 S2 文本资料 handoff；完整 S7 另立门禁 |
| 04   | [开发任务清单-Todo-List.md](04-开发任务清单-Todo-List.md)                                                                             | ✅ 有效 | 阶段任务、执行顺序、完成门槛和验证结论                                                 |
| 05   | [开源组件装配-Open-Source-Foundation.md](05-开源组件装配-Open-Source-Foundation.md)                                                   | ✅ 有效 | 成熟开源组件先行装配规则、smoke test 标准                                              |
| 06   | [本地目录治理-Dev-Environment.md](06-本地目录治理-Dev-Environment.md)                                                                 | ✅ 有效 | `H:\ai-studybuddy-*` 本地目录职责、外部试炼场、验证产物与单机数据边界                  |
| 07   | [文档策略-Design-Docs-Strategy.md](07-文档策略-Design-Docs-Strategy.md)                                                               | ✅ 有效 | 文档分层、子系统文档触发条件                                                           |
| 08   | [共同底座架构-Architecture.md](08-共同底座架构-Architecture.md)                                                                       | ✅ 有效 | 共同底座架构、Adapter、Job、数据对象和跨子系统边界                                     |
| 09   | [测试验收计划-Test-Plan.md](09-测试验收计划-Test-Plan.md)                                                                             | ✅ 有效 | 历史验收记录 + 第十四章“当前版本验收矩阵”（v0.8.1 全系统验收基线）                                                    |
| 10   | [后端开发规范-Backend-Guidelines.md](10-后端开发规范-Backend-Guidelines.md)                                                           | ✅ 有效 | 后端目录结构、SQLite、Adapter、AI Provider、日志和环境变量约定                         |
| 11   | [前端开发规范-Frontend-Guidelines.md](11-前端开发规范-Frontend-Guidelines.md)                                                         | ✅ 有效 | React/Vite 前端结构、API 信封、上传轮询、笔记渲染安全与 T08 验收规范                   |
| 12   | [开发规范-Dev-Rules.md](12-开发规范-Dev-Rules.md)                                                                                     | ✅ 有效 | 工具无关 16 步协作流程、分支/worktree、多 Agent、验证、隐私和提交规则                  |
| 13   | [部署运维指南-Deployment.md](13-部署运维指南-Deployment.md)                                                                           | ✅ 有效 | Windows 原生部署包、受控前置运行时、生产启停、检查、备份恢复、升级回滚和任务计划       |
| 14   | [项目代码百科-Code-Wiki.md](14-项目代码百科-Code-Wiki.md)                                                                             | ✅ 有效 | 系统代码、部署边界与模块导航百科；用于测试、维护与审计定位                             |
| 15   | [前端信息架构与界面范围研究-Frontend-Information-Architecture.md](15-前端信息架构与界面范围研究-Frontend-Information-Architecture.md) | ✅ 有效 | 基于当前路由和产品边界研究学生端信息架构、页面范围与后续界面候选项；不替代独立实施门禁 |

---

## 一点五、先读事实层：为什么、为谁、什么已经完成

- **产品目的与使用者**：`docs/01` 是首要入口。系统为一名在 Windows 本机学习的学生而做，帮助她把课程/考试目标、学习节奏、资料笔记、练习、错题和考前冲刺连成可持续闭环；家长不是系统操作者，只接收脱敏的异步学习摘要。
- **已集成事实**：只有 `origin/master` 上的代码、`docs/04` 任务状态和主线复验共同构成“已完成”结论。当前 S1–S6 主线已完成；开发机 Windows 原生 + Node 24 部署基线已验证，但用户电脑的安装运行验收仍是未完成门禁。
- **S7 与外部候选边界**：S7-MVP 已完成主线复验并推送 `origin/master`：目标仅为受控 PCM WAV → 显式本机 `whisper.cpp` → 可编辑文本 → S2 文本资料。旧外部 ASR/FFmpeg 候选的能力卡、harness 或隔离证据仍不等于完整 S7、通用静音、G2、T02 主线、用户机能力或 Phase 3。
- **当前治理/实施项**：Phase 3 的 T02A–T02G 已完成各自批准范围的主线复验并进入 `origin/master`；T02G 仅完成仓库外合成夹具安全边界，真实 ACL、真实 backup/restore 与恢复写入仍未完成。用户于 2026-07-28 仅重新开放 11 个高权重必做项的恢复规划：T02-R1、T02-R2、T04-1～T04-3、T02-R3、T05-1～T05-3、T02-R4、T02-R6；它们等待独立审查与逐项实施，其余 Phase 3 任务继续未完成。Docker/WSL、G2/外部 ASR 主线、完整 S7、S3 Worker 和用户电脑验收仍是各自独立门禁。
- `H:\ai-studybuddy` 是当前主系统 Git 仓库；这里只保存有效设计文档、正式实现和可审计结论。`H:\ai-studybuddy-composer` 是独立的本机组件试炼场，不加入主仓库 workspace，不作为主系统源码目录。
- 试炼场中的 `.env.local`、`.venv`、`node_modules`、测试输出、真实凭据和临时素材不得复制或提交到主仓库。试炼场验证通过不等于产品已接入；必须先回填有效编号文档，再在主仓库按 Adapter/API/UI 边界重新实现。
- **worktree 脏状态与目录边界治理**：未提交状态不是产品完成或失败结论，也不等于可删除垃圾。当前安全收口计划为 `.plans/process-dirty-state-remediation-plan.md`，其索引和批准状态见 `docs/04`；唯一允许的新任务 worktree 根目录是 `H:\ai-studybuddy-worktrees`，`H:\ai-studybuddy` 内严禁创建或保留 `.worktrees` 根。任何语义改动、生成物或依赖残留都必须先分类、核对绝对路径并取得相应批准，不能用 `git clean`、`git reset --hard` 或覆盖 checkout 处理。

---

## 二、子系统轻量 PRD 触发规则

| 子系统      | PRD 文档                                               | 当前状态                                                                                                                           | 触发条件                                                     |
| ----------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| S1 学习节奏 | `subsystems/03-S1学习节奏子系统PRD-StudyRhythm.md`     | ✅ 已创建，MVP 已实现                                                                                                              | Phase 0.8 必需                                               |
| S2 资料笔记 | `subsystems/03-S2-资料笔记子系统PRD-NoteBuilder.md`    | ✅ 已创建，MVP 已实现                                                                                                              | Phase 0.8 开始开发 S2 前触发                                 |
| S3 限时练习 | `subsystems/03-S3-限时练习子系统PRD-PracticeRunner.md` | ✅ MVP 已完成：Schema、生成、提交批改与前端闭环均已验收                                                                            | S2 MVP 完成后触发                                            |
| S4 错题改错 | `subsystems/03-S4-错题改错子系统PRD-ErrorFixer.md`     | ✅ MVP 闭环已完成：T04A Schema/归档、T04B 错题改错前端与 T05 回流规则均已验收                                                      | S3 MVP 完成后触发                                            |
| S5 期末冲刺 | `subsystems/08-S5-期末冲刺子系统PRD-ExamCrammer.md`    | ✅ Phase 2-T01–T06 与 POST-PHASE2 全系统验证、完整 E2E、文档对齐和主线复验均已完成并推送                                           | Phase 2 已触发并完成                                         |
| S6 家长观察 | `subsystems/06-S6-家长观察子系统PRD-ParentReport.md`   | ✅ T06A 规则报告生成与 T06B 渠道推送已实现；真实渠道 smoke 非常规验证                                                              | Phase 1 后期、准备正式发送家长报告前触发                     |
| S7 课堂采集 | `subsystems/07-S7-课堂录音子系统PRD-ClassCapture.md`   | ✅ S7-MVP 已完成主线复验并推送 `origin/master`：受控 WAV 同步转写、编辑、显式保存为 S2 文本资料；旧候选能力仍为 `PARTIAL`/历史事实 | 不含 Worker、FFmpeg、云端、G2、实时录音、用户机验收或完整 S7 |

---

## 三、未来文档触发条件

| 文档                                   | 触发条件                                                  | 当前状态                            |
| -------------------------------------- | --------------------------------------------------------- | ----------------------------------- |
| 08-共同底座架构-Architecture.md        | 设计共同数据模型、队列、对象存储、AI Provider、Adapter 前 | ✅ 已创建（Phase 0.7/0.8）          |
| 09-测试验收计划-Test-Plan.md           | 调通第一个开源组件 smoke test 前                          | ✅ 已创建（Phase 0.5）              |
| 10-后端开发规范-Backend-Guidelines.md  | 写第一个后端服务 / Adapter / API / Worker 前              | ✅ 已创建（Phase 0.8 T03）          |
| 11-前端开发规范-Frontend-Guidelines.md | 写第一个正式前端页面前                                    | ✅ 已创建（Phase 0.8 T08）          |
| 12-开发规范-Dev-Rules.md               | 多 AI / 多分支 / 多 worktree 协作时                       | ✅ 已创建（Phase 1-T00）            |
| 13-部署运维指南-Deployment.md          | Phase 1 完成后准备部署时                                  | ✅ 已创建（PROCESS-RUNTIME-DEPLOY） |
| 14-安全与隐私-Security-Privacy.md      | Phase 1 后期或真实家庭试用前                              | 未触发                              |

---

## 四、旧草稿归档

旧草稿已归档到仓库外备份目录。除非用户明确要求做历史考证，不要恢复到 `docs/`，也不要把旧文件名重新放回当前有效文档。禁止恢复的旧名包括但不限于：`PRD.md`、`ARCHITECTURE.md`、`todo-list.md`、`backend-guidelines.md`、`frontend-guidelines.md`、`dev-rules.md`。

---

## 五、文档门禁规则

### 5.1 文档创建前检查清单

1. 先读本索引。
2. 检查目标文档是否已经存在。
3. 检查触发条件是否满足。
4. 不满足触发条件：不创建，只说明“还不到创建时机”。
5. 满足触发条件：按命名规范创建。
6. 同一次修改必须更新本索引。
7. 提交前必须运行 `scripts/check-docs-governance.ps1`。

### 5.2 文档命名规范

正式文档命名：

```text
NN-中文标题-English-Title.md
```

示例：

```text
01-总PRD-产品需求-Product-Requirements.md
12-开发规范-Dev-Rules.md
```

子系统 PRD 放在 `docs/subsystems/` 下，并遵守同样的编号与中英命名规则。

### 5.3 提交前验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1
git diff --check
```

---

## 六、文档阅读顺序

### 6.1 第一次接触本项目

1. 本文件（00-文档索引）；
2. [01-总PRD-产品需求](01-总PRD-产品需求-Product-Requirements.md)；
3. [02-七子系统地图](02-七子系统地图-Scenario-Systems.md)；
4. [07-文档策略](07-文档策略-Design-Docs-Strategy.md)；
5. [12-开发规范](12-开发规范-Dev-Rules.md)。

### 6.2 准备后端或前端开发

1. [04-开发任务清单](04-开发任务清单-Todo-List.md)；
2. [08-共同底座架构](08-共同底座架构-Architecture.md)；
3. [10-后端开发规范](10-后端开发规范-Backend-Guidelines.md) 或 [11-前端开发规范](11-前端开发规范-Frontend-Guidelines.md)；
4. 相关子系统 PRD；
5. [12-开发规范](12-开发规范-Dev-Rules.md)。

### 6.3 准备 Phase 1

1. 重读 S1/S2/S3/S4 PRD 与最新验收结论；
2. Phase 1-T00、T10、T02、T03、T11、T03A、T03B、T03C、T03D、T04、T04A、T04B、T05、T07、T08、T09A、T09B、T09C、T09D 与 T09E 已完成；S3 已完成 Schema、练习生成/提交批改 API、前端发起/作答/结果闭环、练习历史与归档学期只读查看，S4 已完成错题归档、错题改错前端与回流规则，T07 已在考试工作台展示当前课程近期时间线活动，T08 已提供本机配置中心与连接验收；
3. S6 家长观察 PRD、T06A 规则报告生成和 T06B 渠道推送已完成并登记；T06B 使用 `report:<date>` 冻结脱敏快照，按 `report_key + channel` 去重和独立重试，SMTP/飞书均失败时保留本机脱敏 HTML 与固定错误摘要，真实渠道 smoke 仍不是常规验证依赖；
4. T09A–T09E、T12、M01、M02、M03 与 Post-M03 均已完成并进入远端主线；Phase 2-T01–T06 也已完成主线复验并推送，S5 当前包含模拟考、确定性只读临考速背、确定性即时只读冲刺计划和考试工作台冲刺区。POST-PHASE2 全系统验证、完整 E2E、文档对齐与主线复验已完成并推送 `origin/master`；开发机 Windows 原生 + Node 24 基线已验证，用户电脑安装运行仍待目标机器验收。Phase 3 的 T02A–T02G 已完成各自主线复验并进入 `origin/master`；T02G 的计划、实现、文档与 P1 修复均已完成独立审查、快进集成和主线验证，且不授权真实 ACL、备份或恢复写入。用户于 2026-07-27 明确暂停 T02 剩余工作，并冻结 T02G 之后全部开发机 Phase 3 任务；2026-07-28 的 `PHASE3-REOPEN-HIGH-WEIGHT-20260728` 仅对 T02-R1、T02-R2、T04-1～T04-3、T02-R3、T05-1～T05-3、T02-R4、T02-R6 有限重新开放，仍待独立审查与逐项实施，未纳入任务继续暂停；T02 与 Phase 3 均未完成。S7-MVP 已完成主线复验并推送 `origin/master`：它只覆盖受控 WAV、本机同步 `whisper.cpp`、可编辑文本及显式 S2 handoff；旧 T02/T04 外部候选能力仍为 `PARTIAL`、T03 Composer smoke 为 `PASS`，不等于完整 S7、通用静音、G2 或用户机验收。S3 Worker 不属于当前 MVP。
5. `docs/04` 的“Phase 1 行动计划索引”是任务与 `.plans/` 的对应 SoT；T09A 的 v4 计划、实现、主线复验和 `origin/master` 推送均已完成；前端维护任务 M01 也已完成：任务分支 `codex/phase1-m01-markmap-chunk-optimization` 的实现提交 `57b8612` 与验证证据提交 `6f5abcb` 已 fast-forward 合入 `master` 并推送 `origin/master`。主线复验通过文档治理、`git diff --check`、`pnpm type-check`、后端/前端 build、隔离 `pnpm test`（前端 64/64、后端 215/215）和专项 Playwright E2E（2/2）；`katex` 535.51 kB warning 仍是独立遗留项。T09B/T09C 已完成；T09D 计划、实现、独立复审修复、主线集成、主线复验与 `origin/master` 推送已完成；T09E 计划、实现、主线集成、主线复验与 `origin/master` 推送已完成，验证隔离根 `I:\ai-studybuddy-tmp\runs\phase1-t09e-master-verify-20260719-001`。

---

## 七、AI Agent 专用规则

### 7.1 每次任务开始前

1. 先读 `docs/00-文档索引-Index.md`；
2. 确认当前产品事实以 `01-总PRD` 和 `02-七子系统地图` 为准；
3. 读取 `docs/12-开发规范-Dev-Rules.md` 的 16 步流程；
4. 旧归档草稿和外部参考项目不作为当前执行依据。

### 7.2 新增设计文档前

1. 检查是否满足本文件中的触发条件；
2. 不满足：不创建，向用户说明“还不到创建时机”；
3. 满足：按命名规范创建，并同步更新本索引表。

### 7.3 禁止行为

- ❌ 不要凭记忆新建文档；
- ❌ 不要从旧 zip 或外部参考项目直接恢复旧稿到 `docs/`；
- ❌ 不要硬编码任何盘符路径到业务代码中；
- ❌ 不要提交真实密钥、Provider URL、资料原文、完整 UUID 或正式运行数据；
- ❌ 不要跳过文档门禁和 `docs/12` 的批准流程。

---

## 八、版本历史

| 版本  | 日期       | 变更                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| v2.63 | 2026-07-28 | 澄清 `6.3` 中 2026-07-27 的历史冻结记录已由同日 `PHASE3-REOPEN-HIGH-WEIGHT-20260728` 对指定 11 项有限替代；未纳入任务继续暂停，未表示 T02 或 Phase 3 完成。                                                                                                                                                                                                                                                  |
| v2.62 | 2026-07-28 | 同步用户重新开放 Phase 3 高权重必做项的恢复计划：仅纳入 T02-R1、T02-R2、T04-1～T04-3、T02-R3、T05-1～T05-3、T02-R4、T02-R6；计划待独立审查和逐项实施，不表示 T02、Phase 3、真实恢复、生产上线或用户电脑验收完成。                                                                                                                                                                                            |
| v2.61 | 2026-07-26 | T02G 已完成 P1 修复、独立审查、rebase、`master` 快进合并、合并后脚本/文档/类型复验并推送 `origin/master`（`6f5ecdd`）。该切片仅覆盖仓库外合成夹具边界；不表示 T02、Phase 3、真实 ACL/备份/恢复、生产上线或用户电脑验收完成。                                                                                                                                                                                 |
| v2.60 | 2026-07-26 | 同步 Phase 3 T02 实施事实：T02A–T02F 已各自完成主线复验并进入 `origin/master`；T02G 实现提交 `b5c6783` 已在任务分支完成合成夹具的路径/ACL 只读证据、v2 backup manifest 和 restore `-WhatIf` fail-closed 验证，正待独立审查/集成。该记录不表示 T02G、T02、Phase 3、安全审计、真实 ACL/备份/恢复、生产上线或用户电脑验收完成。                                                                                 |
| v2.59 | 2026-07-26 | PHASE3-T02C 实现提交 `3a0b6bf` 已安全 fast-forward 集成到本机 `master`，并完成主线复验：Windows 原生 Node 24、仓库外隔离根、后端 build、T02C 专项与 T02A/T02B 相邻边界测试共 47/47、`pnpm type-check`、前端测试、文档治理和 `git diff --check` 均通过；外部服务配置保持为空，未调用真实服务。实现、主线复验与文档状态提交已推送 `origin/master`，不等于 T02、Phase 3、安全审计、生产上线或用户电脑验收完成。 |
| v2.58 | 2026-07-26 | 创建 PHASE3-T02C 配置加载与环境错误脱敏实施计划 `.plans/phase3-t02c-env-error-redaction-plan.md`，登记 `docs/04` Phase 3 行动计划索引；范围仅限 `.env`/运行环境解析、配置校验错误和脚本检查摘要的秘密回显边界。当前仅为计划已创建并完成计划阶段审查，等待用户单独批准实施，不等于 T02C 实施、T02、Phase 3、安全审计、生产上线或用户电脑验收完成。                                                            |
| v2.57 | 2026-07-26 | PHASE3-T02A 状态补正与最新主线复验：实现提交 `7f976a0` 已在 `origin/master` 历史中，本轮基于 `533e6f2` 确认无需额外合并并完成 Node 24 主线复验；后端 build、T02A 专项 16/16、`pnpm type-check`、前端 Vitest 26 files / 139 tests、完整 `pnpm test`（后端 272/272）、文档治理和 `git diff --check` 均通过。范围仍仅限生产攻击面与统一错误边界，不等于 T02、Phase 3、安全审计、生产上线或用户电脑验收完成。    |
| v2.56 | 2026-07-26 | PHASE3-T02B 已推送 `origin/master`：实现提交 `eeb9cb1` 与主线复验文档提交 `7281229` 已进入远端主线；随后更新本文档与 `docs/04`/计划文件为远端已推送状态。范围仍仅限 OCR/whisper.cpp 子进程环境最小化与安全输出回归，不等于 T02、Phase 3、安全审计、生产上线或用户电脑验收完成。                                                                                                                              |
| v2.55 | 2026-07-26 | PHASE3-T02B 已 fast-forward 集成到本机 `master` 并完成主线复验：Node 24、后端 build、T02B/OCR 专项 7/7、`pnpm type-check`、前端 Vitest 26 files / 139 tests、文档治理、`git diff --check` 和完整 `pnpm test`（后端 272/272）均通过；仅既有 KaTeX chunk warning。尚未推送 `origin/master`，不得宣称远端主线、T02、Phase 3、安全审计或用户电脑验收完成。                                                       |
| v2.54 | 2026-07-26 | 同步 PHASE3-T02B 任务分支实现、专项验证与独立审查完成：OCR/whisper.cpp 子进程改为正向环境 allowlist，OCR 错误输出脱敏；后端分拆全量、前端测试、type-check、文档治理和 diff 检查通过。完整 `pnpm test` 受本机既有代理/浏览器连接占用固定端口 `59402` 影响出现单项既有测试失败；未合入 `master` 或推送 `origin/master`，不得宣称 T02B、T02、Phase 3、安全审计或用户电脑验收完成。                              |
| v2.53 | 2026-07-26 | 登记 PHASE3-T02B 独立实施计划及其 `docs/04` 行动计划索引：范围只限 OCR 与 whisper.cpp 子进程环境最小化和安全输出回归；当前为任务分支验证/独立审查阶段，未合入 `master` 或推送 `origin/master`。                                                                                                                                                                                                              |
| v2.52 | 2026-07-25 | 同步 `docs/04` 流程状态：`9ed5bc1` 部署候选已通过 `b72e8b0` 收口进入 `origin/master`；Phase 3 启动治理/计划阶段；历史 worktree / 暂停计划继续审计清理。                                                                                                                                                                                                                                                      |
| v2.51 | 2026-07-25 | S7-MVP 已完成主线复验并推送 `origin/master`；功能边界仍只限受控 WAV、本机同步转写、可编辑文本与显式 S2 handoff，不扩大为完整 S7、G2、T02 主线、用户机验收或 Phase 3。                                                                                                                                                                                                                                        |
| v2.50 | 2026-07-25 | S7-MVP 已 fast-forward 至本机 `master` 并完成主线复验，待推送 `origin/master`；仍不扩大为完整 S7、Worker、FFmpeg、云端、G2、用户机验收或 Phase 3。                                                                                                                                                                                                                                                           |
| v2.49 | 2026-07-25 | 登记并同步 S7-MVP：仅受控 PCM WAV 的本机同步转写、学生编辑与显式 S2 文本资料 handoff；实施中，不扩大为 Worker、FFmpeg、云端、G2、用户机验收或完整 S7。                                                                                                                                                                                                                                                       |
| v2.48 | 2026-07-25 | 固化用户的主系统目录边界：`H:\ai-studybuddy` 内禁止任何 worktree 根，唯一的新任务 worktree 根为 `H:\ai-studybuddy-worktrees`；历史仓内 worktree 只可按批准清单迁出或安全处置。                                                                                                                                                                                                                               |

| v2.47 | 2026-07-25 | 登记多 worktree 脏状态的安全收口计划：语义差异、待审计划、生成物、依赖残留和外部证据必须分层治理；不以清理之名丢失内容，也不改变产品/用户机/S7 的既有边界。 |
| v2.46 | 2026-07-25 | 收口产品目的、使用者、主线事实、S7 候选证据与产品接入边界；明确开发机 Node 24 已验证不等于用户电脑验收，并区分当前 H 盘开发机治理与历史绝对路径。 |
| v2.44 | 2026-07-21 | Phase 1.5-T01：创建并登记 S7 课堂采集子系统 PRD，明确课堂录音经本地 ASR 转为纯文本并复用 S2 笔记管道；T02–T06 保持未启动，下一门禁为 T02 composer smoke 独立计划。 |
| v2.43 | 2026-07-21 | 同步 POST-PHASE2 分支与主线全量测试、完整 E2E、文档对齐和最终推送均已完成；Phase 3 继续暂缓。 |
| v2.42 | 2026-07-21 | 同步 Phase 2-T01–T06 已完成主线复验并推送、POST-PHASE2 全系统验证与文档对齐进行中，以及 Phase 3 暂缓的当前状态。 |
| v2.41 | 2026-07-20 | Phase 2-T01：在 S3 练习与 S4 错题稳定运行门禁满足且用户明确批准后，创建并登记 S5 期末冲刺子系统 PRD；下一门禁为 Phase 2-T02 模拟考 Schema 与生成独立计划，T02–T06 尚未启动，S7 仍按门禁等待 |
| v2.40 | 2026-07-20 | 同步系统文档当前状态：确认 T09A–T09E、T12、M01、M02、M03 与 Post-M03 均已完成主线集成、复验并推送 `origin/master`；补齐 T09E 收尾提交 `af37bd5`、M03 收尾提交 `6ddd9fa` 与 Post-M03 收尾提交 `eac469b`，更新前端 14 路由事实基线，并明确当前没有新的已批准业务实施任务 |
| v2.39 | 2026-07-19 | 确认 Phase 1-T09E 主线收尾：任务分支 `codex/phase1-t09e-practice-history-archive` 的实现提交 `de5c41e` 已 fast-forward 合入 `master`；主线复验通过文档治理、`git diff --check`、`pnpm type-check`、后端/前端 build、隔离 `pnpm test`（后端 223/223、前端 20 files / 92 tests）与专项 Playwright E2E（T09E 练习历史归档 1/1、学期选择回归 1/1）；主线收尾提交 `af37bd5` 推送 `origin/master`；仅做主线收尾、文档证据和测试端口稳定性最小修复，未扩大业务范围 |
| v2.38 | 2026-07-19 | 登记 Phase 1-T09E：练习历史与学期归档已获用户明确批准并在任务分支 `codex/phase1-t09e-practice-history-archive` 完成分支实现与验证：练习历史、学期归档、归档只读写保护和 Playwright 验收通过；尚未合入 `master` 或推送 `origin/master`，主线完成仍待后续合入复验 |
| v2.37 | 2026-07-19 | 登记 Phase 1-T09E：练习历史与学期归档独立实施计划 `.plans/phase1-t09e-practice-history-archive-plan.md` 已创建并完成计划审查；当前计划待批，未获用户明确批准不得实施 |
| v2.36 | 2026-07-19 | 确认 Phase 1-T09D 已推送 `origin/master`：计划提交 `0d2127e`、实现提交 `0a054f8` 与主线收尾提交 `e1034e7` 均进入远端主线；T09E 尚未创建计划，是下一计划门禁 |
| v2.35 | 2026-07-19 | Phase 1-T09D 已完成 fast-forward 主线集成与主线复验：计划提交 `0d2127e`、实现提交 `0a054f8` 进入 master；主线验证通过 docs governance、diff check、type-check、后端/前端 build、隔离 `pnpm test`（后端 220/220、前端 87/87）与全量 E2E 12/12；T09E 尚未创建计划，是下一计划门禁 |
| v2.34 | 2026-07-19 | 登记 Phase 1-T09D 独立复审修复与分支复验：修复时间线跨页锚点、学期切换卸载边界、current 读取失败重试、E2E 动态日期与 Playwright 隔离根守卫；此条记录分支复验节点，主线集成与复验证据见 v2.35，T09E 尚未创建计划 |
| v2.33 | 2026-07-19 | 登记 Phase 1-T09D 全局导航与学生旅程 E2E 分支实现与验证：统一全局导航、考试上下文导航、PageState 与真实 Express/SQLite 学生旅程 E2E；此条为实现分支节点，后续复审与主线证据见 v2.34/v2.35，T09E 尚未创建计划 |
| v2.32 | 2026-07-18 | 补齐 Phase 1-M01 主线完成事实：任务分支 `codex/phase1-m01-markmap-chunk-optimization` 的实现提交 `57b8612` 和验证证据提交 `6f5abcb` 已 fast-forward 合入 `master` 并推送 `origin/master`；主线复验通过文档治理、`git diff --check`、type-check、后端/前端 build、隔离全量测试（前端 64/64、后端 215/215）与专项 E2E（2/2）。Markmap 物理 chunk 为 0.86 kB / 72.44 kB / 320.81 kB；KaTeX 535.51 kB warning 保留为独立遗留，T09B–T09E 未启动 |
| v2.31 | 2026-07-18 | Phase 1-M01 实现、专项 E2E、全量验证与实现复审已通过：笔记页仅在存在导图时动态加载，Markmap 拆为 0.86 kB / 72.44 kB / 320.81 kB 物理 chunk；KaTeX 535.51 kB warning 如实保留为独立遗留；实现提交 `57b8612` 已创建；此条为实现分支节点，后续主线证据见 v2.32 |
| v2.28 | 2026-07-18 | T09A 已 fast-forward 合入 `master` 并推送 `origin/master`：实现提交 `965ee4f`、交付证据 `c796439`、测试稳定性修复 `1649fab`；主线复验通过 type-check、后端/前端 build、全量测试（后端 215/215、前端 61/61）及 E2E（专项 1/1、全量 6/6），T09B–T09E 未启动 |
| v2.30 | 2026-07-18 | Phase 1-M01 v2 已通过独立复审并获用户明确批准；实施分支 `codex/phase1-m01-markmap-chunk-optimization` 已从最新 `origin/master` 创建，当前仅实施该维护任务 |
| v2.29 | 2026-07-18 | 登记 Phase 1-M01 前端 Markmap 按需加载与构建 chunk 治理的 v2 独立计划；已通过独立复审，当前待用户明确批准，尚未实施 |
| v2.26 | 2026-07-18 | 登记 T09A 独立计划 v4 已通过独立复审，当前等待用户明确批准；未批准不得实施 |
| v2.25 | 2026-07-18 | 登记 T09A 独立计划已创建且仍处于独立复审中，未获用户批准不得实施；T09B–T09E 仍仅登记路线 |
| v2.24 | 2026-07-18 | 系统文档一致性同步：纠正 T03/T04/T06/T08 陈旧状态，登记 T09A–T09E 行动计划索引和“先登记、再计划、批准后实现、完成回填”的强制链路 |
| v2.23 | 2026-07-17 | Phase 1-T08：实现本机配置中心、Windows DPAPI 加密配置存储、AI/SMTP/飞书连接测试、运行时热切换、loopback API 防护和前端设置页；下一门禁调整为 T09A 学期创建、选择与切换独立计划 |
| v2.22 | 2026-07-17 | Phase 1-T07：登记 S1 时间线过滤扩展与考试工作台当前课程近期活动已完成；下一门禁调整为 T08 本机配置中心与连接验收独立计划 |
| v2.21 | 2026-07-17 | 将本机配置中心登记为 Phase 1-T08 候选任务，固化 Windows 用户级秘密存储、AI/SMTP/飞书分渠道测试、脱敏状态和功能降级边界；当前下一门禁仍为 T07 |
| v2.20 | 2026-07-17 | 登记前端信息架构与界面范围研究；明确吸收考试工作台枢纽、S6 无家长 Web 页和 S1 时间线优先级，同时禁止以页面数量驱动开发或把渠道/Provider 秘密直接保存到前端 |
| v2.19 | 2026-07-17 | Phase 1-T06B：实现 S6 QQ SMTP/飞书渠道投递、冻结脱敏快照、`report_key + channel` 去重、失败隔离/重试、双渠道失败本机留档和一次性计划任务 runner；下一门禁调整为 T07 S1 时间线扩展独立计划 |
| v2.18 | 2026-07-17 | Phase 1-T06A：实现 S6 脱敏规则报告、可选 AI 摘要降级和报告生成专项测试；下一门禁调整为 T06B 家长报告推送独立计划 |
| v2.17 | 2026-07-17 | Phase 1-T06：创建 S6 家长观察 PRD 并登记索引；下一门禁调整为 T06A S6 家长报告生成独立计划 |
| v2.16 | 2026-07-17 | 同步系统进度：登记 T04B 错题改错前端与 T05 回流规则均已完成，下一门禁调整为 T06 S6 家长观察 PRD；统一 S5/S6/S7 未来 PRD 文件名 |
| v2.15 | 2026-07-16 | Phase 1-T04A：创建学期库 migration v5、`mistakes`/`mistake_evidence`/`weak_points`，实现 S3 提交后错误作答幂等归档与两证据薄弱点；下一门禁调整为 T04B 独立计划与明确批准 |
| v2.14 | 2026-07-16 | Phase 1-T04：创建并登记 S4 错题改错轻量 PRD，明确 S3 错误作答只读输入、错因确认、重做证据、薄弱点多证据原则和隐私边界；下一门禁调整为 T04A 独立计划与明确批准 |
| v2.13 | 2026-07-16 | Phase 1-T03D：登记 S3 前端 API 封装、练习发起/作答/结果页、工作台“练习”区、前端测试与隔离浏览器验收已完成；S3 MVP 完成，S4 PRD 触发条件满足但仍需独立计划和明确批准 |
| v2.12 | 2026-07-16 | Phase 1-T03C：登记 `POST /api/practice-sessions/:id/submit`、客观题规则批改、`practice_answers`、session 汇总字段与 `practice_completed` StudyEvent 已完成；下一门禁调整为 T03D，S4-S7 仍未触发 |
| v2.11 | 2026-07-16 | 修复 master 漂移：将既有 T03A/T03B 分支实现纳入主线状态，入口规则与下一门禁统一为 T03C；S4-S7 仍未触发 |
| v2.10 | 2026-07-16 | Phase 1-T03B：登记 PracticeRunnerService、`POST /api/practice-sessions`、`GET /api/practice-sessions/:id`、作答前隐藏答案 DTO 与 mock AI API 测试已完成；下一门禁调整为 T03C |
| v2.9 | 2026-07-16 | Phase 1-T03B：登记练习生成 API 实施计划已创建并自审，等待用户明确批准；S3 API/Service/Worker/前端仍未开始 |
| v2.8 | 2026-07-16 | Phase 1-T03A：登记学期库 migration v4、S3 三表、11 个索引、8 个一致性 trigger、最小 shared 类型与 127/127 后端、32/32 前端全量验证；下一实现门禁调整为 T03B |
| v2.7 | 2026-07-16 | 登记 Phase 1-T03A 数据库与 Schema 实施计划已创建并待批准；校准 S3 PRD 题目顺序字段与下一门禁状态 |
| v2.6 | 2026-07-16 | Phase 1-T02：登记 Provider 实例级连续失败熔断、10 分钟冷却、恢复探测、全冷却错误和脱敏日志；下一实现门禁调整为 T03A |
| v2.5 | 2026-07-15 | 对齐 S1/S2/S3 子系统 PRD 文件编号；确认 Phase 1-T11 已合并到 master 并完成最终隔离验收；登记 Phase 1-T02 待批准计划 |
| v2.4 | 2026-07-15 | Phase 1-T11：登记考试确认与多考试工作台闭环、正式 API 契约及自动化/浏览器验收证据；修正页首版本漂移 |
| v2.3 | 2026-07-15 | Phase 1-T03：在获批文档计划范围内创建并登记 S3 限时练习 PRD |
| v2.2 | 2026-07-15 | Phase 1-T00：登记 12-开发规范，修正 Phase 0.8 完成态、S3 触发态和 Phase 1 阅读/门禁顺序 |
| v2.1 | 2026-07-13 | 补充前端规范的分页、轮询退避、资料笔记导航与格式化治理规则 |
| v2.0 | 2026-07-13 | T08 首个正式前端页面任务触发，登记前端开发规范 |
| v1.9 | 2026-07-13 | 对齐 T06 后系统文档：修正报告渠道环境变量状态，明确 QQ SMTP/飞书变量已登记并在 Phase 0.7 验证，正式消费留到 S6 ParentReport |
| v1.8 | 2026-07-13 | T06 审查收尾：修复任务状态更新对非法 `occurredAt` 静默回退为当前时间的问题，新增回归测试；全量测试更新为 94/94 通过 |
| v1.7 | 2026-07-13 | 回填 Phase 0.8 T06：S1 学习节奏核心 API 实现完成，包括学期 migration v2、课程/考试/任务/事件/时间线 8 个端点、标准 API 信封与 93/93 全量测试通过 |
| v1.6 | 2026-07-12 | 回填 Phase 0.8 T05：主仓库已正式接入 AI Provider Router、Dev API 与脱敏日志；同步登记 77/77 全量测试及后端测试稳定性治理 |
| v1.5 | 2026-07-11 | 触发文档门禁：创建 10-后端开发规范，登记为有效文档 |
| v1.4 | 2026-07-10 | 吸收参考系统的产品闭环：将 Exam、KnowledgeModule、练习记录与错题回流纳入有效设计和后续任务边界 |
| v1.3 | 2026-07-10 | 产品默认形态改为孩子 Windows 本机 + 邮件/飞书异步家长报告；以 Phase 0.7 替代隧道验证 |
| v1.2 | 2026-07-09 | Phase 0.5 完成交割后，统一任务清单、底座架构、测试计划和组件路线图状态 |
| v1.1 | 2026-07-09 | Phase 0.5A MVP 底座完成后，更新共同底座、组件状态、AI Provider 与 OCR 主路径 |
| v1.0 | 2026-07-07 | 初始版本，文档重建后的第一版索引 |

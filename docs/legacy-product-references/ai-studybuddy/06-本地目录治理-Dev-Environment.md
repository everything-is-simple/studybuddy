# AI StudyBuddy 本地目录与验证资产治理

**版本**：v1.9
**状态**：已确认
**日期**：2026-07-25
**用途**：定义主系统、外部组件试炼场、运行数据、日志、临时文件和备份的唯一边界。本文件是 Windows 单机目录治理的单一事实来源（SoT）。

---

## 一、总原则

产品默认运行在孩子的 Windows 11 电脑：Express 仅监听 `127.0.0.1`，SQLite 和学习资料保存在本机，OCR/AI/报告按需运行；父母只通过 QQ 邮件和飞书接收脱敏摘要。Docker/WSL2、家用主机、隧道、公网入口与家长远程登录均不属于当前单机成品。

目录必须按职责隔离：**源码不存真实数据，试炼场不变成主系统，运行数据不进入 Git，备份不反向污染当前 SoT。**

## 二、当前开发机目录边界（H 盘）

当前开发机已迁到 H 盘治理；旧文档中的 `I:\...` 只保留为历史路径语义，不再作为本轮重启的默认值。各目录按职责拆开，目的是让源码、正式/半正式数据、日志、可再生临时产物、worktree、备份和人工学习区互不污染。

| 路径                         | 唯一职责                     | 可以放                                                          | 禁止放                                                                                                     |
| ---------------------------- | ---------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `H:\ai-studybuddy`           | 主系统 Git 仓库              | `docs/`、`packages/`、`scripts/`、`.plans/`、正式测试和产品代码 | 真实学习资料、正式 SQLite、长期日志、模型缓存、密钥明文、部署运行数据、任何 `.worktrees` 根或任务 worktree |
| `H:\ai-studybuddy-worktrees` | **唯一**任务 worktree 根目录 | 从最新 `master` 派生的任务分支、隔离实现                        | 主系统目录内 worktree、正式运行数据、密钥、模型缓存                                                        |
| `H:\ai-studybuddy-composer`  | 外部组件/能力试炼场          | 最小样例、非隐私 fixtures、能力卡、局部依赖、测试日志           | 正式产品代码直接引用、真实学习资料、主仓库 workspace 配置                                                  |
| `H:\ai-studybuddy-data`      | 开发机人工指定的数据根候选   | SQLite、`materials/`、受控导出/备份                             | 源码、Git 元数据、密钥明文；E2E 不得复用                                                                   |
| `H:\ai-studybuddy-day-study` | 人工学习工作区               | 用户自己创建或整理的资料副本                                    | 系统唯一数据源、应用数据库、自动迁移目标                                                                   |
| `H:\ai-studybuddy-logs`      | 脱敏日志汇总                 | 运行摘要、错误摘要、任务状态                                    | API Key、SMTP 授权码、完整 Webhook、资料原文、完整答案                                                     |
| `H:\ai-studybuddy-tmp`       | 可再生临时/验证空间          | OCR 切片、E2E `runs/<task-id>`、部署包 smoke、Playwright 证据   | SQLite 正式库、唯一备份、真实资料主副本                                                                    |
| `H:\ai-studybuddy-backup`    | 只读阶段备份                 | 源码阶段 ZIP、旧稿归档、恢复说明                                | 当前 SoT 文档的直接编辑副本、密钥明文                                                                      |

**路径解释规则**：本节的 `H:\ai-studybuddy*` 是**当前开发机**的目录治理事实，不是普通用户电脑必须存在的安装路径。跨机器文档应优先使用逻辑名称（`<repo-root>`、`<external-component-root>`、`<run-evidence-root>`、`<app-data-root>`）；正式使用机器的数据根采用 `%LOCALAPPDATA%\AIStudyBuddy`。旧记录中的 `I:\...` 仅为历史证据路径，不应被改写成当前安装承诺。

**主系统清洁硬规则**：`H:\ai-studybuddy` 是主系统仓库，不得再创建、恢复、复制或移动任何 `H:\ai-studybuddy\.worktrees\*`。已存在的历史目录不因此自动删除；必须先完成归属审计，再按用户批准的精确清单使用 Git worktree 管理命令迁出登记 worktree，或安全处置无效残留。

非正式目录说明：`H:\ai-studybuddy-t09-validation` 是历史/专项验证产物区，不是本轮要建立的正式系统目录；`H:\.pnpm-store` 是 pnpm 内容寻址缓存，不是 AI StudyBuddy 运行目录，不能作为部署包内容或验收数据源。

本轮开发机重启使用仓库外隔离运行根，例如：

```text
H:\ai-studybuddy-runtime\
├─ runs\local-dev-20260723-001\
├─ logs\
├─ tmp\
└─ backups\
```

`.env.local` 只允许在本机未提交状态写入 `APP_DATA_ROOT`、`PYTHON_PATH` 等机器路径；业务代码、部署包、文档示例不得把 `D:\miniconda\py310` 或 `H:\...` 写成使用机器依赖。

正式使用机器固定采用当前 Windows 用户目录：

```text
%LOCALAPPDATA%\AIStudyBuddy\
├─ app\
├─ config\
├─ data\
├─ logs\
├─ tmp\
├─ models\
├─ backups\
└─ runtime\venv\
```

生产形态只监听 `127.0.0.1`；Docker/WSL 只用于开发隔离、ASR/G2 验证或未来可选实验，不是使用机器常驻产品依赖。E2E/Playwright 必须使用 `H:\ai-studybuddy-tmp\runs\<task-id>` 这类可再生隔离目录，不得复用 `%LOCALAPPDATA%\AIStudyBuddy\data` 或开发机正式数据根。

## 三、外部组件试炼场

`H:\ai-studybuddy-composer\windows-native` 是 Phase 0.7 的独立 Node/Python 验证目录，使用自己的 `package.json`、`.venv` 和 `.env.local`，不加入 `H:\ai-studybuddy\pnpm-workspace.yaml`。

每个组件样例至少包含：

```text
smoke-test/       可重复执行脚本
output/           可再生结果，必须忽略
COMPONENT-CARD.md 版本、命令、输入输出、耗时、内存、失败边界
```

严格禁止：

- 主系统 `packages/` import、执行或直接复制试炼场样例；
- 把 `.env.local`、`.venv/`、`node_modules/`、真实凭据、真实学习资料或 output 放回主仓库；
- 用“试炼场曾经跑过”替代产品代码的正式测试。

唯一接入路径：`试炼场 smoke test → 能力卡 → 04 任务状态 → 09 验收结果 → 08 Adapter 边界 → Phase 0.8 在 packages 重新实现`。

## 四、运行数据结构与清理

```text
APP_DATA_ROOT\
  studybuddy.db
  config\
    ai.active.enc / ai.prev.enc
    smtp.active.enc / smtp.prev.enc
    feishu.active.enc / feishu.prev.enc
    state.json
  semesters\<semester-id>\
    semester.db
    files\<course-id>\<generated-name>
    tmp\
    parent-reports\
  tmp\
  backups\
```

- 数据表只保存逻辑 `storage_key`，不保存绝对文件路径。
- SQLite 关闭后才能复制到 `data\backups`；恢复前保留原库的只读副本。
- `tmp` 和 `H:\ai-studybuddy-tmp` 可以清理，但清理脚本必须拒绝跨目录删除，且绝不删除 `materials`、`data` 或备份。
- 邮件附件和导出放在 `exports`；发送记录由 SQLite 的 `report_deliveries` 去重。
- `config/*.enc` 只能由创建它的 Windows 当前用户解密；`state.json` 只存状态和验证时间，不存密钥、完整 URL 或邮箱授权码。
- 测试和浏览器验收必须把 `APP_DATA_ROOT` 指向 `H:\ai-studybuddy-tmp\runs\<task-id>` 等隔离目录，不得读写正式运行目录。

## 五、密钥、日志与备份

`.env.example` 仅列变量名；`.env.local` 永不提交。日志不得记录 `AI_API_KEY`、`SMTP_AUTH_CODE`、完整 `FEISHU_WEBHOOK_URL`、资料原文、笔记正文、答案或聊天内容。

每个里程碑完成后：先对 `H:\ai-studybuddy` 做 Git 提交，再把源码与文档的阶段快照放到 `H:\ai-studybuddy-backup`；真实学习数据由家长确认后单独备份。备份只用于恢复，不得直接恢复为 `docs/` 的当前设计依据。

## 六、Phase 0.8 接入门槛

Phase 0.7 只验证，不修改主系统。SQLite、本地文件、SQLite Job Worker、RapidOCR、报告 Adapter 只有在能力卡、`docs/09-*` 实测结果、`docs/08-*` 边界和文档治理检查都齐全后，才可以在 Phase 0.8 重新实现。HP 实机兼容复测（Node 22 LTS、16GB）在设备可用后执行，不阻塞 Phase 0.8。

## 七、worktree 脏状态与生成物治理

`git status` 显示的内容必须先按性质处理，而不是统一称为“垃圾”：

1. **语义改动**（业务代码、迁移版本、脚本行为或有效文档事实）必须保留现场，在最新主线派生的干净 worktree 中比较、测试和取得专门批准；不得为了变干净而覆盖。
2. **未跟踪计划**属于待审的决策资产。计划是否提交、迁移、保留或归档必须在 `docs/04` 有明确状态，计划存在不等于功能已经实施。
3. **可再生生成物**（编译 `.js/.map/.d.ts`、测试输出等）和**依赖残留**（例如某个 worktree 内的 `node_modules`）只有在精确绝对路径白名单、父目录核验、无占用进程和用户批准都满足后，才可处理。
4. **仓库外组件试炼场、运行数据和证据目录**不属于主仓 Git 脏状态，不得因为主仓清理而移动、复制或删除。

禁止使用 `git clean`、`git reset --hard`、覆盖 checkout 或面向仓库根的通配符递归删除来处理脏状态。当前收口批次、风险分级和批准门以 `.plans/process-dirty-state-remediation-plan.md` 与 `docs/04` 的 `PROCESS-DIRTY-20260725` 为准。即使个别 worktree 尚未收口，也不改变 `origin/master` 的产品事实，更不改变用户电脑验收、S7 产品接入或外部候选能力的状态。

## S7-MVP 临时音频目录边界（2026-07-25）

S7-MVP 的上传 WAV 不是长期资料文件：仅可在由 `APP_DATA_ROOT` 派生的 `tmp/class-capture/<request-id>/` 内短暂存在，服务端在成功、失败、超时和取消路径都删除。真实课堂录音、模型、CLI、DLL、harness、转写全文和运行日志不进入主仓库；外置候选继续留在 `H:\ai-studybuddy-components`，但业务代码只能使用环境变量，不能硬编码本机盘符。此规则不等于用户电脑验收完成。

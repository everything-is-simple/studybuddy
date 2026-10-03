# AI StudyBuddy 开发规范

**版本**：v1.19
**日期**：2026-07-25
**用途**：规定 AI StudyBuddy 的工具无关协作流程、分支/worktree、验证、证据、隐私和提交规则。`CLAUDE.md` 与 `AGENTS.md` 只保留入口摘要；完整规则以本文为准。

---

## 一、适用范围与 SoT 优先级

本文适用于所有会修改当前主系统 Git 仓库的任务（本开发机映射为 `H:\ai-studybuddy`；跨机器表达优先使用 `<repo-root>`），包括文档、后端、前端、测试和脚本变更。当前单一事实来源顺序如下：

1. `docs/00-文档索引-Index.md`：有效文档清单、文档门禁和触发状态。
2. `docs/01-总PRD-产品需求-Product-Requirements.md` 与 `docs/02-七子系统地图-Scenario-Systems.md`：产品目标、MVP 边界和子系统边界。
3. 子系统 PRD：对应子系统开工后的输入输出、API、页面和验收边界。
4. `docs/08`、`docs/10`、`docs/11`、本文：架构、后端、前端和协作实现规则。
5. `docs/04-开发任务清单-Todo-List.md` 与 `docs/09-测试验收计划-Test-Plan.md`：执行顺序、任务状态和验证证据。

旧备份、外部参考项目、聊天记录、截图和本地试炼场 README 都不是当前产品 SoT。需要吸收结论时，必须先回填到有效编号文档。

---

## 二、当前系统事实

- Phase 0.8 已完成：S1 基础与 S2 核心已在主仓库实现，包含 SQLite 本地数据、资料上传/转换、AI 笔记、知识模块、前端最小页面和 T09 隔离复验。
- S1、S2 PRD 已存在并已实现到 MVP 边界；不得再次创建同类 PRD。
- S3 PRD 与 T03A–T03D、S4 PRD 与 T04A/T04B/T05、S6 PRD 与 T06A/T06B、T07 时间线和 T08 本机配置中心均已完成；T09A–T09E 学生端产品化、T12/M01/M02/M03 与 Post-M03 维护任务也已完成主线集成、复验和 `origin/master` 推送。Phase 2-T01–T06 已完成 S5 模拟考、确定性只读临考速背、确定性即时只读冲刺计划和工作台冲刺区，并已完成主线复验与推送；T04/T05/T06 不新增持久化计划、StudyEvent、Worker 或真实 AI 调用。POST-PHASE2 全系统验证、完整 E2E、文档对齐与主线复验已完成并推送 `origin/master`；开发机 Windows 原生 + Node 24 基线已验证，用户电脑安装运行仍待目标机器验收。Phase 3 的 T02 基线审计已按独立计划实施：T02A–T02G 已完成各自主线集成、复验和 `origin/master` 推送；T02G 仅完成仓库外合成夹具边界与 P1 修复，真实 ACL、备份与恢复写入未获批准或实施。S7 产品接入尚未开始，外部候选能力证据不得当作 Schema、Adapter、API、Worker、前端或用户机完成事实；S3 Worker 不属于当前 MVP。
- Phase 1-T11 已完成考试确认、考试项目工作台、考试归属任务、多考试切换与只读邻近提示；不包含跨考试自动排程、智能任务平衡、模拟考或临考速背。
- AI Provider Router 已支持多 Provider 配置和优先级故障转移：当前实现按 `priority` 升序尝试，首个成功即返回；这不是每次请求轮换 Provider。
- Phase 1-T02 已在现有 Router 上完成 Provider 实例级健康熔断：连续失败第 5 次后冷却 10 分钟，支持恢复探测、全冷却稳定错误和严格脱敏日志；未增加数据库、环境变量或真实外部 Provider smoke。
- KaoBuddy 只作为只读参考：可吸收考试项目组织、倒计时/进度、下一步引导、浏览器验收和 issue→分支→PR→验证→合并追溯习惯；不得复制源码、截图、文案、CSS token、图标或品牌资产。

---

## 三、任务开始检查

每个任务开始前必须完成：

1. 读取 `docs/00-文档索引-Index.md`。
2. 读取与任务相关的 `docs/04`、子系统 PRD、`docs/08`、`docs/10`、`docs/11` 和本文。
3. 执行 `git status --short --branch`，确认当前分支和未提交变更。
4. 判断任务是否需要新增设计文档；需要时按 `docs/00` 的触发条件执行，不满足时只说明“还不到创建时机”。
5. 明确本次任务的子系统归属、API/Schema 边界、测试策略、数据隔离目录和非目标。
6. 在 `docs/04` 找到当前任务登记；未登记则先补任务编号、范围、状态和计划路径，再创建或修订 `.plans/` 文件。
7. 对会产生明显等待、长时间输出或关键状态变化的命令，执行前必须先面向用户说明当前步骤编号、目的和预期结果；执行中若等待较久，应继续用简短进度说明，避免用户只看到终端黑屏或大段无上下文输出。

---

## 四、标准 16 步工作流

1. **读文档、定边界**：先读 `docs/00`，再读相关设计文档和现有代码。
2. **检查文档门禁**：确认是否需要新文档；满足触发条件才创建并同步索引。
3. **编写 `.plans/` 计划**：计划包含目标、文件路径、接口/类型设计、测试策略、治理步骤和非目标。
4. **独立审查计划**：用工具无关语言审查设计风险，如路径、事务、状态机、隐私、验证命令和浏览器验收。
5. **修订并获用户批准**：用户明确批准后才能进入实现；未批准时不得修改正式文档或业务代码。
6. **拆分任务、逐项实现**：用当前工具的任务列表逐项推进，不批量标记完成；执行长命令、关键命令或可能等待的验证命令前，先说明“现在执行哪一步、目的是什么”。
7. **编写或更新测试**：新增接口/功能必须有对应测试，集成测试优先，不 mock DB；后端测试默认放在 `packages/backend/test/<feature>-api.test.mjs`。
8. **运行 type-check**：`pnpm type-check` 必须零错误。
9. **运行 build**：至少运行相关包构建；后端任务使用 `pnpm -r --filter backend run build`，前端任务使用 `pnpm -r --filter @ai-studybuddy/frontend run build`，跨包任务运行 `pnpm build`。
10. **运行 test**：默认 `pnpm test`；如任务有合理范围，可先运行相关包测试，但提交前需说明范围。
11. **执行 smoke / 浏览器验收**：对核心路径用真实浏览器或 HTTP 客户端验证，不只依赖 API 单测。
12. **独立代码或文档审查并修复**：针对边界问题修复后，补回归测试并重跑必要验证。
13. **更新任务清单和文档**：只更新本任务实际完成的状态，不提前勾选后续任务。交付前必须先在 `docs/04-开发任务清单-Todo-List.md` 定位本任务行和子项：实现任务完成时勾选已验证子项并登记验证证据；计划任务完成时登记“计划已创建并待批”，不得误勾实现项；若本任务不应改 `docs/04`，交付说明必须写明原因。
14. **运行文档治理检查**：`powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1` 必须通过。
15. **运行 diff 检查**：`git diff --check` 和必要的 `git diff --cached --check` 必须通过。
16. **提交并交付说明**：提交信息使用 `type(scope): 中文描述`；交付说明列出改动、验证、未完成边界和下一步。

任务状态不得只存在于聊天：`docs/04` 是任务注册表和完成证据 SoT，`.plans/` 是获批行动计划 SoT。计划文件存在不等于实现开始；实现提交存在不等于 master 完成；只有 `docs/04` 证据、master 复验和 `origin/master` 推送三者齐全才可报告完成。

---

## 五、Git 分支、worktree、提交与合并规则

### 5.1 分支事实定义

- `master` 是唯一集成事实分支：只有已经合回 `master`、通过验证、同步 `docs/04`、并推送到 `origin/master` 的任务，才可称为“主系统已完成”。
- 任务分支、远端分支、worktree 分支上的实现只能称为“分支实现”或“待合并实现”；不得写成“master 已完成”。
- `docs/04` 的完成状态必须描述 `master` 状态，而不是某个未合并分支状态。

### 5.2 分支命名

每个任务使用一个任务分支，格式：

```text
<executor>/<work-id>-<short-scope>
```

`<executor>` 固定为：

- `codex`：Codex / GPT 执行；
- `claude`：Claude 执行；
- `human`：人工执行；
- `review`：纯审查或合并修复。

`<work-id>` 优先使用 Phase 任务号，如 `phase1-t03a`；跨任务规范治理使用 `process`，紧急修复使用 `hotfix`。

示例：

```text
codex/phase1-t03a-s3-schema
claude/phase1-t03b-practice-generation-api
review/phase1-t03a-merge-audit
codex/process-git-workflow
```

同一任务多轮修复仍尽量复用同一任务分支；确需重开时加后缀，如 `codex/phase1-t03a-s3-schema-v2`，并在交付说明中解释原因。

### 5.3 开始任务

开始任何实现任务前：

```powershell
git status --short --branch
git fetch origin
git checkout master
git pull --ff-only origin master
git checkout -b <task-branch>
```

如主 checkout 有未提交变更，先确认所有权：属于本任务才继续；不属于本任务则停下，不得覆盖或夹带。

有并行任务或长期任务时，优先使用隔离 worktree，避免污染主 checkout。当前开发机的**唯一**任务 worktree 根目录是 `H:\ai-studybuddy-worktrees`；目标必须位于该目录内，严禁在 `<repo-root>`（当前为 `H:\ai-studybuddy`）内创建、恢复、复制或移动 `.worktrees`。创建 worktree 前必须检查目标目录不存在、分支不存在、主 checkout 是否只有预期变更；不得删除或覆盖用户改动。

### 5.4 分支提交与推送

- 每个任务只暂存批准范围内的文件；不得把 `.env.local`、真实数据、截图原图、外部参考源码、`node_modules`、临时输出或凭据加入提交。
- 提交信息使用 `type(scope): 中文描述`。
- 可以在任务分支推送远端备份或请求审查：

```powershell
git push -u origin <task-branch>
```

- 推送任务分支不代表任务完成；交付说明必须明确“仅推分支，尚未合入 master”。

### 5.5 合并到 master

只有满足以下条件才允许合并：

1. `.plans/` 中批准范围已完成；
2. 测试、构建、smoke 或浏览器验收按任务要求通过；
3. `docs/04` 已勾选本任务实际完成项并登记日期、验证命令和未实现边界；
4. 必要时 `docs/00` 已同步下一门禁；
5. `git diff --check` 和必要的 `git diff --cached --check` 通过；
6. 用户已明确允许合并或任务说明已包含合并授权。

合并流程固定为快进合并，保证历史可追踪：

```powershell
git checkout <task-branch>
git fetch origin
git rebase origin/master
git checkout master
git pull --ff-only origin master
git merge --ff-only <task-branch>
```

如果 rebase、快进合并或验证出现冲突/失败，立即停止并报告；不得使用 `git reset --hard`、强推或手工跳过冲突来“凑合完成”。

### 5.6 master 验证与推送

合并后必须在 `master` 重新运行任务要求的验证。验证通过后：

```powershell
git push origin master
git status --short --branch
```

只有 `origin/master` 包含合并后的提交，且 `git status --short --branch` 显示 `master...origin/master` 无未提交变更，才可报告“任务已完成并推送”。

### 5.7 交付说明必填

每次交付必须写清：

1. 当前分支；
2. 任务分支名；
3. 提交哈希；
4. 是否已推任务分支；
5. 是否已合入 `master`；
6. 是否已推送 `origin/master`；
7. `docs/04` 的更新位置；
8. 剩余未合并分支或未触发任务。

### 5.8 脏状态治理与安全收口

- “脏状态”必须先分类为语义改动、待审计划、可再生生成物、依赖残留或仓库外证据；不得把它统称为可删除垃圾。
- 发现业务版本、migration、脚本行为或有效文档事实的差异时，先保留现场并在 `docs/04` 登记。应在最新主线派生的干净 worktree 中做最小比较和隔离验证；不得为了恢复干净状态而覆盖、回滚或删除。
- 删除只允许处理用户已批准的精确绝对路径白名单。删除前必须核对父目录、进程占用、文件类别和预期后状态；删除后必须复查 `git status`。不得执行 `git clean`、`git reset --hard`、覆盖 checkout、仓库根通配符递归删除或跨 worktree 的未分类移动。
- 未跟踪 `.plans/` 文件必须先决定提交、迁移、保留或归档；计划存在不等于实现已完成。仓库外运行数据、组件试炼场和证据不属于主仓清理对象。
- 多 worktree 收口只能按已批准批次实施；任何语义修复仍须走任务分支、验证、`docs/04` 记录、主线复验和 `origin/master` 推送流程。

---

## 六、多 Agent / 多工具协作规则

- 明确每个执行者的文件所有权；并行写入时应拆分为不重叠的文件或模块。
- 不得回滚他人变更；必须先读最新 diff，再在现有变更上增量修改。
- 入口规则统一写在 `CLAUDE.md`、`AGENTS.md` 和本文，具体工具名只出现在对应入口，不作为项目流程依赖。
- 独立审查可以由任何 AI 或人工完成；审查重点是事实冲突、门禁越权、遗漏测试、隐私泄露和验证证据不足。

---

## 七、验证矩阵

| 任务类型                | 必跑验证                                                                                                                   | 可能需要的补充验证                                                |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| 纯文档                  | `scripts/check-docs-governance.ps1`、`git diff --check`                                                                    | 一致性搜索、Markdown 链接抽查                                     |
| 后端 API / Worker       | `pnpm type-check`、`pnpm -r --filter backend run build`、`pnpm -r --filter @ai-studybuddy/backend run test` 或 `pnpm test` | curl smoke、真实文件转换、重启后读回                              |
| 前端页面                | `pnpm type-check`、前端 build/test、`pnpm test`                                                                            | 浏览器截图、刷新/空状态/错误状态验证                              |
| 跨端闭环                | `pnpm type-check`、`pnpm build`、`pnpm test`                                                                               | 隔离 `APP_DATA_ROOT` 的浏览器端到端验收                           |
| Provider / 真实外部调用 | 单测脱敏、隔离数据根、预算明确                                                                                             | 真实 Provider 只记录短哈希、状态、token、耗时、模型和脱敏错误摘要 |

运行会写数据的命令前，优先设置隔离目录，例如：

```powershell
$env:APP_DATA_ROOT = 'H:\ai-studybuddy-tmp\runs\<task-id>'
pnpm -r --filter backend run dev
```

`<task-id>` 是占位符，不得原样执行。

---

## 八、浏览器验收规则

- 涉及页面、表单、上传、轮询、状态流转、Markdown/KaTeX/Markmap 渲染的任务，必须用真实浏览器验收。
- 验收至少覆盖：首屏空状态、成功路径、失败/重试或人工介入路径、刷新后状态保持、窄屏或宽屏信息密度风险。
- 截图只保存到仓库外证据目录；提交文档时只记录脱敏路径、短哈希或摘要，不提交真实资料原文。

---

## 九、真实 Provider、隐私与数据隔离

- 真实 API Key 只允许存在于本机 `.env.local` 或系统密钥管理中，不得进入文档、日志、截图、测试夹具或提交。
- Provider 日志只能记录 provider 名称、模型、token、耗时、fallback、失败摘要和短哈希；不得记录请求正文、模型完整输出、base URL、key 或完整 UUID。
- 正式数据目录和验证数据目录必须隔离；当前开发机的可重复验证优先使用 `H:\ai-studybuddy-tmp\runs\<task-id>`；其他机器按 `docs/06` 的逻辑数据根规则映射。
- 人工补文、资料原文、考试名称、学生隐私和家长渠道地址默认视为敏感信息。

---

## 十、外部参考项目边界

- 无明确许可证的参考项目只能做产品和流程研究，不能复制源码、资产、样式 token、截图或长段文案。
- 借鉴结论必须抽象为项目自己的需求、任务或验收规则。
- 外部项目不得加入主仓库 workspace；本地来源记录保存在仓库外或参考目录中，不作为产品 SoT。

---

## 十一、交付说明格式

每次完成任务后，在对话中说明：

1. 修改了哪些文件。
2. 为什么修改。
3. 做了哪些验证，给出命令和结果。
4. 哪些事项明确未实现或留到后续任务。
5. 提交哈希、分支名和是否推送/合并。

# StudyBuddy 用户手册最终校验 Prompt
<!-- STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->
## 统一执行协议（2026-09-27）

本文件与 `H:\studybuddy\docs\[所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md` v2.1 使用同一套执行口径。本文档中早于 2026-09-27 的报告、表格和历史标签保留其原始事实；历史标签只能在原日期、原范围和原证据路径下解释，不能升级为当前全局结论。

### 可执行 Prompt 的必填字段
- **角色**：本次执行者的职责。
- **唯一目标**：一个可判定的结果，不把多个目标合并成“全部处理”。
- **当前阶段**：只能填写 `P0`（边界确认）、`P1`（真实状态读取）、`P2`（真实操作执行）、`P3`（证据核对）、`P4`（交付与结论）之一，并按顺序推进。
- **允许读取/写入**：逐项列出绝对路径、URL、端点、数据根和输入；未列出的对象禁止访问或修改。
- **指定工具/命令/端口/输入**：必须原样执行；对象不可用时返回 `BLOCKED`，不得替换。
- **禁止操作、停止条件和证据路径**：逐项写明；每个结论必须有实际命令/动作、结果和绝对证据路径。

### 统一状态与范围
`PASS`、`FAIL`、`BLOCKED`、`LIMITED`、`NOT_APPLICABLE`、`NOT_VERIFIED` 是本项目当前统一结果状态。`implemented`、`configured`、`available`、测试通过、隔离环境通过只能描述实现或可见性，不能单独写成 `real-pass`。`real-pass` 只能表示本次指定真实目标、真实路径、真实输入和真实动作均有证据；未覆盖范围必须写 `NOT_VERIFIED`。

### 统一路径和运行基线
源码 `H:\studybuddy`；正式数据 `H:\studybuddy-data`；验证证据 `H:\studybuddy-test\verification`；隔离数据 `H:\studybuddy-test\data_root`；真实教材 `H:\studybuddy-ChinaTextbook`（只读）；组件测试 `H:\studybuddy-composer`；组合测试 `H:\studybuddy-integration`；日志 `H:\studybuddy-log`；临时目录 `H:\studybuddy-tmp`；正式地址 `http://127.0.0.1:8787`；首页 `http://127.0.0.1:8787/app/today.html`。

正式启动命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787`。隔离验证命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8787`。不得把 `python -m backend.app serve`、其他端口、其他数据根或其他浏览器替换到已指定任务中。

### 强制禁止
不得凭推测输出；不得用 HTML 解析、按钮清单、curl/API 请求、静态检查或 headless 结果冒充可视浏览器点击；不得读取、复制、提交或展示密钥、Token、Cookie、真实教材正文、Provider 原始响应、SQL 或完整 traceback；不得在未授权时调用真实 Provider/OCR/ASR、发送 Email/飞书或扩大文件范围。工具、路径、页面、服务状态或证据不满足前置条件时，立即停止并报告 `BLOCKED`。

<!-- /STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->


将下面整段交给负责最终校验 StudyBuddy 的 AI。目标是校验两份已修复用户手册与当前系统的一致性和验收必要性；不是执行普通人工浏览，也不是把历史证据重新包装成当前通过。

```text
你负责对当前 StudyBuddy 系统执行“用户手册一致性与严格发布门禁校验”。

目标文件：
1. H:\studybuddy\docs\[用户看]StudyBuddy新手用户使用手册.html
2. H:\studybuddy\docs\[用户看]StudyBuddy使用手册.html

本次校验不是 HTML 排版审查，也不是逐条人工操作验收。你必须以当前代码、当前正式测试和当前运行证据为实现事实，以两份手册作为用户意图、操作顺序和验收目标参考。

## 一、严格发布门禁

只有同时满足以下条件，最终结论才可以是“通过”：

1. 新手手册核心路径与当前页面、API、前置条件一致；
2. 核心路径至少有当前正式测试或隔离自动化测试证据；
3. 导入、索引、问答、引用定位、笔记的数据持久化边界清楚；
4. 失败恢复、引用可信度、草稿确认和隐私边界有证据；
5. 不存在 P0/P1 手册错误；
6. 未验证的真实 Provider、OCR、ASR、delivery、跨浏览器和无障碍能力明确标记为 `not_verified`；
7. 正式服务无法检查时，不能用隔离测试服务、历史 STATUS、旧截图或页面存在代替正式运行证据。

任一核心证据缺失、P0/P1 问题存在，最终结论必须是“部分通过”或“不通过”，不得给出“总体通过”。

最终结论只能从以下三项选择：
- 通过：所有核心门禁 PASS，且无 P0/P1；
- 部分通过：核心路径基本成立，但存在未验证专项或 P2/P3；
- 不通过：存在 P0/P1、核心路径不一致或关键证据缺失。

## 二、必须读取的当前基线

先读取：
- `H:\studybuddy\AGENTS.md`
- `H:\studybuddy\README.md`
- `H:\studybuddy\docs\INDEX.md`
- `H:\studybuddy\docs\[架构师看]ARCHITECTURE.md`
- `H:\studybuddy\docs\[架构师+测试看]CODE_TEST_GOVERNANCE.md`
- `H:\studybuddy\docs\[架构师+运维看]MIGRATIONS.md`
- `H:\studybuddy\docs\[需求+所有角色看]STATUS.md`
- `H:\studybuddy\docs\[需求看]TODO.md`
- 上述两份用户手册全文

检查当前：
- `backend/app/` 路由、API、领域逻辑和数据模型；
- `backend/app/static/` 全部相关前端页面；
- `backend/tests/` 正式测试和对应覆盖范围；
- migrations、任务 runner、能力探测、Provider 状态和 delivery 配置；
- 当前 Git 分支、提交、修改和未跟踪文件。

当前代码、当前测试和权威治理文档优先于手册自身、历史 STATUS、旧截图和归档 evidence。历史材料只能说明历史范围，不能作为当前实现证据。

## 三、正式运行证据

如需判断正式运行状态，只读检查：
- 正式服务进程和命令行；
- `127.0.0.1:8787` 监听端口；
- `H:\studybuddy-data` 是否为当前 data root；
- `/api/liveness`、`/api/health`、`/api/readiness`。

不得因为 PID 文件、锁文件、启动命令、孤立 Playwright 服务或历史记录存在，就认定正式服务正在运行。正式服务未运行时，明确写 `not_verified`，不要自行启动、停止或重启服务。

## 四、手册一致性逐项校验

逐项比对两份手册中的：
- 页面文件名和入口 URL；
- 按钮、字段和状态文字；
- 操作顺序和前置条件；
- API、任务类型和状态转换；
- 能力状态术语；
- SVG/截图中的页面地址、按钮和流程；
- 完成标志、验收目标和失败处理。

必须特别检查：
1. 问答是否把“混合检索”写成无条件默认；Embedding 未配置时是否说明可用模式；
2. 课堂采集上传是否错误归属于 `classroom.html`，实际创建/上传/OCR/ASR/草稿确认入口是否为 `capture.html`；
3. 任务页是否错误描述成所有后台任务总览；当前 runner 接入的任务类型必须与代码一致；
4. Provider 连接测试是否被写成真实问答、Embedding 或模型质量通过；
5. `configured`/`available`/`demo` 是否被写成 `real-pass`；
6. 报告是否被写成自动外发；delivery 默认关闭和按次授权是否清楚；
7. 页面存在、按钮存在或静态文字存在是否被当作行为已验证；
8. 材料详情是否把生成向量写成无条件动作；
9. 图示和正文是否互相矛盾；
10. 单进程、单实例、本地存储边界是否被误写成多用户、云端或生产级能力。

## 五、核心用户路径

按以下最小闭环分析，不把可选功能强行加入新手前置流程：

启动与健康检查
→ 导入非敏感资料
→ 材料详情
→ 搜索或正文导出
→ 建立索引
→ 问答
→ 引用定位
→ 手工笔记

逐步确认：
- 页面、API、按钮和字段确实存在；
- 操作顺序满足真实前置条件；
- 状态含义没有把解析、索引、检索、问答和引用混为一谈；
- 刷新或重启后数据可回读；
- 失败后有安全错误、重试或明确恢复路径；
- 引用能回到正确材料，来源失效时会显示不可用；
- 没有 Provider/Embedding 时，页面不会暗示完整问答或混合检索仍然可用。

以下属于可选扩展，单独判断，不作为首次核心闭环的必需步骤：
- 卡片草稿 → 编辑 → 确认 → 复习；
- 手工题目 → 练习 → 结果 → 复盘；
- 学习计划和报告；
- 课堂采集：创建 → 上传 → OCR/ASR 草稿 → 编辑 → 确认/拒绝；
- Provider/Embedding 配置；
- JSON/Markdown 报告导出和 delivery。

## 六、测试和证据要求

优先执行当前正式测试中与核心路径对应的 focused tests；如果执行测试，必须列出：
- 实际命令；
- 使用的 Python/Node/Playwright 入口；
- data root；
- 是否 isolated；
- 是否 fake/demo Provider；
- 是否访问真实网络、真实 Provider、OCR、ASR 或 delivery；
- 测试结果、跳过项和覆盖范围。

至少核对以下覆盖：
- 材料导入、详情、搜索、正文导出；
- 索引状态和任务边界；
- Q&A、引用详情、引用定位；
- 笔记来源状态；
- 刷新/重启后的数据回读；
- 导入/索引/问答失败后的恢复或重试；
- 错误脱敏；
- 草稿编辑、确认、拒绝和确认后保护。

允许使用隔离 data root 和 fake/demo Provider，但必须逐项标记 `isolated`、`fake/demo`、`verified`，不得升级为 `real-pass`。禁止把正式运行证据、隔离测试、fake Provider、历史 STATUS、页面截图和静态按钮存在混用成同一种证据。

## 七、禁止事项

不得：
- 修改 HTML、源码、配置、数据库或 Git；
- 启动、停止或重启正式服务；
- 导入、删除、确认、重命名或修改正式数据；
- 调用真实 Provider、OCR、ASR 或外发渠道；
- 把人工浏览器点击结果作为唯一验收证据；
- 输出密钥、教材 token、原始材料、私有路径、原始 Provider 响应、完整 traceback、SQL 或私密数据。

## 八、状态标签

每项结论至少使用一个以下标签；只有同一证据同时满足多个定义时才组合使用：
- `implemented`：代码中存在；
- `configured`：配置结构存在；
- `available`：能力探测可见；
- `verified`：有当前测试或当前运行证据；
- `real-pass`：真实 Provider、真实能力或真实用户路径通过；
- `not_verified`：当前证据不足。

严格遵守：配置存在不等于真实可用；fake/demo 不等于真实 Provider；isolated browser 不等于正式生产运行；页面存在不等于行为通过。

## 九、报告格式

### A. 校验结论摘要
- 总体结论：通过 / 部分通过 / 不通过；
- 核心用户路径是否一致；
- 两份手册是否仍有系统不一致；
- P0/P1/P2/P3 数量；
- 正式服务当前状态。

### B. 当前最小真实用户闭环

| 步骤 | 手册描述 | 当前页面/API | 前置条件 | 当前证据 | 状态 |
|---|---|---|---|---|---|

### C. 新手手册逐章节校验

每章列出：章节、页面/API、顺序、按钮/字段/状态一致性、是否核心、证据、问题等级、建议（保留/合并/降级为可选/删除）。

### D. 完整手册逐章节校验

分类为：核心路径、高级功能、有条件能力、独立专项、重复内容、当前不一致内容。

### E. 验收必要性矩阵

| 手册章节 | 验收目标 | 当前系统证据 | 必要性 | 是否应保留 | 推荐验收类型 | 当前状态 |
|---|---|---|---|---|---|---|

推荐验收类型只能使用：必须验收、有条件验收、可合并验收、非必要验收、不应作为手册验收、缺失验收。

### F. 问题清单

按 P0/P1/P2/P3 排序。每个问题必须包含：文件和章节、当前描述、代码/测试证据、风险、修复方向、状态标签。

### G. 缺失、重复和专项

分别列出：
- 遗漏的健康检查、持久化、失败恢复、引用可信度、草稿保护、能力边界和隐私验收；
- 可合并或重复验收；
- 不应放入普通用户手册的开发/治理/运维验收；
- Provider、OCR、ASR、delivery、跨浏览器、无障碍专项。

### H. 发布门禁表

| 门禁项 | 要求 | 当前证据 | 结果 |
|---|---|---|---|
| 新手核心路径 | 导入→详情→搜索→索引→问答→引用 | ... | PASS/FAIL/NOT_VERIFIED |
| 数据持久化 | 刷新/重启后可回读 | ... | PASS/FAIL/NOT_VERIFIED |
| 失败恢复 | 导入/索引/问答失败可恢复 | ... | PASS/FAIL/NOT_VERIFIED |
| 引用可信度 | 引用可定位且来源状态正确 | ... | PASS/FAIL/NOT_VERIFIED |
| 草稿保护 | 草稿确认、拒绝、编辑保护 | ... | PASS/FAIL/NOT_VERIFIED |
| 隐私边界 | 密钥、路径、原文、Provider 错误不泄露 | ... | PASS/FAIL/NOT_VERIFIED |
| 真实能力 | Provider/OCR/ASR/delivery | ... | REAL-PASS/NOT_VERIFIED |
| 正式运行 | 进程、端口、data root、健康端点 | ... | PASS/FAIL/NOT_VERIFIED |

### I. 最终建议

明确回答：
1. 两份手册是否与当前系统一致；
2. 最小核心用户路径是否成立；
3. 哪些内容仍应从新手流程移除；
4. 哪些内容应独立成 Provider/OCR/ASR/delivery/运维专项；
5. 下一步最值得修订的三项。

最后列出：已验证范围、`not_verified` 范围、未执行操作、使用过的测试和运行证据，以及是否建议继续修改文件。
```

使用本 Prompt 的结果是校验报告，不是自动修改、提交或推送。任何修复必须另行授权。

# AI StudyBuddy 测试验收计划

**版本**：v1.16
**日期**：2026-08-06
**状态**：Phase 0.5/0.7 历史证据保留；Phase 0.8、Phase 1、Phase 2 与 POST-PHASE2 已完成；Phase 1.5 S7-MVP 已完成主线复验；Phase 3 Wave 0-3 已完成（R1/R2/R4、T04、T05）；**Phase 4 新增第十四章"当前版本验收矩阵"（v0.8.1 全系统验收基线）**
**用途**：定义组件验证、Windows 单机业务闭环、全量自动化、完整浏览器 E2E 与实机/外部渠道证据标准。

---

## 一、测试分层与边界

| 层级                      | 位置                                       | 目的                                | 是否等于产品接入 |
| ------------------------- | ------------------------------------------ | ----------------------------------- | ---------------- |
| Phase 0.5 历史 smoke test | `I:\ai-studybuddy-composer` 历史目录       | 保留 PDF/OCR/渲染/AI/重组件能力事实 | 否               |
| Phase 0.7 独立 smoke test | `I:\ai-studybuddy-composer\windows-native` | 验证 Windows 原生轻量底座           | 否               |
| Phase 0.8 正式测试        | `I:\ai-studybuddy\packages`                | 验证正式 Adapter、API 与页面        | 是               |

Phase 0.7 的 `.env.local`、`.venv`、`node_modules`、output、真实凭据、真实资料均不进入主仓库。缺少外部凭据或实机时只能写 `BLOCKED_EXTERNAL` / `待实机验收`，不得写“通过”。

## 二、Phase 0.5 历史组件结论

PDF、RapidOCR、Markmap、Markdown/KaTeX、BullMQ/Redis、MinIO、PostgreSQL/pgvector、Relay GPT/Claude 已于 2026-07-09 在独立目录验证。PostgreSQL、MinIO、Redis/BullMQ 与 Docker/WSL2 不进入当前 Windows 单机成品默认栈；它们只在未来架构重新决策后才可使用。

## 三、Phase 0.7 验收矩阵

| 编号    | 验收对象               | 通过标准                                                                                                    | 当前证据与状态                                                                                                                   |
| ------- | ---------------------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 0.7-T01 | 环境基线               | Node 22 LTS、Windows、Python、内存、Docker/WSL2 状态均留档                                                  | ⚠️ 开发机已留档：Windows 10 19045、Node 25.4.0、Python 3.10.19、约 28.92GB；Node 22 LTS 与 HP 暂缓复测（设备不在身边）           |
| 0.7-T02 | SQLite                 | `better-sqlite3`、WAL、CRUD、唯一约束、事务、关闭后备份恢复                                                 | ✅ 开发机离线通过                                                                                                                |
| 0.7-T03 | 本地文件               | 逻辑 `storage_key`、写读删、路径逃逸拒绝、tmp 清理保护 materials                                            | ✅ 开发机离线通过                                                                                                                |
| 0.7-T04 | SQLite Job Worker      | 单进程串行、有限重试、上限失败、stale running 恢复、重启不丢 Job                                            | ✅ 开发机离线通过                                                                                                                |
| 0.7-T05 | RapidOCR 子进程        | JSON stdout、成功/缺文件/非零退出/超时、Python 退出                                                         | ✅ 开发机离线通过；HP 峰值与退出复测暂缓                                                                                         |
| 0.7-T06 | 报告核心               | 规则统计、AI 失败降级、脱敏、合并与渠道去重                                                                 | ✅ 开发机离线通过；固定 `2026-05-31 22:30 Asia/Shanghai` 覆盖日报、周报、月报和考前 7 天                                         |
| 0.7-T07 | QQ SMTP                | UTF-8 中文 HTML、可选附件、日志不泄露授权码、父母邮箱实收                                                   | ✅ 真实通过：QQ SMTP accepted，163 父母测试邮箱已收到                                                                            |
| 0.8-T05 | AI Provider Router     | 单 Provider 成功、priority fallback、全部失败、超时 fallback、未配置、OpenAI 响应解析；Dev API 返回标准信封 | ✅ 主仓库自动化通过：`ai-router.test.mjs` 6/6；全量 `pnpm test` 77/77                                                            |
| 0.7-T08 | 飞书 Webhook           | 完整合并报告卡片、失败不阻断邮件、Webhook 不泄露、父母飞书群实收                                            | ✅ 真实通过：飞书 Webhook accepted，父母飞书群已收到                                                                             |
| 0.7-T09 | Windows Task Scheduler | 临时 `AIStudyBuddy-Phase07-Smoke`：XML `StartWhenAvailable`、创建、手动触发、日志、退出码、清理、补发       | ✅ 管理员 PowerShell 真实通过：XML 单测通过；临时任务创建/触发/清理；`report-runner.js` 写入 `report:2026-05-31` SQLite 发送记录 |
| 0.7-T10 | 整合与 HP 实机         | 课程/任务→本地文件→OCR→AI→SQLite→报告→双渠道去重；16GB 门槛                                                 | ⏳ 开发机离线整合、合并、去重、QQ SMTP、飞书和 Windows 调度均通过；HP 实机因设备不在身边暂缓                                     |

## 四、报告隐私、合并与重试

- 日报、周报、月报与考试前 7/3/1 天提醒均使用 22:30；周日或月末重合时，邮件和飞书各只发送一条合并报告。
- 一个周期使用 `report:<yyyy-mm-dd>`；`report_deliveries` 使用 `report_key + channel` 唯一键。
- 邮件成功、飞书失败时，只允许重试飞书；反之亦然。
- 电脑关机或休眠错过时，下次 Windows 登录尽快补发；补发成功后不再重复。
- 报告不得发送资料原文、笔记正文、答案或聊天内容；日志不得写入授权码或完整 Webhook。

## 五、HP 实机兼容复测（非阻塞，待机会执行）

孩子 HP Pavilion Aero（Windows 11、Ryzen 5 5625U、16GB）当前不在身边。**该项已从 Phase 0.7 完成门槛移出**，改为可选兼容复测：设备可用后，以 Node 22 LTS 执行，目的为确认兼容性，不影响 Phase 0.8 进度。

```powershell
cd I:\ai-studybuddy-composer\windows-native
npm ci
npm run test:all
npm run measure:memory
```

必须同时满足：Docker Desktop 和 WSL2 未运行；学习服务可用内存至少 6GB；OCR、AI、邮件或报告峰值可用内存至少 3GB；无明显卡顿或持续分页增长；OCR 后 Python 退出；报告后 Node 退出；重复同周期不重复发送。

## 六、Phase 0.8 composer 试炼场验收（T04A）

在 `I:\ai-studybuddy-composer\converter\` 完成 DOCX、URL、本地 HTML、PPTX 的独立调通，形成能力卡与可重复 smoke test。T04A 不属于主系统正式验收，但为 T04B 在 `I:\ai-studybuddy\packages` 重新装配 Adapter 提供接口、安全、错误与验收证据。

| 格式 | 位置                       | 关键证据                                                                                                                               | 状态 |
| ---- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---- |
| DOCX | `converter\docx-test`      | mammoth 1.12.0；中文正文、视觉占位、空文档错误；`npm test` 4/4 通过                                                                    | ✅   |
| URL  | `converter\url-fetch-test` | undici 7.28.0；SSRF 全阻断、连接层回环 DNS 拒绝、5 MB/3 跳/10 秒限制、错误 body 取消与 Agent 关闭；真实 URL 首次成功；`npm test` 25/25 | ✅   |
| HTML | `converter\url-fetch-test` | jsdom + Readability；script/style 剥除、中文正文、fallback 路径                                                                        | ✅   |
| PPTX | `converter\pptx-test`      | jszip 3.10.1；数字页序、图片 OCR 提示、纯图片成功、损坏容器失败、命名/十进制/十六进制 XML entity 解码                                  | ✅   |

T04A 硬门槛：

- DOCX 中文正文、空文档错误、图片/图表占位均通过。
- URL 所有安全测试通过：协议/SSRF 拒绝、连接层回环 DNS 拒绝、5 MB/3 跳/10 秒限制、错误 body 取消和 Agent 关闭；至少一条真实 URL 成功（`zh.wikipedia.org` 首次抓取成功，重复访问触发 429 后返回人工出口）。
- HTML 中文正文可取，`script/style` 剥除。
- PPTX 页序、图片 OCR 提示、纯图片成功、损坏容器错误、命名/十进制/十六进制 XML entity 解码均通过。

## 七、Phase 0.8 正式 E2E 验收

Phase 0.8 已完成；以下保留为 S1/S2 后续补齐与 Phase 1 继续验收的候选清单，未在 T09 通过的项目不得伪称完成：

```text
选择学期教学日期 + 上传课程表图片
  → OCR/AI 识别预览与孩子确认
  → 原子化创建学期、课程实例、课表、目录和每学期 SQLite
  → 持续录入/确认考试日期
  → 每日首页完成证据驱动闭环
  → 资料/练习事件进入质量门与 StudyEvent
  → 22:30 生成脱敏 INFO，并在周/月观察窗形成 SIGNAL/TREND
```

验收时还要证明：`APP_DATA_ROOT\tmp` 清理不影响长期资料和笔记；正式 Adapter 不直接依赖试炼场脚本；真实数据和密钥不在 Git 中。

### 7.1 Phase 0.8 T09：隔离真实 E2E（2026-07-14）

| 验收项                           | 实际证据                                                                                                                                                                                                                            | 结论                                            |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| 隔离与隐私                       | 两个 run 使用独立 `APP_DATA_ROOT`、合成文本 PDF；仓库外 evidence 仅保存短哈希、状态、计数、耗时与裁剪截图。                                                                                                                         | ✅ 通过                                         |
| 基线                             | 隔离 worktree 中 `pnpm type-check`、后端 build、`pnpm test` 通过；后端 97/97、前端 12/12。                                                                                                                                          | ✅ 通过（Markmap chunk 大小警告非阻塞）         |
| 文本 PDF 转换                    | 两个 run 的 `material_convert` 均 1 次完成，终态前可读 normalized text。                                                                                                                                                            | ✅ 通过                                         |
| 真实 Provider 笔记生成           | 已配置 Provider 的 run 中 3 次调用均成功返回（`pixel-k12` / `gpt-5.5`；token 701/784/831；约 15.4/20.0/16.2 秒），但 `JSON.parse(response.content)` 失败，`note_generate` 用尽 3 次且没有落库笔记。错误仅留 `JSON_PARSE` 与短哈希。 | ❌ 未通过；不得用历史 smoke test 替代           |
| 无 Provider 降级                 | 显式无 Provider run 的 `note_generate` 3 次、约 14 秒后进入 `pending_quality_check`；页面显示“需要人工补文”，刷新不白屏。                                                                                                           | ✅ 通过                                         |
| 考试与 priorityBucket            | 浏览器考试表单未能提交；同一未来 deadline 的 API 对照为 overdue=0、confirmed=1、pending=2。任务列表仍按 deadline 而非 bucket 排序。                                                                                                 | ⚠️ 仅后端派生逻辑通过，不是浏览器闭环或排序验收 |
| 手动补文                         | `pending_quality_check` 下 `replace-text` 返回 `INVALID_STATUS`，符合当前后端仅允许 `conversion_failed` 补文的规则；页面没有可用手动补文入口。                                                                                      | ❌ T10 候选恢复 UX/状态契约缺口                 |
| 笔记/KaTeX/Markmap/模块/模块任务 | 没有成功笔记，因而无法验证。                                                                                                                                                                                                        | ⏳ 依赖真实 Provider 成功后重跑                 |
| tmp 安全清理读回                 | 已核对允许范围；因无完成笔记，未删除任何 tmp，避免形成无效通过结论。OCR 仍使用系统临时目录，尚无 `APP_DATA_ROOT\tmp` 清理实现或读回自动化证据。                                                                                     | ⏳ 依赖成功笔记与清理实现后重跑                 |

无 Provider run 的三次 note Job 尝试跨约 14 秒，符合 5 秒退避；本次运行**未观察到**重入，但当前 `setInterval` 不等待 `runOnce()`，不能将此写成 Worker 已证明串行。前端轮询在页面隐藏时不停止、状态变化不重置退避，亦未作为通过项。该 2026-07-14 首次运行不勾选完成；修复后复验结论见 7.2。

### 7.2 Phase 0.8 T09 修复后隔离复验（2026-07-15）

| 验收项               | 实际证据                                                                                                                                                                                                                                  | 结论                  |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| 修复基线             | `4f595c6` 修复 AI JSON 解析与考试表单受控值；`20a67c6` 收紧 JSON 解析失败错误消息并新增敏感哨兵回归测试。                                                                                                                                 | ✅ 通过               |
| 自动化回归           | `pnpm type-check`、后端 build、全量 `pnpm test` 通过；后端 102/102、前端 13/13。一次完整测试曾出现后端健康检查波动，单文件复跑与第二次全量均通过。                                                                                        | ✅ 通过，记录启动波动 |
| 真实 Provider 主路径 | 合成文本 PDF 转换 1 次完成，AI 生成 1 次完成；笔记 Markdown、highlights、Markmap、4 个知识模块、4/4 来源关联与 `material_note_completed` 事件均落盘。token 1949，AI 耗时 31,987 ms；2026-07-15 用户批准首次 AI 预算从 30 秒放宽到 35 秒。 | ✅ 通过               |
| 浏览器考试闭环       | 通过纯浏览器操作创建 pending 考试，截图 `01-courses-and-pending-exam.png`；不再使用 API 绕过证明考试创建。                                                                                                                                | ✅ 通过               |
| 浏览器笔记渲染       | 截图 `02-note-markdown-katex-markmap.png` 与 `05-after-tmp-cleanup-note-readback.png` 证明笔记正文、KaTeX 文本、Markmap 区域和知识模块可读。                                                                                              | ✅ 通过               |
| 无 Provider 降级     | 独立 run 显式清空 Provider；AI 3 次有限重试后进入 `pending_quality_check`，文本保留、无笔记、无模块；错误/状态字段不含 Key、正文短语、V8 诊断串或 Provider URL。浏览器刷新后仍可读。                                                      | ✅ 通过               |
| tmp 安全清理读回     | 仅删除当前 run 的 `semesters/<semesterHash>/tmp`，不碰 files/DB/其他学期；重启后端后 API 与浏览器均能读回笔记、模块和思维导图。                                                                                                           | ✅ 通过               |
| 证据脱敏             | 仓库外 evidence/browser-evidence 只保存截图、短哈希、计数、耗时和脱敏相对路径；截图前遮盖 semesterId 输入框可见值。                                                                                                                       | ✅ 通过               |

复验结论：T09 的 P0 功能阻塞已修复，核心业务闭环已经真实走通；首次 AI 生成耗时 31,987 ms，落入用户批准后的 35 秒预算。`docs/04` 可勾选 T09 与第一个里程碑。T10 人工补文恢复闭环、T11 考试确认/学习任务浏览器闭环、Worker 单飞和轮询优化仍保留为后续独立任务，不纳入本次通过结论。

### 7.3 Phase 1-T11：考试确认与任务创建闭环（2026-07-15）

| 验收项              | 实际证据                                                                                                                                                                                                | 结论                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| 后端考试确认契约    | 集成测试覆盖单考试读取、pending 首次确认、confirmed 幂等、rejected/superseded 409、不存在/跨学期 404、固定 S1 确认事件和确认后任务 priority 派生。                                                      | ✅ 通过                                 |
| 课程页与工作台      | 前端组件测试覆盖 pending 确认入口、confirmed 工作台入口、非法考试 URL、日期/倒计时/进度、当前考试任务隔离、任务创建和状态流转。                                                                         | ✅ 通过                                 |
| 多考试最小范围      | 组件与浏览器测试覆盖 confirmed 考试切换、近期最多 5 场概览、pending 只显示待确认，以及当前考试前后 7 个自然日的其他考试/关联截止任务只读提示。                                                          | ✅ 通过                                 |
| 资料课程上下文      | `courseInstanceId` 查询参数只接受当前学期课程，预选后手动切换会同步 URL；非法值不会驱动前端越权读取。                                                                                                   | ✅ 通过                                 |
| 自动化基线          | `pnpm type-check`、后端 build、前端 build 均退出码 0；隔离 `pnpm test` 后端 109/109、前端 32/32。                                                                                                       | ✅ 通过（Markmap chunk 大小警告非阻塞） |
| Chromium 浏览器闭环 | Playwright 在 `Asia/Shanghai`、后端 `127.0.0.1:4311`、前端 `127.0.0.1:4173` 下 1/1 通过；覆盖三场考试、两场确认、切换、近期概览、邻近提示、任务 `todo → doing → done`、刷新读回、资料上下文和非法 URL。 | ✅ 通过                                 |
| 数据隔离与证据      | 最终全量测试使用 `phase1-t11-20260715-221112-final-test`，最终浏览器验收使用 `phase1-t11-20260715-221352-final-e2e`；截图、trace、report、test-results 仅写入仓库外 `APP_DATA_ROOT/playwright`。        | ✅ 通过                                 |
| 非目标              | 未实现跨考试自动排程、智能任务平衡、模拟考、临考速背、T02 Provider 健康熔断或 S3 业务代码。                                                                                                             | ✅ 边界保持                             |

T09 的历史结论保持不变；T11 作为后续独立任务在本节形成新的通过证据，不回写或改写 T09 当时的未完成事实。

### 7.4 Phase 1-T08：本机配置中心与连接验收（2026-07-17）

| 验收项           | 实际证据                                                                                                                 | 结论        |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------ | ----------- |
| Windows 秘密存储 | Node `v22.23.1`、win32 x64 的 `@primno/dpapi` 与 `DpapiProtector` roundtrip 均为 true；自动化使用注入式 `TestProtector`  | ✅ 通过     |
| 状态与恢复       | 覆盖候选不落盘、active/prev 恢复、双损坏降级、唯一 tmp 清理、同通道串行锁和跨通道并行                                    | ✅ 通过     |
| 连接与热切换     | AI 逐 Provider 全通过才激活；SMTP/飞书 mock 测试隔离；新请求读取新 Router，在途请求继续使用旧 Router，熔断状态跨请求保留 | ✅ 通过     |
| API 安全         | 覆盖字段/数量/协议/长度上限、JSON-only、loopback Origin、恶意预检 403、状态响应不含密钥或路径                            | ✅ 通过     |
| 前端设置页       | 组件测试覆盖运行状态、成功/失败、密钥清空、不写 `localStorage` 和首次引导；浏览器在 `/settings` 与 `/courses` 验收可见   | ✅ 通过     |
| 自动化基线       | 后端 212/212，前端 10 files / 52 tests，根级 type-check、build、`pnpm test`、文档治理和 diff 检查通过                    | ✅ 通过     |
| 外部服务边界     | 未执行真实 AI、SMTP、飞书 smoke；浏览器未点击真实测试激活按钮                                                            | ✅ 边界保持 |

## 八、Phase 0.8 设计回填验收矩阵

| 编号    | 场景                 | 必须证明的行为                                                                                                                      | 通过证据                                                                   |
| ------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| 0.8-E01 | 学期初始化原子性     | “日期 → 课程表 → 预览 → 确认”成功时同时产生学期索引、`semester.db`、课程实例、课表和目录；任一步失败时不留下可见半成品              | 自动化集成测试覆盖成功与每个故障点；文件树、全局索引与业务库断言一致       |
| 0.8-E02 | 分学期隔离与恢复     | 不同学期使用不同业务库/目录/缓存；单个学期库的损坏、校验和恢复不影响其他学期                                                        | 创建两个学期的测试、故意损坏一个副本、`integrity_check` 和最近备份恢复记录 |
| 0.8-E03 | 学期生命周期         | `active → teaching_ended → follow_up → archived` 合法；归档默认只读，受控更正有审计；当前学期与旧 follow_up 的待办可聚合            | 状态迁移测试、首页聚合截图或 E2E 断言、审计事件断言                        |
| 0.8-E04 | 补考与重修           | 补考只新增原课程实例下的考试尝试；重修在新学期建新课程实例并链接原实例；临时补考课表仅在明确存在固定补课时写入                      | API/数据库断言：补考不增加课程实例；重修关联正确；历史资料复用为显式选择   |
| 0.8-E05 | 考试日期确认门       | 来源、识别置信度、孩子确认和变更历史均保存；未确认或变更待重确认日期不得驱动倒计时与 7/3/1 提醒                                     | pending/confirmed/superseded 状态的集成测试和报告预览断言                  |
| 0.8-E06 | 每日证据闭环         | 首页呈现明日准备、到期、待质检、错题复习和下一步；孩子可完成、修正或继续处理，不必接受 AI 排程                                      | 前端 E2E：任务/质量/事件状态迁移；StudyEvent 含证据引用                    |
| 0.8-E07 | AI 质量门与覆盖      | `required_fix`、`suggestion`、`uncertain`、`pending_quality_check`、`overridden` 的展示与规则正确；覆盖保留原结论、证据、原因和时间 | 单元/集成测试、审计记录断言；开放题不能被 AI 单方面判死                    |
| 0.8-E08 | AI/OCR/报告 fallback | PDF/OCR/AI/报告分别按文档规定降级；Provider 故障不锁死学习；双渠道失败保留本地 HTML                                                 | 注入失败的自动化测试、Job 重试/待质检记录、离线 HTML 与渠道错误摘要        |
| 0.8-E09 | 异常与报告尺度       | AI 仅生成异常候选及证据；孩子确认的合理特例不进入负面趋势；日报 INFO 非评价，周报 SIGNAL 只报重复模式，月报 TREND 需足够样本        | 固定时间窗测试数据、报告快照、基线/特例/置信度断言                         |
| 0.8-E10 | 隐私与报告发送       | 报告和日志不含资料正文、笔记正文、答案、API Key、SMTP 授权码或完整 Webhook；渠道按 `report_key + channel` 去重/单独重试             | 邮件/飞书 payload 快照、日志扫描、渠道失败重试测试                         |

### 8.1 已完成的 T05 Router 验收证据

- `packages/backend/test/ai-router.test.mjs` 覆盖单 Provider 成功、首 Provider 失败后的 fallback、全部 Provider 失败、超时后的 fallback、未配置与 OpenAI-compatible 响应解析。
- timeout mock 必须监听 `fetch` 第二参数中的 `AbortSignal`；忽略 abort 会让 SDK timeout 测试永久等待，不能作为有效的 fallback 验收。
- 已复跑 `pnpm type-check`、`pnpm build`、`pnpm test`：全量 77/77 通过；文档治理与 `git diff --check` 同步通过。
- 后端 API 测试以互不重叠的随机端口区间启动子进程，健康检查预算为 10 秒；`packages/backend` 的 `pnpm test` 固定 `node --test --test-concurrency=1`，避免多个 Express 子进程并行启动时由 CPU/端口竞争导致的偶发健康检查失败。

## 九、Phase 2 与全系统收口验收

### 9.1 Phase 2 S5 完成覆盖

| 范围                     | 自动化与浏览器证据                                                | 当前边界                                          |
| ------------------------ | ----------------------------------------------------------------- | ------------------------------------------------- |
| T02 模拟考 Schema 与生成 | migration v9、API 集成测试、确定性生成与学生安全 DTO              | 持久化模拟卷/尝试/答案/模块分析；不依赖真实 AI    |
| T03 模拟考前端           | 页面/客户端测试与 Playwright 覆盖生成、作答、刷新恢复、提交和结果 | 只消费 T02 API，不改后端事实                      |
| T04 临考速背             | 后端/前端测试与 Playwright 覆盖翻卡、计时、刷新恢复和窄屏         | 即时只读卡片；无 Schema、Worker 或真实 AI         |
| T05 冲刺计划             | 后端/前端测试与 Playwright 覆盖 7 天建议、状态降级和安全深链      | 即时只读计划；不持久化 `CramPlan` 或完成状态      |
| T06 工作台冲刺区         | 组件测试与 Playwright 覆盖已确认考试、窗口状态、跨考试切换和窄屏  | 仅前端聚合；不新增 API、Schema、StudyEvent 或写回 |

### 9.2 POST-PHASE2 分支全量验证（2026-07-21）

任务分支 `codex/post-phase2-full-validation` 使用仓库外隔离目录完成以下验证，退出码均为 0：

- `pnpm type-check`；
- 后端生产构建（含 OCR worker 复制）与前端生产构建；前端仅保留既有 KaTeX chunk 大于 500 kB 的非阻塞 warning；
- `pnpm test`：后端 237/237；前端 JSON reporter 明确确认 61/61 suites、137/137 tests；
- `pnpm test:e2e`：执行 `e2e/` 下 15 个 spec，Playwright 21/21 通过，覆盖完整学生旅程与 Phase 2 模拟考、速背、冲刺计划和考试工作台。

本轮不运行真实 AI、QQ SMTP、飞书、正式 Windows Task Scheduler 或其他外部 smoke；这些外部依赖不作为常规全量回归门槛。

### 9.3 POST-PHASE2 主线全量复验（2026-07-21）

任务分支完成 `git fetch --prune origin` 和 `git rebase origin/master` 后，以 `git merge --ff-only` 纳入干净的 `master`，未产生 merge commit。主线使用与分支不同的隔离目录重新完成：

- `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\post-phase2-full-validation-20260721-master-full` 下 `pnpm type-check`、后端生产构建、前端生产构建和 `pnpm test` 均退出码 0；后端 237/237，前端 JSON reporter 确认 26 个测试文件、61/61 suites、137/137 tests；
- `APP_DATA_ROOT=I:\ai-studybuddy-tmp\runs\post-phase2-full-validation-20260721-master-e2e` 下完整 `pnpm test:e2e` 执行 15 个 spec，Playwright 21/21 通过；
- 文档治理和 `git diff --check` 通过，测试/构建未留下受跟踪文件变更；前端仍只有既有 KaTeX 535.51 kB chunk 非阻塞 warning。

分支与主线证据范围一致，POST-PHASE2 收口完成；真实外部 smoke 仍未运行，也不据此宣称真实渠道可用。

---

## 十、Phase 1.5-T02 S7 ASR Composer Smoke

| 验收项                 | 实际证据                                                                                      | 结果                                                        |
| ---------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Windows CPU 安装与加载 | Python 3.10.19 独立 `.venv`；FunASR 1.3.22；torch/torchaudio 2.11.0+cpu；本地 SenseVoiceSmall | ✅                                                          |
| 官方来源与许可         | ModelScope 官方 `iic/SenseVoiceSmall`；API 与下载 README 均为 Apache License 2.0；FunASR MIT  | ⚠️ 模型只有 `master`，无 immutable revision；逐文件哈希补强 |
| 安全样例               | 本机 SAPI 合成中文/中英混合；程序生成静音、轻噪声、损坏 WAV 与非 WAV；无学生数据              | ✅                                                          |
| 正向短音频             | 两个语音样例各 3/3 非空、短哈希稳定；RTF 约 0.146–0.188                                       | ⚠️ 存在可见识别替换，不代表课堂准确率                       |
| 无语音/噪声            | 静音和轻噪声各 3/3 产生同一短误识别                                                           | ❌ no-speech 门禁未关闭                                     |
| 稳定错误               | 损坏 WAV → `AUDIO_DECODE_FAILED`；非 WAV → `AUDIO_FORMAT_UNSUPPORTED`                         | ✅                                                          |
| 结果契约               | 离线批次 14/14 通过 Draft 2020-12 JSON Schema；完整转写不进主仓库                             | ✅                                                          |
| 性能资源               | 模型加载 3,342 ms；总进程 28,056 ms；峰值工作集约 3,125.5 MiB；CPU 64.109 s                   | ⚠️ 仅短音频开发机事实，16GB/长音频须重测                    |
| 离线与清理             | 显式本地模型 + offline 环境变量成功；100 ms 轮询无 TCP；退出后无候选 Python 残留              | ⚠️ 未做防火墙隔离，证据为辅助级                             |
| 执行边界               | 未修改 `packages/`，未执行 FFmpeg，未实现 Adapter/API/Worker/前端                             | ✅                                                          |

**总判定：`PARTIAL`。** T02 执行完成并证明 Windows CPU 本地 ASR 的基本技术可行性；静音/轻噪声 false positive、immutable revision、离线证明强度、一次性 pip cache 偏差和首次树清单缺口阻止完整 `PASS`。下一步只能创建并审查 T03 FFmpeg 音频预处理计划；T04 产品装配前必须重验 no-speech、模型版本、许可/再分发、资源和课堂近似样例。

---

## 十一、Phase 1.5-T02/T04 G2 跨平台可验证离线隔离门禁

G2 的验收对象是**可验证的操作系统级离线隔离**，而不是某一个 Windows 配置、模型缓存状态或人工断网结果。每次验收必须明确 ASR 所在的平台、OS/运行时版本、CPU 架构及外部隔离实现；合格结果只适用于该组合，不外推为跨平台、产品接入或生产发布资格。

| 验收项                | 强证据通过标准                                                                                                                                              | 当前事实与状态                                                                                       |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| G2 外部强制隔离       | ASR 进程外部的 OS、容器或虚拟化层对其出站能力强制生效；可采用标准 Windows Firewall、Linux namespace/nftables、Docker `--network none`、独立虚拟机或等价机制 | 未执行新的平台组合验证                                                                               |
| G2 审计、清理与回滚   | 留存隔离启用前后状态、覆盖范围、阻断/拒绝结果、清理和回滚记录；不得遗留永久策略或未清理规则                                                                 | 未执行；每次平台实测须有独立计划和明确批准                                                           |
| G2 隔离下本地正向结果 | 隔离持续有效时，以显式本地模型路径取得结构化、可复查的本地 ASR 正向结果                                                                                     | 未执行；不能由缓存命中或进程未联网轮询替代                                                           |
| 辅助性事实            | `offline`/cache-only、DNS、hosts、代理、无 TCP 轮询或人工断网可记录为缓存、清理或环境事实                                                                   | 永远不能单独构成 G2 `PASS`                                                                           |
| 历史 Windows 证据     | 定制 Windows 10 的 Firewall profile 全部不可用时停止；不创建规则、不修改永久策略                                                                            | 旧 G2=`BLOCKED` 历史保留；在新语义下该环境可标记 `ENVIRONMENT_UNAVAILABLE`/`DEFERRED`，但不是 `PASS` |

现有门禁事实不变：G1/G3=`PASS`；T02=`PARTIAL`；T03=`PASS`；T04 为能力验证 `PARTIAL`、非 Adapter 装配；T05/T06 未启动。正式采用这些验收语义本身没有运行 Firewall、namespace、nftables、Docker 或虚拟机隔离试验，也没有下载/核验模型、重跑 G1/G3 或进入产品实现。任何真实 G2 执行仍须独立行动计划、审查和用户明确批准。

---

## 十二、PROCESS-RUNTIME-DEPLOY Windows 部署验收矩阵

本矩阵只评价 Windows 原生部署准备，不评价 S7/ASR 产品装配，也不把 G2 试验结论写成产品部署结论。所有会写运行数据的命令必须使用仓库外隔离根；E2E 必须使用 `H:\ai-studybuddy-tmp\runs\<task-id>` 这类可再生目录，不得使用正式 `%LOCALAPPDATA%\AIStudyBuddy\data`。

| 验收项     | 通过标准                                                                                                                                                                                                 | 当前证据口径                                                                                                                                    |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 部署包扫描 | 包含编译后后端/前端/shared、OCR Worker、OCR requirements、部署脚本、兼容清单；排除 `.git`、`node_modules`、密钥、真实数据、日志、tmp、models、Playwright 证据                                            | 记录部署包根、zip、扫描命令和排除扫描结果                                                                                                       |
| Bootstrap  | 使用机器安装根创建目录、复制 app、安装生产 Node 依赖、创建 OCR venv、生成无密钥 `production.env`；不依赖开发机盘符作为运行时                                                                             | 记录 InstallRoot、Node/Python 版本、venv 路径和无密钥声明                                                                                       |
| 生产启停   | 后端只监听 `127.0.0.1`；健康接口成功；前端 `/` 与 SPA fallback 返回 HTML；未知 `/api/*` 返回 JSON 404；停止后端口释放                                                                                    | 记录 PID、端口、health JSON、HTTP 状态和 stop 结果                                                                                              |
| OCR smoke  | RapidOCR 可导入；中文合成图、空白图、不存在路径、超时、Worker JSON 输出和临时清理通过；模型缓存不进源码                                                                                                  | 记录 `test-ocr-runtime.ps1` 输出和 RuntimeRoot                                                                                                  |
| 备份/恢复  | 白名单 `studybuddy.db` 与 `semesters/`、v2 manifest/hash/路径验证、`-WhatIf` 不落盘；`-EnableWrite` 受控恢复写入（8 步状态机：PREWRITE_APPROVED→WRITERS_QUIESCED→PRECHECK_PASSED→RECOVERY_POINT_VERIFIED→STAGING_WRITTEN_AND_VERIFIED→CUTOVER_IN_PROGRESS→POST_RESTORE_VERIFICATION→RESTORE_COMPLETED，含状态文件/中断标记/重启默认拒绝）。真实目标机写入仍待精确批准+R3-prewrite 签收（Wave 1/2 已隔离根与选项 C 演练通过） | 记录 `scripts/test-data-boundary.ps1` 合成夹具结果、Wave 1/2 演练证据（`.plans/evidence/phase3-wave1-t043-20260806.md`、`phase3-wave2-t043-real-sim-20260806.md`）；不得记录真实 backup path、payload 文件列表或 restore root |
| 配置/密钥  | 安装包和 Git 不携带真实密钥；AI/SMTP/飞书未配置时离线确定性主线可用，发送类能力不伪造成功                                                                                                                | 记录 `check-installation.ps1` secure-config、secret-files 和 plain-secret-config 检查                                                           |
| 任务计划   | 默认不注册真实发送；注册脚本以当前用户身份指向安装根 wrapper；卸载/注销不删学习数据                                                                                                                      | 记录单测或 WhatIf/静态检查；真实发送另行验收                                                                                                    |
| 安全网络   | 不新增防火墙规则，不绑定局域网，不暴露公网；日志不含 API Key、SMTP 授权码、完整 Webhook 或资料原文                                                                                                       | 记录端口监听和日志/密钥扫描                                                                                                                     |

当前 Node native 依赖安装还需要稳定网络取得预编译包；若下载失败会退回本地编译并要求 Visual Studio C++ Build Tools。bootstrap 脚本必须给出可操作错误，不能静默半配置。

---

## 十三、文档治理检查

每轮证据回填后运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check-docs-governance.ps1
git diff --check
```

Phase 0.7 的最终选型结论与实测数据已经同步回 `docs/04-*`、`docs/08-*` 与能力卡。Phase 1.5-T02 的 `PARTIAL` ASR 证据已同步回 `docs/04-*`、`docs/08-*`、composer README 与能力卡；不得将该结论描述为 S7 或 `AuralConverter` 已完成。Phase 0.8 T04A composer 试炼场证据与 T05 正式 AI Router 验收已同步回 `docs/04-*`、`docs/05-*`、`docs/08-*`、能力卡与本节。Phase 0.8 每完成一项正式 Adapter/API/页面验收，再把实际命令、结果和证据路径回填本计划；当前未完成的 HP 兼容复测与 Phase 0.8 E2E 不得用文档措辞掩盖。

## 十一、S7-MVP 本地 WAV → S2 验收（2026-07-25，已完成主线复验并推送 `origin/master`）

| 层级         | 必须验证                                                                                          | 禁止替代                                   |
| ------------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| Adapter      | 受控 PCM WAV 成功、格式/大小拒绝、运行时未配置、非零退出、超时、临时文件和 CLI 残留清理           | 只测 harness、只测 cache/offline、真实录音 |
| API + SQLite | 许可确认、学期/课程归属、编辑文本保存为 `text` material + `normalized_texts`、不创建转换/笔记 Job | mock DB、自动 Provider 调用                |
| 前端         | 许可复选框、格式/质量提示、转写后可编辑、显式保存、资料卡明确生成笔记操作                         | `localStorage` 暂存全文、自动保存          |
| 浏览器闭环   | fake CLI + 隔离 `APP_DATA_ROOT` 下完成“选择 WAV → 编辑 → 保存为 S2 输入”                          | 使用真实 Provider、Firewall/G2、Docker/WSL |
| 开发机 smoke | 固定外置 CLI/模型哈希复核后用合成 PCM WAV，记录脱敏退出码、耗时和清理结论                         | 把结果外推为用户机、完整 S7 或通用静音     |

S7-MVP 已完成任务分支测试、构建、文档治理、diff 检查与开发机 smoke；仍须主线复验及远端推送，在此之前不得标记为主线完成。

---

## 十四、当前版本验收矩阵（Phase 4，v0.8.1，2026-08-06）

> **用途**：本矩阵是"当前 v0.8.1 全系统验收"的**单一确定标准**，替代按 Phase 历史堆积的旧章节。每项引用真实证据路径，证据不足项明确标注待补，不虚构通过。
> **证据基线（2026-08-06 本轮实测）**：后端测试 342/342、前端测试 149/149（28 files）、浏览器 E2E 24/24、type-check 零错误、双端 build 通过、真实业务冒烟（真实 OCR venv 课表预览→创建学期→课程→考试确认→任务/时间线→资料上传→转换读回）通过。所有实测均在隔离 `APP_DATA_ROOT=H:\ai-studybuddy-tmp\runs\phase4-acceptance-20260806\<子项>` 下执行。
> **实测命令与结果（2026-08-06）**：`pnpm type-check` 零错误；`pnpm -r --filter backend run build`、`pnpm -r --filter @ai-studybuddy/frontend run build` 成功；`pnpm -r --filter @ai-studybuddy/backend run test` 342/342（duration 252s）；`pnpm -r --filter @ai-studybuddy/frontend run test` 149/149（28 files）；`pnpm test:e2e` 24/24（48.2s）；专项 `error-feedback-matrix.test.mjs`+`ai-logger-boundary.test.mjs`+`runtime-log-boundary.test.mjs` 17/17；`playwright test e2e/error-feedback-matrix.spec.ts` 3/3；真实服务冒烟 `node packages/backend/dist/server.js`（BACKEND_PORT=38080、PYTHON_PATH=OCR venv、FRONTEND_STATIC_ROOT=packages/frontend/dist）health 返回 v0.8.1，学生主路径 API 闭环通过。

### 14.1 S1-S7 学生主路径验收

| 子系统 | 验收项 | 通过标准 | 证据 | 状态 |
|---|---|---|---|---|
| S1 学习节奏 | 学期创建/切换/隔离 | 预览→确认→创建→切换→刷新恢复，跨学期隔离 | `semester-selector.spec.ts`（E2E）+ `study-rhythm` 后端测试 | ✅ 本轮实测（2026-08-06：E2E 24/24 含 semester-selector，后端 342/342；真实冒烟 OCR 预览→创建学期→设当前→读回一致） |
| S1 | 课程/课表/考试目标 | 课程 CRUD、周课表条目、考试确认/倒计时 | `course-schedule-exam-goals.spec.ts`（E2E） | ✅ 本轮实测（2026-08-06：E2E course-schedule-exam-goals 通过；真实冒烟创建课程 201、考试 201、确认考试 confirmed） |
| S1 | 任务/时间线 | 任务状态机、事件过滤、时间线展示 | `timeline.spec.ts`（E2E）+ `study-rhythm` 测试 | ✅ 本轮实测（2026-08-06：E2E timeline 通过；真实冒烟任务创建后时间线返回 `assessment_attempt_confirmed` 事件） |
| S2 资料笔记 | 上传/转换/AI 降级 | PDF/文本/图片上传→转换→AI 失败降级待质检 | `student-journey.spec.ts`（E2E）+ `note-builder` 测试 + 真实冒烟 | ✅ 本轮实测（2026-08-06：E2E student-journey 通过；真实冒烟文本资料上传 200、读回 200；无 Provider 时生成笔记返回确定性状态错误，符合 AI 降级边界） |
| S2 | 笔记渲染/知识模块 | Markdown/KaTeX/Markmap、模块来源关联 | `markmap-lazy-load.spec.ts`（E2E）+ `note-generation-parsing` 测试 | ✅ 本轮实测（2026-08-06：E2E markmap-lazy-load 通过，后端 342/342 含 note-generation-parsing） |
| S3 限时练习 | 生成/作答/批改 | 发起→作答→超时提交→批改结果→刷新恢复 | `practice-runner.spec.ts`（E2E）+ `practice` 后端测试 | ✅ 本轮实测（2026-08-06：E2E practice-runner 通过，后端 342/342 含 practice-generation/submit） |
| S3 | 练习历史 | 历史列表/结果只读 | `practice-history-archive.spec.ts`（E2E） | ✅ 本轮实测（2026-08-06：E2E practice-history-archive 通过） |
| S4 错题改错 | 归档/错因/重做/薄弱点 | 错题列表/详情/错因/重做/掌握状态 | `error-fixer.spec.ts`（E2E）+ `error-fixer-*` 后端测试 | ✅ 本轮实测（2026-08-06：E2E error-fixer 通过，后端 342/342 含 error-fixer 系列） |
| S5 期末冲刺 | 模拟考 | 生成/作答/提交/结果/模块分析/409 冲突 | `mock-exam.spec.ts`（E2E）+ `mock-exam*` 后端测试 | ✅ 本轮实测（2026-08-06：E2E mock-exam 通过，后端 342/342 含 mock-exam-schema/api） |
| S5 | 速背/冲刺计划/工作台 | 确定性只读卡、7 天计划、工作台冲刺区 | `cram-cards.spec.ts`、`cram-plan.spec.ts`、`exam-workbench.spec.ts`（E2E） | ✅ 本轮实测（2026-08-06：E2E cram-cards/cram-plan/exam-workbench 通过） |
| S6 家长报告 | 规则报告/AI 降级/去重 | 脱敏聚合、渠道级去重、双失败留档 | `parent-report-*` 后端测试 | ✅ 本轮实测（2026-08-06：后端 342/342 含 parent-report-service/delivery/runner；未跑真实渠道，见 14.6） |
| S7 课堂采集 | 受控 WAV→S2 handoff | 受控格式/同步转写/编辑/显式保存 | S7-MVP 验收（docs/09 §11）+ `class-capture` 后端测试 | ✅ MVP 边界本轮实测（2026-08-06：后端 342/342 含 s7-class-capture-api；受控 WAV 依赖本机 whisper.cpp，实机属 14.6 目标机门禁） |

### 14.2 失败反馈与脱敏（T02-R4）

| 验收项 | 通过标准 | 证据 | 状态 |
|---|---|---|---|
| 错误矩阵 | S1-S7 错误中文可操作且脱敏 | `error-feedback-matrix.test.mjs` 6/6 + `error-feedback-matrix.spec.ts` 3/3（E2E） | ✅ 本轮实测（2026-08-06：`node --test test/error-feedback-matrix.test.mjs ...` 17/17 含 6/6；`playwright test e2e/error-feedback-matrix.spec.ts` 3/3 passed） |
| 日志脱敏 | AI 日志字段 allowlist、落盘 ai-events.jsonl | `ai-logger-boundary.test.mjs` 4/4 | ✅ 本轮实测（2026-08-06：专项 `node --test` 17/17 含 4/4；全量后端 342/342 覆盖） |

### 14.3 安全与数据（Phase 3 Wave 0-3）

| 验收项 | 通过标准 | 证据 | 状态 |
|---|---|---|---|
| 秘密扫描（T02-R1） | 正式仓库+部署包 0 真实秘密 | `phase3-wave0-r1-summary.json` | ✅ 本轮实测（2026-08-06 核对：`signed-off-clean`，47 命中逐条人工复核后 `realSecrets=0`，全部为配置变量引用或测试合成值） |
| ACL 采证（T02-R2） | Windows 标准默认、0 reparse | `phase3-wave0-r2-summary.json`（误报已澄清） | ✅ 本轮实测（2026-08-06 核对：6 目录采证 `reparsePointsFound=0`，Windows 标准默认 ACL 结论，误报已修复记录） |
| 日志轮转（T05-3） | 单文件上限自动轮转、保留 3 份 | `runtime-log-boundary.test.mjs` 7/7 | ✅ 本轮实测（2026-08-06：专项 `node --test` 17/17 含 7/7；全量后端 342/342 覆盖） |
| 备份/恢复（T04-1/2/3） | 白名单备份、完整性检测、受控恢复写入 | `phase3-wave1/2` 证据 + `restore-data.ps1` 状态机 | ✅（2026-08-06：`restore-data.ps1` 静态核验默认 `-WhatIf` fail-closed（`RESTORE_VALIDATED_NO_WRITE`）+ `-EnableWrite` 8 步状态机；Wave 1/2 演练证据在 `.plans/evidence/`；真实目标机写入待批准，见 14.6） |

### 14.4 部署验收（docs/13 §12 八项）

| 验收项 | 通过标准 | 当前状态 |
|---|---|---|
| 部署包扫描 | 含编译产物、排除密钥/数据/日志 | ✅（2026-08-06 核对 R1：候选包 314 文件、命中 10 全部合成/引用、0 真实秘密；T02-E 边界） |
| Bootstrap | 目录/依赖/OCR venv/无密钥 env | ✅（选项 C 模拟验证为历史证据；本轮未重复全新安装，目标机门禁见 14.6） |
| 生产启停 | 127.0.0.1 监听、health、SPA fallback、停止释放 | ✅ 本轮实测（2026-08-06：`node packages/backend/dist/server.js` + OCR venv 启动，health 返回 v0.8.1，`BACKEND_HOST` 强制 `127.0.0.1`） |
| OCR smoke | RapidOCR 可导入、合成图通过 | ✅ 本轮实测（2026-08-06：OCR venv `rapidocr_onnxruntime`/`onnxruntime` 导入 OK；合成课表 28 字符识别、置信度 >0.99；真实 `POST /semesters/preview` 走通）。真实课表图片仍待补（14.6） |
| 备份/恢复 | 白名单 manifest/hash、受控写入 | ✅（2026-08-06：`restore-data.ps1` 状态机静态核验 + Wave 1/2 证据；真实目标机写入待批准） |
| 配置/密钥 | 安装包与 Git 无真实密钥 | ✅（2026-08-06 核对 R1 0 真实秘密 + M03 历史） |
| 任务计划 | 不默认注册真实发送 | ✅（2026-08-06 静态检查：`register-parent-report-task.ps1` 走 `ShouldProcess` 确认门，默认不注册） |
| 安全网络 | 无防火墙改动、无公网、日志脱敏 | ✅（2026-08-06：`BACKEND_HOST` 拒绝非 127.0.0.1、`start-production.ps1` 以 127.0.0.1 健康检查；T02A-F 历史） |

### 14.5 全量自动化基线

| 检查 | 通过标准 | 实测 |
|---|---|---|
| `pnpm type-check` | 零错误 | ✅ 本轮实测（2026-08-06：零错误，三个包 Done） |
| 后端 build / 前端 build | 成功 | ✅ 本轮实测（2026-08-06：后端 build 成功含 ocr-worker.py 拷贝；前端 build 成功） |
| 后端测试 | 全绿 | ✅ 本轮实测（2026-08-06：342/342，duration 252s，隔离根 backend-test） |
| 前端测试 | 全绿 | ✅ 本轮实测（2026-08-06：149/149，28 files，隔离根 frontend-test） |
| `pnpm test:e2e` | 全绿 | ✅ 本轮实测（2026-08-06：24/24，48.2s，隔离根 e2e） |

### 14.6 未完成/待补项（如实标注）

- **真实目标机验收**：用户电脑安装运行（独立门禁，docs/04 明确"未完成不得宣称"）
- **真实课表 OCR 解析**：合成图解析 0 条，需真实课表图片（docs/04 已知边界）
- **真实外部渠道**：S6 QQ SMTP/飞书未跑真实发送（非常规验证）
- **R3-postrestore / T02-R6**：目标机真实恢复演练后独立复核（Phase 3 收尾）

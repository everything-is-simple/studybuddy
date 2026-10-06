# 参考点核对表（03-Architecture 准备材料）

**版本**：v0.1.0
**日期**：2026-08-07
**状态**：📝 准备材料，待 03-Architecture 吸收
**用途**：对照四个参考仓库逐项核对"参考什么 → 采用/不采用 → 理由"，作为 03-Architecture 设计的输入
**核对方法**：4 个搜索子代理并行深挖 `H:\pi-references\{pi, pi-skills, inno-agent, pi-desktop}`，逐项核实文件/签名/代码
**上游**：docs/00 索引 §二、docs/01-TRD §2

---

## 一、动力 1：pi 系统 —— AI 底座（`H:\pi-references\pi`）

**作用**：决定"系统以什么为内核运行"。pi-studybuddy 以 pi-coding-agent 为 AI 底座，不修改内核，通过扩展接入业务。

### 参考点核对

| 参考点 | 实际确认（路径/文件/签名） | 采用/不采用 | 理由 |
|---|---|---|---|
| `extensions.md`（扩展生命周期钩子） | `packages/coding-agent/docs/extensions.md`（2988 行）。完整覆盖 `project_trust`/`resources_discover`/`session_*`/`before_agent_start`/`agent_*`/`turn_*`/`message_*`/`tool_execution_*`/`tool_call`/`tool_result`/`model_select` 等钩子。扩展放置 `~/.pi/agent/extensions/`、`.pi/extensions/`，TS 经 jiti 加载 | 采用 | pi-studybuddy 通过扩展接入业务的核心入口，生命周期钩子决定 StudyBuddy 各阶段何时挂载/卸载 |
| `skills.md`（SKILL.md 按需加载能力包） | `docs/skills.md`（231 行）。实现 [Agent Skills 标准](https://agentskills.io)，从 `~/.pi/agent/skills/`、`.pi/skills/` 等发现。SKILL.md 必含 frontmatter `name`/`description`，可选 `license`/`compatibility`/`metadata`/`allowed-tools`。`/skill:name` 调用，按需 `read` 加载（progressive disclosure） | 采用 | StudyBuddy 学习单元天然适合 SKILL.md 包装：description 常驻 system prompt，完整指令按需加载 |
| `sdk.md`（registerTool 等 API） | `docs/sdk.md`（1205 行）。SDK 主入口 `createAgentSession()`，导出 `defineTool`/`customTools`/`createCodingTools`。用法 `createAgentSession({ customTools: [myTool] })` 或 `tools: ["read","bash","my_tool"]` | 采用 | pi-studybuddy 桌面工作台程序化嵌入 pi 的第二入口；`customTools` 与扩展 `registerTool` 互备，便于集成测试直接构造 session |
| `prompt-templates.md` | `docs/prompt-templates.md`（95 行）。Markdown 片段，文件名即 `/name` 命令；位置 `~/.pi/agent/prompts/*.md`、`.pi/prompts/*.md`。支持 `$1`/`$@`/`${1:-default}` 位置参数 | 采用 | StudyBuddy 学习脚手架（如 `/spaced-repeat`、`/summarize-note`）可用 prompt 模板固化，无需写代码 |
| `providers.md`（多供应商模型） | `docs/providers.md`（341 行）。订阅类 OAuth（Codex/Claude/Copilot/xAI/OpenRouter）+ API Key 类 30+ 供应商（含国内 ZAI/Qwen/Xiaomi）。`/login` 写 `~/.pi/agent/auth.json`（0600） | 采用 | 不修改内核，全部模型层走 pi provider 体系；国内供应商覆盖对学习场景合规与成本控制是直接红利 |
| `models.md` | `docs/models.md`（565 行）。`~/.pi/agent/models.json` 添加自定义 provider/model；支持 4 种 API（openai-completions/responses/anthropic-messages/google-generative-ai）。`thinkingLevelMap` 对齐统一"思考强度"档位 | 采用 | 学习工作台接本地推理（Ollama）或自建代理走 models.json，不动内核即可切换底座 |
| `mcp 接入` | docs 无 `mcp.md`；`usage.md:303` 明确："It intentionally does not include built-in MCP"。源码无 MCP server/client 实现 | 不采用（内核侧） | pi 内核不内置 MCP；pi-studybuddy 若需 MCP，必须在扩展层自建 MCP client（通过 `registerTool` 暴露、用 `pi.exec`/`fetch` 连接 MCP server）。结论回填文档时注明"MCP 不在内核参考点范围" |
| `packages.md`（分发） | `docs/packages.md`（228 行）。`pi install npm:@foo/bar@1.0.0`/`git:...`/本地路径；写 `~/.pi/agent/settings.json`。`package.json` 的 `pi` manifest 声明 `extensions`/`skills`/`prompts`/`themes` 路径。核心包须列为 peerDependencies：`pi-ai`/`pi-agent-core`/`pi-coding-agent`/`pi-tui`/`typebox` | 采用 | pi-studybuddy 自身可作为 pi 包分发（学习单元包），依赖上述 5 个 peerDependency；分发机制决定"下载储存"阶段产物形态 |
| `registerTool` 工具注册契约 | `packages/coding-agent/src/core/extensions/types.ts:1251-1253`：`registerTool<TParams, TDetails, TState>(tool: ToolDefinition<...>): void`。`ToolDefinition`（449-498 行）必填 `name`/`label`/`description`/`parameters`/`execute`；可选 `promptSnippet`/`promptGuidelines`/`constrainedSampling`/`renderShell`/`prepareArguments`/`executionMode`。execute 返回 `{ content, details, usage?, terminate? }`，错误须 throw。`defineTool()` 辅助函数保留类型推断 | 采用 | "业务能力唯一入口"的契约依据。pi-studybuddy 所有学习工具（`recall_card`/`schedule_review`/`query_note`）必须经 `registerTool` 注入；返回 `void` + execute 抛错语义决定单件测试断言形态 |
| `@earendil-works/pi-ai` AI provider 抽象层 | `packages/ai/package.json`（v0.84.0）。`Provider<TApi>` 接口（`models.ts:97-149`）含 `id`/`name`/`baseUrl`/`headers`/`auth`/`getModels()`/`stream`/`streamSimple`。`createProvider<TApi>()` 工厂（762 行）。`Api` 类型联合 10 种已知 API。`builtinProviders()` 注册 38 个内置 provider 工厂 | 采用 | pi-studybuddy 多供应商可插拔的契约底座。不重写 provider，仅在扩展层用 `pi.registerProvider()` 注入学习场景专用 provider；所有 model 选择、鉴权、流式派发复用 pi-ai 抽象 |

### 装配纪律影响

1. **下载储存阶段**：`packages.md` 的 5 件套 peerDependencies 与 `providers.md` 的 auth.json 凭据路径是入库清单硬约束；MCP 不内置，不进入下载清单。
2. **单件测试阶段**：`registerTool` 契约（types.ts:1251-1253 + ToolDefinition:449-498）与 `sdk.md` 的 `defineTool/customTools` 是工具单件断言唯一依据——每个学习工具单测须断言 execute 返回形状与抛错语义，并断言 registerTool 返回 void。
3. **集成测试阶段**：`extensions.md` 钩子顺序与 `pi-ai Provider` 抽象（stream/streamSimple 契约）共同定义集成边界——须用 `createAgentSession({ customTools })` 拼装真实 pi-ai provider 验证工具与钩子协作。
4. **组装阶段**：以"扩展 + 技能包 + prompt 模板"的 pi 包形态组装，通过 `pi` manifest 声明四类资源路径，禁止改动内核源码。
5. **系统冒烟/E2E 阶段**：所有引用结论回填到 pi-studybuddy 有效编号文档：extensions 钩子顺序与 registerTool 签名回填到"组件治理-单件/集成测试"编号；packages peerDependencies 与 providers 凭据解析顺序回填到"下载储存"编号；MCP 不内置结论回填到"装配纪律-范围排除"编号。

---

## 二、动力 2：pi-skills —— 组件供给（`H:\pi-references\pi-skills`）

**作用**：决定"通用能力从哪来、怎么装配"。8 个现成技能按需引入，业务自建 skill 与其同构。

### 参考点核对

| 参考点 | 实际确认（路径/文件/字段） | 采用/不采用 | 理由 |
|---|---|---|---|
| SKILL.md frontmatter 仅 `name`+`description` 两字段 | README:85-101；6 个 SKILL.md frontmatter 全部只有这两字段 | 采用 | 极简、与 pi 生态原生兼容；description 是唯一常驻 prompt cache 的部分，符合 progressive disclosure |
| 触发/流程/陷阱/验证用正文章节而非 frontmatter 字段 | `vscode/SKILL.md:39` Gotchas；`youtube-transcript/SKILL.md:38` Notes；`browser-tools/SKILL.md:93` Efficiency Guide；`transcribe/SKILL.md:24` Output | 采用（章节约定） | 章节名不强制统一但语义分层清晰；自建 skill 应规定统一章节名（`## When to Use`/`## Usage`/`## Output`/`## Gotchas`） |
| `{baseDir}` 占位符引用 helper 脚本 | 全部 6 个 SKILL.md 的 bash 块用 `{baseDir}/xxx.js` | 采用 | 让技能目录可放任意位置而不改正文，是"自包含能力包"的关键 |
| 扁平目录（一层深） | README:43 "only looks one level deep for SKILL.md" | 采用 | 强制扁平结构，避免深层嵌套撑爆 prompt；学生本机资源有限，此约束有正面价值 |
| **重要漂移**：README 索引层与 SKILL.md 契约层不一致 | README:81 说 transcribe 是 "Groq Whisper API"；但 `transcribe/SKILL.md:3,8` 实际是本地 parakeet-cpp，无需 API key | 采用教训 | README 是"索引层"，SKILL.md 是"契约层"，二者会漂移；自建 skill 必须以 SKILL.md 为唯一事实源，CI 强制 README 与 SKILL.md 同步 |
| README:112 残留 `subagent` 技能，但 Available Skills 表无此目录 | README:112 | 不采用（视为缺陷） | 文档残留；pi-studybuddy 应有"技能清单 = 目录扫描"唯一真源，禁止 README 手维护清单 |
| 无 manifest/registry 文件 | 无 skills.json/yaml | 不采用（要补） | 技能发现纯靠目录扫描；pi-studybuddy 建议生成 `skills.manifest.json`（name/description/version/deps）便于启动校验与按需加载 |
| frontmatter 无 version/author/deps 字段 | 6 个 SKILL.md frontmatter 均无 | 不采用（要补） | 学生本机分发需要版本追踪与依赖声明；自建 skill 应扩展 `version`+`requires`（如 `requires: node>=18, ffmpeg`） |
| 无测试目录/测试文件 | 各技能目录仅 SKILL.md + helper + package.json | 不采用（要补） | pi-skills 靠 "## Output" 示例自证质量；pi-studybuddy 进入五阶段治理，单件测试阶段必须为每个引入技能写夹具 |
| `transcribe`：本地 ASR，仅 Apple Silicon macOS | `transcribe/SKILL.md:3` description；:8 本地 parakeet；:40-42 限制 | 部分采用（设计模式采用，实现重做） | 学生端"录讲座→转文字"是核心场景，但 transcribe 限 macOS arm64，pi-studybuddy 在 Windows 需自建等价物（whisper.cpp）；"本地优先、无云端、无 API key"边界设计对学生隐私友好，应保留 |
| `browser-tools`：Chrome DevTools Protocol 连 :9222 | `browser-tools/SKILL.md:3`；:21-81 能力；:93-194 Efficiency Guide | 不全量采用（取设计模式 + content 子能力） | 学生工作台不需通用浏览器自动化；但 CDP 连接+eval+截图+元素拾取设计模式可用于"在线题库抓取/学习平台自动登录"窄场景；建议只引入 `browser-content.js`（Readability+Turndown 提取） |
| `youtube-transcript`：video-id/URL→带时间戳字幕 | `youtube-transcript/SKILL.md:3`；:20 transcript.js；:38-41 Notes（不做摘要，无字幕不处理） | 采用 | 学生看教学视频转讲义是核心场景，直接引入；与 transcribe 形成"视频音轨→文字"vs"视频字幕→文字"互补 |
| `brave-search`：Brave Search API + URL 内容提取 | `brave-search/SKILL.md:3`（"Lightweight, no browser required"）；:28-49 搜索选项；:51-57 content.js | 采用 | 学生查资料/查文档是核心场景，直接引入；需注意 API key 在学生本机的密钥管理（免费层需信用卡，对学生门槛高，可能换 Bing/Google 或走代理） |
| 每个技能=自包含目录（SKILL.md + helper + package.json） | `browser-tools/` 含 8 个 .js + package.json + SKILL.md；`brave-search/` 含 search.js/content.js + package.json | 采用 | 自包含=可独立安装/卸载/测试；与五阶段组件治理的"单件测试"阶段天然契合 |
| progressive disclosure：description 常驻，正文按需加载 | README:87-101；description 是 frontmatter 唯一被索引部分 | 采用 | 学生本机 prompt cache 资源有限，8 个技能 description 短句常驻、正文按需，是防撑爆的关键 |
| helper 脚本不预读入 prompt，仅执行时调用 | 所有 helper 只在 SKILL.md bash 块以 `{baseDir}/xxx.js` 引用，agent 决定执行时才 fork | 采用 | 大块 JS 代码不进 prompt，只进进程；这是"能力包"与"prompt 注入"的分界 |

### 装配纪律影响

1. **五阶段位置**：8 个现成技能在"下载储存"阶段以 git clone 进入 `.pi/skills/`；在"单件测试"阶段每个技能独立跑 helper 脚本验证（pi-skills 自身无测试，pi-studybuddy 必须自建夹具）；在"集成测试"阶段验证 `{baseDir}` 替换、description 触发匹配、与 agent 契约；在"组装"阶段按学习场景按需挂载；在"系统冒烟/E2E"阶段跑端到端学习链路。
2. **"业务自建 skill 与其同构"具体含义**：同 frontmatter（name+description，建议扩展 version+requires）、同 `{baseDir}` 占位符、同扁平目录（一层深）、同 helper 脚本模式、同 progressive disclosure；但内容是 pi-studybuddy 业务能力（错题本生成/番茄钟/Anki 导出/课程表同步），且必须补 pi-skills 缺失的三项纪律——显式 `## Out of Scope` 章节、frontmatter 版本与依赖声明、单件测试夹具。
3. **漂移教训入纪**：pi-skills 的 README↔SKILL.md 漂移说明"索引层手维护必腐"，pi-studybuddy 应以"目录扫描 + SKILL.md frontmatter"为唯一技能真源，禁止手维护清单文件，CI 强制 README 索引与目录扫描一致。
4. **学生端取舍**：youtube-transcript / brave-search 直接采用；transcribe 取设计模式但跨平台实现重做（whisper.cpp 替 parakeet）；browser-tools 只取 content 子能力与 CDP 设计模式；gccli/gdcli/gmcli/vscode 与学生学习工作台关联弱，默认不引入。
5. **progressive disclosure 是硬纪律**：8 个技能 description 短句常驻 prompt、正文与 helper 按需加载、扁平目录一层深——这三条是防 prompt cache 撑爆的底线。

---

## 三、动力 3：inno-agent —— 业务化范本（`H:\pi-references\inno-agent`，MIT）

**作用**：证明"以 pi SDK 构建完整学习产品"可行且成熟。与 pi-studybuddy 最同类的产品（个人学习智能体），是业务接入 pi 的直接路线图。

### 参考点核对

| 参考点 | 实际确认（路径/文件/关键代码） | 采用/不采用 | 理由 |
|---|---|---|---|
| `inno-extension.ts` 用 `pi.registerTool()` 批量注册业务工具 | `apps/inno-agent/src/agent/inno-extension.ts` 的 `createInnoExtension()` 内，对每个 `createXxxTools()` 返回的 `ToolDefinition[]` 用 `for...of` 逐个 `pi.registerTool(tool)`。已确认工具集：L1 learner tools、scheduler tools（5 个）、channel tools（条件注册）、L2 wiki tools、L3 tools、`parse_document`、`ocr_image`、`web_search`、`create_practice_lab`、`ask_user_question`。同时 `pi.registerProvider()` 注册模型供应商，并通过 `pi.on("tool_call"/"tool_result"/"before_agent_start"/"session_start"/"turn_end"/"model_select")` 多钩子做路径守卫、错误集中日志、上下文注入、L3 增量索引 | 采用（核心模式直接借鉴） | pi SDK 标准扩展范式，"永不修改内核"原则的落地方式。pi-studybuddy 应同样以单一 extension factory + registerTool 批量挂载业务工具 |
| 三层记忆 memory/（L1 学习者画像 + L2 原生 wiki + L3 会话检索） | L1 `src/memory/learner/`：`profile-store.ts`（profile.json + events.jsonl）+ `auto-profile.ts` + `context-pack.ts`。L2 `src/memory/l2/`：`l2-search.ts` 实现 BM25 词法候选 30→前 8 作图谱种子→一跳图谱扩展，权重 DIRECT_LINK(0.5)/SOURCE_OVERLAP(0.4)/ADAMIC_ADAR(0.3)/TYPE_AFFINITY(0.1)；配套 wiki-graph/wiki-linker/wiki-maintainer/l2-index-store/semantic-chunker/summarizer。L3 `src/memory/l3/`：`sqlite-store.ts` 基于 `node:sqlite`（Node ≥ 22.5），schema 含 `chunks`+`chunks_fts`（FTS5/unicode61）+ 预留 `embeddings`；CJK 切 **bigram**（学习计划→学习 习计 计划），ASCII 整词小写，OR-combined MATCH；`recall.ts` 阈值门控；`indexer.ts` 基于 `last_offset + last_mtime_ms` 增量。三层受 `config.memory.{l1,l2,l3}Enabled` 控制，Simple Mode 全局总开关 | 采用（三层结构整体借鉴，实现细节按需简化） | 三层记忆是 inno-agent 核心差异化设计，"学习伙伴"区别于通用编程 agent 的根本。L1 必须有；L2 可借鉴但评估是否需知识图谱（个人学习场景图谱规模小，可先只做 BM25 + DIRECT_LINK）；L3 用 SQLite FTS5 + bigram 分词对中文学习场景非常合适，直接复用。Simple Mode 总开关设计值得借鉴 |
| 技能系统 + 内容中心 content-source/ | `src/content-source/index.ts` 的 `createContentSource(hub)` 根据 `hub.type` 返回 `GitHubContentSource` 或 `BundleServiceSource`。GitHub 路径：Git Trees API（recursive=1）取整树，缓存 5 分钟；文件从 raw.githubusercontent.com 拉取，带 token + 429/5xx 指数退避；通过 `CATEGORY_MARKER`（SKILL.md/preset.json）识别。bundle 服务：`GET {baseUrl}/index.json` 返回目录，每项作为 tarball 下载。`isSafeItemName` 路径安全校验。默认公开 hub 是 `Chloris-Blaxk/inno-agent-hub`。内置兜底预设：`presets/lesson-plan`、`presets/ppt-creation`、`presets/scenario-explain`。工作区级私有技能 `<workspace>/.skills/` 自动发现 | 采用（GitHub hub 路径直接复用，bundle 服务按需） | 技能 + 预设的内容中心机制对学习工作台极有价值。GitHub 路径零成本可直接借鉴；isSafeItemName 路径校验、5 分钟 tree 缓存、raw CDN + 退避重试都是实战细节。bundle 服务面向私有部署，pi-studybuddy 单机桌面可暂不实现，留扩展点。内置兜底预设 + 工作区 `.skills/` 私有技能双层结构必须采纳 |
| 练习实验室 terminal/（xterm.js over WebSocket） | `src/terminal/terminal-session-manager.ts` 按 session id 管理 PTY 会话；`local-pty-backend.ts` 跨平台 PTY（Windows PowerShell/Unix bash）；`run-record-store.ts` 持久化运行记录。WebSocket 在 `server.ts:4930` `new WebSocketServer({ noServer: true })`，`server.on("upgrade", ...)` 拦截 `/api/terminal/sessions/([^/?]+)/ws$`；`bindTerminalWs` 双向桥接 ws↔pty。前端 xterm.js。sentinel 机制 `__INNO_RUN_DONE_<runId> <exitCode>` 切片 pty 输出（Windows 用 `& { ... }; Write-Host`，Unix 用 `( ... ) ; printf`，外层 bracketed paste `\e[200~...\e[201~` 防 zsh 高亮破坏）；`before_agent_start` 把最近一次 RunRecord 注入系统提示词 | 采用（核心模式 + sentinel 机制直接借鉴） | "练习实验室"是学习工作台关键闭环——学习者写代码/命令、agent 读运行结果再讲解。xterm.js + WebSocket + PTY 是成熟方案，sentinel 切片 + bracketed paste + Windows PowerShell 兼容这些踩过坑的解法直接复用 |
| 多渠道消息 channels/（飞书/微信/QQ） | `src/channels/channel.ts` 定义 `ChatChannel` 接口（verify/parse/reply/push/sendFile?）、`StreamingReplyChannel`（流式卡片）、`ChannelRegistry`。`personal-dispatcher.ts` 的 `PersonalChannelDispatcher`：`DedupeStore` 去重；`chat-sessions.json` 持久化 channel chatId→inno sessionId 映射；支持 `/new` 指令。具体渠道：`feishu/`、`wechat/`、`bridge/`（QQ 等） | 不采用（大幅简化） | pi-studybuddy 定位"单用户单机 Windows 桌面学习工作台、无远程协作"，飞书/微信/QQ 多渠道回推面向服务化/移动端，桌面单机无此需求。保留 `ChatChannel`/`ChannelRegistry` 接口抽象（便于未来扩展），删除 feishu/wechat/bridge 全部具体实现、删除 `PersonalChannelDispatcher` 的 chat-session 映射与流式卡片逻辑。scheduler 推送目标简化为"桌面通知 + 应用内消息中心" |
| 主动调度 scheduler/（cron） | `src/scheduler/cron-scheduler.ts` 的 `CronScheduler`：进程内 `setInterval` 每 60 秒 tick（首次延迟 5 秒）；每 tick 遍历 `JobStore.list()`，跳过 disabled 和已在运行的（`this.running` Set 防重叠）；`isCronDue(cron, timezone, lastRunAt, now)` 判断到期；`executeJob` 调 `runPromptSerialized(prompt)`。`job-runner.ts`：`push_reminder` 直接格式化文本不调 LLM，其他类型调 agent。推送用 `channel.push(target, output)`；提醒类推送失败视为整次失败；一次性 cron 执行后自动 `enabled=false`。taskType 枚举 `daily_review/weekly_summary/learner_profile_reflection/spaced_review/push_reminder/custom_prompt` | 采用（调度核心 + 学习相关 taskType 借鉴，channel 推送简化） | 主动调度对学习场景极关键（艾宾浩斯复习、每日总结、周报），`spaced_review`/`daily_review`/`weekly_summary`/`learner_profile_reflection` 直接契合学习工作台。in-process setInterval + 60s tick + 防重叠 + 一次性 cron 自动禁用 + jobs.json/runs.jsonl 持久化都是简洁可靠方案。channel 枚举应替换为"桌面通知/应用内消息中心" |
| model-probe / provider-sync | `src/agent/model-probe.ts` 的 `probeProviderModels(input)`：服务端探测模型列表（浏览器不能直连供应商 API）；OpenAI 兼容用 `GET {baseUrl}/models` + Bearer，Anthropic 用 `x-api-key + anthropic-version`；`normalizeModelsUrl` 剥离 `/chat/completions`、`/messages` 后缀补 `/models`；10 秒超时、500 模型上限。`src/agent/provider-sync.ts` 的 `syncProvidersForSubagents`：把 providers 写入 `~/.pi/agent/models.json` + 设置 `~/.pi/agent/settings.json` 默认 provider/model；用 `__inno_managed` 标记仅覆盖来自 Inno 的条目。`pi.on("model_select")` 持久化默认模型 | 采用（model-probe 直接复用；provider-sync 视是否启用子代理而定） | 桌面应用需"添加供应商向导"探测模型列表，model-probe 即插即用。pi-studybuddy 单机桌面若不启用 pi-subagents 子代理，provider-sync 可暂缓；若启用则直接复用 `__inno_managed` 标记策略。`pi.on("model_select")` 持久化默认模型模式必须采纳 |
| workspace-path-guard / observability-extension 等扩展模式 | **workspace-path-guard**（`src/agent/workspace-path-guard.ts`）：`checkWorkspaceMutationPath(workspaceDir, requestedPath)` 解决"cwd 不是充分边界，模型可能输出过期父路径逃逸工作区"。流程：`normalizeToolPath`（处理 `@`/`~`/`file://`/Unicode 空格）→ `resolve` → `findExistingAncestor` → `realpathSync` 解析符号链接 → `isWithin` 判断。在 `pi.on("tool_call")` 拦截 write/edit，越界 `block: true`。**observability-extension**（`src/agent/observability-extension.ts`）：两层观测——扩展层 `pi.on` + Prompt 观察者 `session.subscribe`（agent_start/end、turn_start/end、tool_execution_start/end 带 args/result 摘要 + durationMs）；提取 token 用量；`safeHandler` 全包 try-catch 确保观测不影响 agent loop；`summarizeArgs/summarizeResult` 按工具类型做摘要 | 采用（path-guard 必须有；observability 强烈建议；其他按场景裁剪） | workspace-path-guard 是单机桌面工作台安全底线——学习者工作区隔离全靠它，符号链接逃逸、`~`/`file://`/Unicode 空格边角必须处理，直接复用。observability-extension 对调试和成本监控有价值，建议采纳但可精简。`open`/`xdg-open` 拦截对单机桌面可放宽为"仅警告不阻断"。`before_agent_start` 多源上下文注入是 inno-agent 上下文工程核心模式，必须借鉴 |

### 装配纪律影响

1. **位置**：inno-agent 在五阶段组件治理中处于"业务化范本/直接路线图"位置——它是与 pi-studybuddy 最同类的产品（个人学习智能体），证明了"以 pi SDK 单一 extension factory + registerTool 批量挂载 + 多个 `pi.on` 钩子"的范式能承载完整学习产品，pi-studybuddy 应以此为基础架构模板。
2. **可直接借鉴模式**：registerTool 批量注册 + before_agent_start 多源上下文注入（L1 画像 + 工作区 agent.md + 私有技能 + 最近运行记录）、三层记忆分层、xterm.js+WebSocket+PTY+sentinel 练习实验室、GitHub content-source 技能中心、cron-scheduler + 学习 taskType、workspace-path-guard 路径守卫、Simple Mode 总开关。
3. **需独立设计决策**：channels/（飞书/微信/QQ）应整体删除，保留接口抽象但替换为"桌面通知 + 应用内消息中心"；scheduler 的 channel 枚举同步替换；`open`/`xdg-open` 拦截对单机桌面应放宽为"仅警告"；provider-sync 视是否启用 pi-subagents 子代理决定。
4. **需结合 StudyBuddy 差异化能力**：inno-agent 的 L2 知识图谱（AA/source-overlap）对个人学习场景可能过设计，可先只做 BM25 + DIRECT_LINK；其 L1 画像是通用学习画像，pi-studybuddy 应把已验证的 StudyBuddy 学习者模型字段映射到 LearnerProfile schema，而非照搬。
5. **装配纪律红线**：所有学习行为必须通过 registerTool + `pi.on` 钩子实现，**永不修改 pi SDK 内核**；工具失败统一走 `pi.on("tool_result")` 集中日志；观测层全部 `safeHandler` 包裹。

---

## 四、动力 4：pi-desktop —— 使用者介面（`H:\pi-references\pi-desktop`，Apache-2.0）

**作用**：决定"学生看到的界面长什么样、桌面壳怎么搭"。把 pi coding agent 变成桌面工作台的完整实现，是 pi-studybuddy 使用者介面的直接架构来源。

### 参考点核对

| 参考点 | 实际确认（路径/文件/关键代码） | 采用/不采用 | 理由 |
|---|---|---|---|
| main / preload / renderer 三进程代码组织 | `src/main/`（窗口/托盘/协议/Host 监督，`main.ts` 顶部注释 "No business logic"）、`src/preload/preload.ts`（单文件，仅 `contextBridge.exposeInMainWorld("piBridge", bridge)`）、`src/renderer/`（React 19 + Vite）。README:203-210 明确列出 `src/{contract,main,preload,agent-host,renderer,shared}` 六个顶层目录 | 采用 | pi-studybuddy 同样是 Electron + React 桌面壳，三进程分层是 Electron 事实标准；直接复用目录划分 |
| agent-host 作为独立 utilityProcess | `src/main/host-manager.ts:203` `utilityProcess.fork(this.hostEntry, [], { serviceName: "pi-agent-host", stdio: "pipe", env })`，HostManager 负责 spawn/ping（15s 心跳、10s 超时）/restart（30s 窗口内最多 2 次）/pendingPorts 缓冲。`src/agent-host/index.ts` 入口用 `process.parentPort` 收消息、`createRpcServer()` 提供服务 | 采用 | 学习工作台同样要把 pi coding agent 与 renderer 隔离，避免 renderer 崩溃拖垮 agent 会话；HostManager 崩溃预算 + ping 是工业模式 |
| 会话/文件/配置/watcher 都在 agent-host | `src/agent-host/` 下：session-reader/session-history/session-index/session-watcher/session-content-cache/file-access/file-watch/handlers/skills-service/plugins-service/model-runtime/toolchain-runtime 等 | 部分采用 | agent-host 集中"会话/文件/扩展/watcher"分层值得借鉴；但 pi-studybuddy 业务化层（学科/学习计划/错题/学情）应在 agent-host 内独立成模块，而非散落在 handlers.ts——这是 pi-studybuddy 自建边界 |
| TypeScript 约束的 IPC 契约文件 | `src/contract/api.ts` 定义 `interface Api`（~50 个方法）+ `interface Streams`（9 个服务端推送主题）；`desktop.ts` 定义 `PiBridge`（renderer↔main 的 IPC 表面） | 采用 | 类型化契约消除 renderer↔main↔host 通信"魔幻字符串"，pi-studybuddy 必须有等价契约层 |
| RPC 层（自研轻量 MessagePort RPC） | `src/contract/rpc.ts`：自研"轻量 MessagePort RPC，无外部框架"。五种 wire 消息：`request/response/subscribe/unsubscribe/event`。`createRpcServer()` 在 agent-host 内 `attachPort(MessagePort)`；`createRpcClient(port)` 在 renderer 提供 `call(method, ...args)` 和 `subscribe(topic, key, on)`。`AnyMessagePort` 兼容 DOM MessagePort/utilityProcess/Node worker_threads | 采用 | 自研 RPC < 200 行、无依赖、可测，比引入 electron ipc-rpc 库更可控。pi-studybuddy 直接复用此文件 |
| MessagePort 经主进程转发 | `src/preload/preload.ts:12` 接收 `desktop:host-port` IPC 事件，把 MessagePort 通过 `globalThis.postMessage(..., [port])` transfer 给页面；`src/main/ipc.ts:161` 在 `desktop:connect-host` 处理函数中 `manager.createRendererChannel()` 创建 `MessageChannelMain`，再 `event.sender.postMessage("desktop:host-port", null, [port1])` | 采用 | sandbox + contextIsolation 下传输 MessagePort 的标准做法，pi-studybuddy 直接照搬 |
| BrowserWindow sandbox:true | `src/main/window.ts:36-42`：`webPreferences: { preload, contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true }`。`scripts/check-desktop-security.mjs:75` 硬断言 `windowFactory.includes("sandbox: true")` | 采用 | sandbox 是 Electron 渲染进程默认应开的安全开关，对学习工作台零代价 |
| 严格 CSP | `src/main/protocol.ts:11-25` 定义 `CSP` 常量：`default-src 'self' app:; script-src 'self' app:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`。`handleAppProtocol` 每个静态响应头附 `Content-Security-Policy: CSP`。HTML 预览用更严格 `HTML_PREVIEW_CSP`（`form-action 'none'`） | 采用 | pi-studybuddy 也是 app:// 自定义协议加载，CSP 模板直接复用；预览 HTML 时"更严格独立 CSP"模式对学情报告/笔记预览同样必要 |
| preload 只暴露受控桥接 | `src/preload/preload.ts:223-225` 仅 `contextBridge.exposeInMainWorld("piBridge", bridge)`。`PiBridge` 接口（`desktop.ts:97-185`）穷举所有方法，无任意 IPC 通道 | 采用 | 受控桥接是 sandbox 模式下唯一 renderer→main 通道，必须遵循"白名单接口"模式 |
| credential-vault（DPAPI 密钥库） | `src/main/credential-vault.ts:1` `import { safeStorage } from "electron"`，`safeStorage.isEncryptionAvailable()` 校验后用 `safeStorage.encryptString`/`decryptString` 加密 JSON 内容，写文件 `mode: 0o600`（原子写：temp + rename）。Windows 上 `safeStorage` 后端即 DPAPI。键格式严格校验：`/^channel:(weixin\|telegram\|feishu):[a-z0-9._-]{1,160}$/i` | 采用 | 学习工作台需保存学生模型 API Key 和家长联系凭证，DPAPI 加密是 Windows 单机事实标准。pi-studybuddy 把键格式从 `channel:xxx` 改成 `modelProvider:xxx`/`parentContact:xxx` |
| 内置浏览器 Main-owned WebContentsView | `src/main/browser/browser-tab-manager.ts:2280` `createSecureView()` 返回 `new WebContentsView({ webPreferences: { session, sandbox: true, ... } })`，由 BrowserTabManager 在 Main 持有。README:167 明确："远程网页只进入 Main 创建的沙箱化 WebContentsView，不获得应用 preload、Node 或主 Renderer bridge" | 部分采用 | 若 pi-studybuddy 不做"内置浏览器"可整段省略；若要做"在线题库/学习网站"功能，必须照此实现，绝不能让远程网页进 renderer |
| Agent 授权弹窗 | `browser-authorization-coordinator.ts` + `browser-persistent-grant-store.ts`；`BrowserAuthorizationDialog.tsx:29-49` 弹窗根据 `request.minimumPermission` 显示三级能力说明；`browser-runtime-grant` TTL = 8h；`persistentGrants` 按 sessionId 存 | 部分采用 | pi-studybuddy 没有独立 Agent，但有"AI 学习助手"——若助手要替学生查网页，必须沿用"会话级临时权限 + 持久权限 + 弹窗确认 + TTL"四件套；若 AI 不触达浏览器，省略 |
| 会话管理（创建/切换/重命名/搜索/流式回复/工具调用视图/上下文压缩状态） | API 层 `sessions.list/get/context/rename/delete/export`；Host：session-reader（读 ~/.pi/agent/）、session-index、session-content-cache、session-history（分页 cursor 用 `dev+ino+birthtimeMs` 哈希防陈旧）。UI：SessionSidebar（按日期分组、模糊搜索、unread 计数）。流式回复通过 `Streams["agent.events"]`；工具调用视图 `countToolCallBlocks`；上下文压缩状态 `onContextUsageChange` | 采用 | 学生与 AI 助手对话历史同样需要这套生命周期管理；分页 cursor 的"防陈旧"设计对长学习会话尤其重要 |
| 技能/插件/模型统一管理 | Skills：`agent-host/skills-service.ts` 优先 `https://skills.sh/api/search`，fallback `runNpx(["skills","find",q])`。Plugins：`plugins-service.ts:7-13` 直接 `import { DefaultPackageManager, ... } from "@earendil-works/pi-coding-agent"` + plugin-worker 进程。模型：`model-runtime.ts` + `models.list/modelsConfig.get/set/test` + OAuth | 部分采用 | Skills 体系应替换为"学习技能包"（学科/章节/题型模板），保留 install/set/getContent 三件套但重命名语义。Plugins 应省略（不让学生接触 pi 插件机制）。模型配置必须保留（学生配置多个供应商），`modelsConfig.test` 一键测试连通性很有价值 |
| 开发者工具发现：Node/npm/Python/uv/Git/Bash/Bun | `shared/toolchains/types.ts:1-16` `TOOL_CAPABILITY_IDS = ["shell.bash","shell.powershell","vcs.git","js.node","js.npm","js.npx","js.bun","python.interpreter","python.uv","python.uvx","search.rg","search.fd","data.jq","network.curl"]`。`main/toolchains/manager.ts`（ToolchainManager）+ `probes/node.ts`（MINIMUM_NODE_VERSION="22.19.0"，MAXIMUM_VERIFIED_NODE_MAJOR=24，health=unsupported/unverified/healthy）+ `probes/capabilities.ts` + `discovery-registry.ts`。窗口 focus 时 60s TTL 重扫 | 采用 | OCR venv/whisper.cpp 依赖"发现健康的 Python/uv/Node"——直接复用此机制可避免学生手动装环境 |
| 统一绝对路径执行环境 | `agent-host/toolchain-runtime.ts`：`prependPath(env, directories, platform)` 把托管工具目录前缀到 PATH；`cloneDescriptor` 复制 argvPrefix/pathEntries/envPatch。安装到 `app.getPath("userData")`，不修改系统 PATH/注册表。`scripts/check-desktop-security.mjs` 风格的不变量校验 | 采用 | OCR venv 和 whisper.cpp 调用必须走"统一绝对路径"，否则 Windows PATH 不全时极易失败 |
| 内置 ripgrep/fd | `main.ts:64-66` `["search.rg","search.fd"]` 必须有 `bundled` provider 且 `healthy`；`build/toolchains/core-catalog.json` + `prepare-bundled-tools.mjs` | 采用 | 学习资料/笔记本地搜索的基础能力，离线可用 |
| 文件体验：项目目录/Git 分支/worktree/文件浏览/Markdown/KaTeX/Mermaid/docx 预览 | `main/ipc.ts:178-190` `desktop:select-directory`→`dialog.showOpenDialog`，记录 `recentCwds`（最多 12 条）。`FileExplorer.tsx` lazy 加载。`@文件引用`（`allowed-roots.ts` 校验）+ `session-file-references.ts` 跟踪。`MarkdownBody.tsx`：react-markdown + remark-gfm + remark-math + rehype-katex + rehype-raw + rehype-sanitize + SyntaxHighlighter。Mermaid（`mermaid` 包）。docx 预览（`mammoth` + DOCX_PREVIEW_MAX_BYTES）。`file-watch.ts`：`fs.watch({ recursive: true }, emitChange)` 100ms 防抖→`Streams["files.changed"]` | 采用 | Markdown + KaTeX 是学习场景（公式渲染）硬需求，技术栈直接复用；学生 `@` 引用学习资料/错题截图是核心交互；文件变更监听让 AI 助手能感知学生修改 |

### 装配纪律影响

1. **位置**：pi-desktop 在五阶段组件治理中处于"参考实现层"——被验证的 Electron + pi coding agent 桌面壳完整实例，pi-studybuddy 取其"三进程 + 契约 + 安全 + 工具发现 + 文件体验"五件架构骨架，业务层（学科/学情/错题/学习计划）独立自建。
2. **可直接借鉴**：`contract/{api,rpc,desktop,browser,types}.ts` 类型化契约模式、`host-manager.ts` utilityProcess 监督（spawn/ping/restart 预算）、`credential-vault.ts` safeStorage/DPAPI 模式、`toolchains/` 发现-探测-安装-绝对路径执行四段式、`file-watch.ts` fs.watch→Streams 投递模式——这五块可作为 pi-studybuddy "装配零件"直接搬运改名。
3. **必须独立设计**：业务化"会话语义"（pi-desktop 会话是 coding agent 对话，pi-studybuddy 是学习对话——需附加学科标签/学习目标/错题关联）、"Skills 体系"（pi 的 Skills.sh 不适合学生，应替换为"学习技能包"）、"Plugins"（应省略）、"内置浏览器"（视 TRD 决定）、"消息渠道"（微信/Telegram/飞书对学生场景应省略）。
4. **不变量必须保留**：sandbox:true / 严格 CSP / preload 仅暴露 PiBridge 白名单 / credential-vault 用 safeStorage / Host RPC 契约化——这五条是 Electron 安全底线，pi-studybuddy 必须有等价的 `check-desktop-security.mjs` 风格不变量校验脚本。
5. **装配顺序**：先落地"main + preload + renderer + agent-host"四进程骨架与 `contract/` 契约（可逐字搬运），再叠加 toolchain 发现/credential-vault/file-watch 三个公用零件，最后才在其上自建学习业务模块——避免业务与壳耦合，确保五阶段治理中"壳层稳定、业务可演化"。

---

## 五、跨仓库核对结论（喂给 03-Architecture）

### 5.1 直接采用（架构骨架）

| 来源 | 组件 | pi-studybuddy 落点 |
|---|---|---|
| pi | extensions/skills/sdk/prompt-templates/providers/models/packages 全套 docs + registerTool 契约 + pi-ai 抽象 | 业务能力唯一入口、扩展生命周期、技能体系、模型供应商层 |
| pi-skills | SKILL.md 格式（name+description frontmatter + 正文章节 + {baseDir} + 扁平目录）、progressive disclosure | 自建 skill 与其同构，补 version/requires/Out of Scope/测试夹具 |
| inno-agent | registerTool 批量注册 + `pi.on` 多钩子、三层记忆（L1 profile/events、L2 BM25+图谱、L3 SQLite FTS5 bigram）、terminal 实验室、content-source GitHub hub、cron-scheduler + 学习 taskType、workspace-path-guard、Simple Mode | 业务化范本，直接借鉴模式，channels/ 大幅简化 |
| pi-desktop | 三进程 + contract 类型化 IPC + 自研 RPC + sandbox/CSP/preload 受控桥接/credential-vault + toolchain 发现-探测-安装-绝对路径 + file-watch + Markdown/KaTeX/Mermaid/docx 预览 | 使用者介面五件架构骨架直接搬运改名 |

### 5.2 不采用 / 大幅简化

| 来源 | 组件 | 处置 |
|---|---|---|
| pi | MCP 内核侧 | 内核不内置；若需在扩展层自建 MCP client |
| pi-skills | transcribe 实现（仅 Apple Silicon）、browser-tools 全量、gccli/gdcli/gmcli/vscode | transcribe 取设计模式跨平台重做（whisper.cpp）；browser-tools 只取 content 子能力；其余默认不引入 |
| inno-agent | channels/（飞书/微信/QQ）、PersonalChannelDispatcher、流式卡片 | 整体删除，保留 ChatChannel/ChannelRegistry 接口抽象，推送目标改为桌面通知 + 应用内消息中心 |
| pi-desktop | Plugins、Skills.sh、内置浏览器（视需要）、微信/Telegram/飞书渠道 | Plugins 省略（不让学生接触 pi 插件机制）；Skills 体系替换为"学习技能包"；浏览器/渠道视 TRD 决定 |

### 5.3 必须独立设计

| 组件 | 理由 |
|---|---|
| 学习业务层（学科/学习计划/错题/学情/家长报告） | pi-desktop 是通用 coding agent 壳，无学习业务；StudyBuddy S1-S7 业务认知迁移而非实现复制 |
| 学习技能包体系 | pi-skills 是通用技能，pi-desktop Skills.sh 面向开发者；学生需要"学科/章节/题型模板"语义的技能包 |
| 家长报告脱敏通道 | inno-agent channels 面向 IM 推送，pi-studybuddy 家长报告是异步脱敏摘要，需独立设计（本地导出 + 可选邮件/打印） |
| WPS COM 桥 | 四参考仓库均无 WPS COM 自动化，需独立设计（Python pywin32 子进程，TRD 待决项 1） |
| TTS skill | 四参考仓库均无 TTS，需自建（SAPI/edge-tts，TRD 待决项 4） |

---

## 六、版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1.0 | 2026-08-07 | 初始版本：4 个搜索子代理并行核对四参考仓库，产出参考点核对表 + 跨仓库结论 |

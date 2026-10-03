# 01-TRD 技术需求

**版本**：v0.2.4
**日期**：2026-08-09
**状态**：✅ 已审查批准；T-M5-011 执行中。当前落地顺序为开发机真实主路径优先，运行资源和默认配置在开发机闭环后再复制到使用机。

> T-M5-011 现实校正：本文件的技术能力声明必须以开发机真实运行结果为准；Adapter、mock、Job 登记或安装冒烟不能单独证明产品闭环。问题总账见 [系统集成/02](./系统集成/02-系统问题总账与整改清单.md)。
**上游**：docs/00 索引；参考：`H:\pi-references\pi`、`pi-skills`、`inno-agent`、`pi-desktop`；核对依据：[docs/prep-参考点核对表.md](./prep-参考点核对表.md)

---

## 1. 项目定位

**pi-studybuddy = pi（AI 底座）+ pi-skills（组件供给）+ StudyBuddy 业务能力（内核）+ pi-desktop 式桌面壳（使用者介面）**

- 服务对象：一名在 Windows 本机学习的学生。
- 核心价值：把课程/考试目标、学习节奏、资料笔记、练习、错题和考前冲刺连成可持续闭环；家长接收脱敏异步摘要。
- 与 ai-studybuddy 的关系：**业务认知迁移、实现重构**。ai-studybuddy 已完成 S1-S7 原型验证（342 后端测试 + 149 前端测试 + 24 E2E 基线）；pi-studybuddy 以 pi 为底座重新组装，不复制其实现。

## 2. 技术底座（TRD 决策）

### 2.1 AI 底座：pi-coding-agent

| 决策 | 内容 |
|---|---|
| 内核 | `@earendil-works/pi-coding-agent`（npm，monorepo `packages/coding-agent`） |
| 铁律 | **不修改内核**；所有业务能力通过 `registerTool`、扩展（Extension）、技能（Skill）接入 |
| 运行时 | Node >= 20.6（本项目基线 Node 24，与 ai-studybuddy 部署基线一致） |
| 语言 | TypeScript（strict），ES modules |

**已确认的 pi 能力面**（从 `H:\pi-references\pi\packages\coding-agent\docs\` 核实）：
- `registerTool`（工具注册，inno-agent 用 `pi.registerTool(...)` 注册 OCR/文档/练习等工具）
- Extensions（`extensions.md`）：自定义生命周期钩子
- Skills（`skills.md`）：SKILL.md 按需加载的能力包
- Prompt templates / Themes（`prompt-templates.md`）
- MCP 工具接入
- `@earendil-works/pi-ai`：AI provider 抽象（多供应商可插拔）

### 2.2 组件供给：pi-skills + 自建技能

| 技能 | 来源 | 用途 |
|---|---|---|
| `transcribe` | badlogic/pi-skills | 音频转文字（ASR 补充） |
| `browser-tools` | badlogic/pi-skills | 浏览器自动化（备选） |
| `youtube-transcript` | badlogic/pi-skills | 视频讲义转写（备选） |
| 自建 `studybuddy-*` 系列 | 本项目 | 业务技能：格式转换、OCR 课表、TTS 朗读、练习生成等 |

技能治理：**下载储存 → 单件测试 → 集成测试 → 组装 → 系统冒烟/E2E**（docs/00 §四铁律）。

### 2.3 业务内核：StudyBuddy 能力迁移

从 ai-studybuddy 迁移**业务认知与数据模型**（不复制实现）：
- 考试驱动学习闭环：学期/课程/考试 → 资料笔记 → 知识模块 → 限时练习 → 错题改错 → 期末冲刺 → 家长报告
- 数据模型：global DB（学期注册表）+ 每学期独立 SQLite（semester.db）
- API 信封：`{ success, data, error }`
- 隐私边界：脱敏报告、AI 日志 allowlist、错误中文可操作且脱敏

### 2.4 使用者介面：参考 pi-desktop（Apache-2.0）

| 参考点 | pi-desktop 实现 | pi-studybuddy 采用 |
|---|---|---|
| 进程架构 | Electron 三进程：main / preload / renderer + agent-host | ✅ 采用 |
| IPC | `contract/` 类型化 IPC 契约 + RPC 层（TypeScript 约束） | ✅ 采用 |
| 安全 | `sandbox: true`、严格 CSP、preload 只暴露受控桥接 | ✅ 采用 |
| 内置浏览器 | Main-owned `WebContentsView`，远程网页不进 renderer | 可选（学生端以本机内容为主，浏览能力按需） |
| 会话管理 | 创建/切换/重命名/搜索/流式回复/工具调用视图 | ✅ 采用（**对话默认主入口**：应用启动即打开"💬 对话"标签页，承载 pi 原生 AI 对话，不废弃；详见 02-PRD §3.11 + 03-Architecture §6.7 + 09-UI §4.2） |
| 技能管理 | 搜索/安装/配置 Skills、插件管理 | ✅ 采用 |
| 文件体验 | 项目目录/Git 分支/文件浏览/预览（Markdown/KaTeX/Mermaid/docx） | ✅ 采用 |
| 工具发现 | 发现验证 Node/Python/uv/Git/Bash，统一绝对路径执行环境 | ✅ 采用（OCR venv、whisper.cpp 依赖此） |

## 3. 格式矩阵（重构目标）

| 类别 | 格式 | 方案 |
|---|---|---|
| 文档 | pdf、docx、pptx | 复用 ai-studybuddy 已验证转换器（jszip/mammoth/pdf-parse），重新实现 |
| 文档 | **doc、ppt、xls**（旧二进制，常见课堂资料） | **WPS COM 转中间格式**（doc→docx、ppt→pptx、xls→xlsx）→ 现有管道。本机已装 WPS，零新依赖 |
| 表格 | xlsx、csv | xlsx：jszip 提取 sharedStrings；csv：文本直接 |
| 文本 | txt、md、json、html | 文本直接提取 |
| 图片 | jpg/jpeg/png/webp/gif/bmp/tiff | OCR venv（onnxruntime/PIL 原生支持全格式） |
| 办公衍生 | odt、ods、odp、rtf、epub | jszip 提取 / RTF 自写剥离 |
| 音频 | WAV（受控）→ whisper.cpp | S7-MVP 底座迁移；扩展 mp3/m4a 经 ffmpeg 转 WAV（备选） |
| TTS | 文字朗读 | Windows SAPI（系统自带）或 edge-tts（可选），封装为 skill |
| 拒绝（资料导入） | 压缩包（zip/7z/rar 当学习内容解析）、邮件、宏文档（xlsm/docm/pptm） | 明确提示，不解析。注：备份恢复用 zip 作容器不在此列（见 02-PRD §3.10） |

> 关键决策记录：**不引入 SheetJS**（npm `xlsx@0.18.5` 有 CVE-2023-30533/CVE-2023-22365 且 registry 停更）；doc/ppt/xls 用 WPS COM 转换而非自行解析二进制。

## 4. 系统形态（重构范围）

| 形态 | 技术 | 优先级 |
|---|---|---|
| 桌面应用 | Electron（pi-desktop 架构） | P0（学生本机主入口） |
| Web UI（可选） | React（inno-agent 有 React 19 + Tailwind 4 参考） | P1 |
| 终端 CLI | pi TUI 原生（`pi` 命令 + 项目内 skill） | P1（开发/调试用） |

## 5. 安全与隐私边界

- 只监听 `127.0.0.1`；无公网入口、无云数据库。
- 真实密钥只在本机配置存储（Windows DPAPI，参考 ai-studybuddy T08 配置中心 + pi-desktop credential-vault）。
- 日志脱敏：不记录请求正文、模型完整输出、base URL、key、完整 UUID；AI 日志字段 allowlist。
- 学生资料原文、考试名称、家长渠道地址默认敏感。
- 组件安全：zip 炸弹防护（条目/解压比限制）、MIME 严格匹配、不执行嵌入代码。

## 6. 组件治理与本项目关系

五阶段组件治理（docs/00 §四）是本项目所有组件的强制流程：
- ai-studybuddy 已验证组件（转换器、OCR、whisper.cpp 集成、报告生成）：以"迁移组件"身份仍需走单件测试（在新仓库环境验证 Node 24 + WPS COM + venv）。
- 新组件（WPS COM 桥、TTS、pi-desktop 桌面壳）：严格走五阶段。

## 7. 已定案决策（TRD 审查点 → 已定案）

> 2026-08-07 用户明确批准决策 1-5。依据：[docs/prep-参考点核对表.md](./prep-参考点核对表.md) 四参考仓库核对结论。决策 6 于 2026-08-07 追加（v0.1 交付形态），2026-08-08 v0.2.3 修订（打包能力常态化）。

| # | 决策项 | 定案 | 理由与依据 |
|---|---|---|---|
| 1 | WPS COM 桥 | **Python pywin32 子进程** | 复用 OCR venv 的 Python 运行时，零新依赖；pywin32 是 Windows COM 自动化成熟方案；与 whisper.cpp/OCR 统一 Python 技术栈；子进程隔离 WPS 崩溃不影响主进程。node COM interop（winax 等）维护差、Node 版本 ABI 易失效。核对表确认四参考仓库均无 WPS COM，需独立设计 |
| 2 | 桌面壳 | **取 pi-desktop 架构自建业务化壳** | 精确控制业务边界，五件架构骨架（contract 类型化 IPC + host-manager utilityProcess + credential-vault DPAPI + toolchain 发现-探测-安装-绝对路径 + file-watch）直接搬运改名；业务层（学科/学情/错题/学习计划）独立自建。Plugins 省略（不让学生接触 pi 插件机制），Skills 体系替换为"学习技能包"。Apache-2.0 允许 fork 但会携带通用 coding agent 会话/Skills.sh/微信渠道等无关功能与技术债 |
| 3 | 数据隔离 | **pi 会话目录 `~/.pi` 与业务数据根物理隔离** | pi 会话目录 `~/.pi` 由 pi 自管（auth.json/models.json/settings.json 在 `~/.pi/agent/`，pi-desktop session-reader 读此处），pi-studybuddy 不侵入。业务数据根 `%LOCALAPPDATA%\PiStudyBuddy` 存学期注册表/semester.db/家长报告/学情。密钥走 pi-desktop credential-vault（safeStorage/DPAPI），键名从 `channel:xxx` 改为 `modelProvider:xxx`/`parentContact:xxx` |
| 4 | TTS 引擎 | **SAPI 默认 + edge-tts 可选 skill** | Windows SAPI 系统自带零依赖、离线可用，符合单机桌面与零新依赖优先原则；edge-tts 音质好但需网络，封装为可选 skill 按需切换（progressive disclosure：description 常驻，正文按需加载）。核对表确认四参考仓库均无 TTS，需自建 |
| 5 | 文档语言 | **中文优先** | 与 ai-studybuddy 一致；学生用户母语中文；文档/错误信息/UI 全中文；代码标识符（变量/函数/类名）用英文，注释用中文 |
| 6 | v0.1 交付形态 | **源码形态可运行 + 打包能力常态化（supersedes v0.2.2 "不打包 .exe"）** | 用户 2026-08-08 明确指令："系统不管什么时候，只要功能正常，就要能够被打包"。v0.1 保持源码形态运行（pnpm dev）用于开发审计，**同时必须具备可打包为 x64 setup 安装包的能力**——每个功能完成后都应能产出可部署的安装包。打包工具链（electron-builder）纳入 M4 里程碑，实际打包动作按需执行。AGENTS.md §1.2 的"v0.1 禁用运行级使用"指 AI 运行级使用（verification_only/research_only），不阻止系统本身被打包部署 |

**定案影响**：以上六项不再作为"待决"项重新讨论，后续 02-PRD/03-Architecture/09-UI 设计必须以此为前提；如需变更须走显式变更评审流程。

## 8. 下一步

- 02-PRD：产品需求（业务闭环定义、使用者、家长报告边界、kaobuddy 基本面吸收结论）
- 03-Architecture：pi 扩展层 / 业务 Adapter / 数据层 / 技能体系设计（输入：[docs/prep-参考点核对表.md](./prep-参考点核对表.md) 跨仓库核对结论）
- 09-UI：使用者介面设计（基于 pi-desktop 架构自建业务化壳决策）

---

## 9. 版本历史

| 版本 | 日期 | 变更 |
| v0.2.4 | 2026-08-09 | 交叉审查修订：明确业务数据根 `config/models.json` 与 `config/credentials.json` 的配置边界；生产 agent session 必须使用受控模型配置，无配置时返回 `MODEL_NOT_CONFIGURED`，不得静默回退测试夹具。同步 02-PRD 对话默认主入口状态。 |
| v0.2.3 | 2026-08-08 | §7 决策 6 修订：v0.1 交付形态从"不打包 .exe"改为"源码形态可运行 + 打包能力常态化"。依据：用户 2026-08-08 明确指令"系统不管什么时候，只要功能正常，就要能够被打包"。AGENTS.md §1.2"禁用运行级使用"指 AI 运行级使用，不阻止系统打包部署。打包工具链（electron-builder）纳入 M4 里程碑。supersedes v0.2.2 决策 6 |
| v0.2.2 | 2026-08-07 | §7 加决策 6「v0.1 交付形态：源码形态（pnpm dev），不打包 .exe」——依据 AGENTS.md §1.2（v0.1 禁用运行级使用）+ §6.4（禁止提前设计 v0.2+ 产品化机制）；M0 完成后在 04-Todo §6.0 补版本演进说明（superseded by v0.2.3） |
| v0.2.1 | 2026-08-07 | §2.4 会话管理行补"对话默认主入口"语义——应用启动即打开"💬 对话"标签页承载 pi 原生 AI 对话（02-PRD §3.11 + 03-Architecture §6.7 + 09-UI §4.2 贯通） |
| v0.2.0 | 2026-08-07 | §7 五点待决项经用户明确批准定案（Python pywin32 / 自建壳 / 物理隔离 / SAPI 默认 / 中文优先）；新增 §9 版本历史；关联 docs/prep-参考点核对表.md 作为核对依据 |
| v0.1.0 | 2026-08-06 | 初始草案：技术底座、格式矩阵、系统形态、安全边界、待办决策 |

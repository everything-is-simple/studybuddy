# AI StudyBuddy 开源组件装配 SoT

**版本**：v1.7
**状态**：当前单机主路径已装配 SQLite、本地文件、RapidOCR、OpenAI-compatible Router、QQ SMTP/飞书和 Windows DPAPI 配置保护；重型历史组件仍不进入默认栈
**日期**：2026-07-18
**用途**：定义本项目如何优先使用成熟开源组件，如何在 `I:\ai-studybuddy-composer` 先调通，再封装 Adapter 接入主系统。

> 注：PostgreSQL、MinIO、Redis/BullMQ 已保留为 Phase 0.5 历史能力卡，不进入当前单机成品默认栈；Phase 0.7 以 SQLite、本地文件与 SQLite Job Worker 验证替代路径。

## 一、核心原则：先分解，再组合

AI StudyBuddy 的系统能力来自成熟组件的组合，而不是从零造轮子。

> 系统开发不是先写完整业务，再找组件；而是先把成熟开源组件一个个调通，再通过 Adapter 组合成系统能力。

开发顺序：

```text
成熟开源组件下载
  → composer 独立调试
  → smoke test 验证
  → 组件能力卡沉淀
  → 主系统 Adapter 封装
  → 接入 FormatConverter / Renderer / Worker / Provider
  → 学习闭环联调
```

硬规则：

- 不满足“开源、成熟、可下载、可本地调通、许可证可接受”的系统组件，不进入 MVP。
- AI Provider 不是开源组件，但也必须先在 composer 中用最小样例调通。
- 不得因为某功能重要就自己造轮子。
- 产品流程可以参考优秀开源项目；技术栈不强行搬运。
- `I:\ai-studybuddy-composer` 是独立本机试炼场；`I:\ai-studybuddy` 只接收经过文档门禁后重新实现的正式 Adapter 和业务编排。试炼场不得被主系统 import，也不得把样例代码直接复制进产品。

## 二、组件能力卡模板

每个候选组件必须形成能力卡。

| 字段              | 要求                                          |
| ----------------- | --------------------------------------------- |
| 组件名            | 例如 RapidOCR、SenseVoice、Markmap            |
| GitHub / 官网地址 | 必须可追溯                                    |
| License           | 必须确认许可证                                |
| 成熟度判断        | Stars、维护状态、社区使用度、文档质量         |
| 安装方式          | npm / pip / Docker / 二进制                   |
| 输入              | 文件、文本、URL、音频、图片等                 |
| 输出              | 纯文本、JSON、HTML、Markdown、音频轨等        |
| Composer 目录     | 该组件在 `I:\ai-studybuddy-composer` 下的位置 |
| Adapter 名称      | 主系统封装层名称                              |
| smoke test        | 最小可运行测试                                |
| MVP 状态          | 必接 / 后接 / 只参考                          |

## 三、成熟开源组件下载清单

| 系统能力                  | 成熟开源组件                                                                                                                | Composer 调试目录                                           | 接入方式                                                                                                                  | MVP 优先级     |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------- |
| 产品闭环参考              | [KaoBuddy](https://github.com/jin-zi-xuan/kaobuddy-pwa)                                                                     | `composer\reference\kaobuddy`                               | 参考资料导入、学习计划、模拟考、AI批改、错题本流程；不搬技术栈                                                            | 必参考         |
| 刷题/错题参考             | [MiaowTest](https://github.com/qijun1900/MiaowTest)                                                                         | `composer\reference\miaowtest`                              | 参考题库、练习记录、错题统计；不搬数据库/框架                                                                             | 必参考         |
| 轻量 MVP 参考             | [考试粥助手](https://github.com/zjuhechao/exam-porridge-assistant)                                                          | `composer\reference\exam-porridge`                          | 参考资料上传、AI笔记、练习、错题追踪                                                                                      | 必参考         |
| PDF 文本提取              | [PDF.js](https://github.com/mozilla/pdf.js) / [pdf-parse](https://www.npmjs.com/package/pdf-parse)                          | `composer\pdf`                                              | PDF → 文本，封装 `PdfConverter`                                                                                           | MVP 必接       |
| 图片 / 试卷 OCR           | [RapidOCR](https://github.com/RapidAI/RapidOCR)（首选）/ [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)（备选对比） | `composer\ocr\RapidOCR` / `composer\ocr\PaddleOCR`          | 图片 → 文本，封装 `OcrConverter`                                                                                          | MVP 必接       |
| DOCX 文本提取             | [Mammoth.js](https://github.com/mwilliamson/mammoth.js)                                                                     | `composer\converter\docx-test`                              | DOCX → HTML/纯文本，已封装 `DocxConverter`                                                                                | ✅ T04B 已装配 |
| PPTX 文字层提取           | [JSZip](https://github.com/Stuk/jszip) + OOXML XML 解析                                                                     | `composer\converter\pptx-test`                              | PPTX → 按页纯文本；已封装 `PptxConverter`，保留命名/十进制/十六进制 XML entity 解码验证事实                               | ✅ T04B 已装配 |
| 音频转文字                | [SenseVoice](https://github.com/FunAudioLLM/SenseVoice)                                                                     | `composer\asr\SenseVoice`                                   | 音频 → 文本，封装 `AudioConverter`                                                                                        | Phase 1.5      |
| ASR 备选                  | [FunASR](https://github.com/modelscope/FunASR)                                                                              | `composer\asr\FunASR`                                       | 更完整 ASR pipeline                                                                                                       | Phase 1.5      |
| 视频处理                  | [FFmpeg](https://ffmpeg.org/)                                                                                               | `composer\video\ffmpeg-test`                                | 视频 → 音轨 → ASR                                                                                                         | 后接           |
| 网页 / 本地 HTML 正文提取 | [Mozilla Readability](https://github.com/mozilla/readability) + jsdom + undici                                              | `composer\converter\url-fetch-test`                         | URL/本地 HTML → 正文文本；已封装 `UrlConverter` / `HtmlConverter`，保留回环 DNS 拒绝、错误 body 取消与 Agent 关闭验证事实 | ✅ T04B 已装配 |
| 思维导图渲染              | [Markmap](https://github.com/markmap/markmap)                                                                               | `composer\mindmap\markmap-test`                             | Markdown/层级结构 → 思维导图                                                                                              | MVP 必接       |
| 数学公式渲染              | [KaTeX](https://github.com/KaTeX/KaTeX)                                                                                     | `composer\markdown\katex-test`                              | Markdown 公式展示                                                                                                         | MVP 必接       |
| Markdown 渲染             | [react-markdown](https://github.com/remarkjs/react-markdown)                                                                | `composer\markdown\react-markdown-test`                     | 结构化笔记展示                                                                                                            | MVP 必接       |
| 持久化任务                | SQLite `jobs` 表 + 单进程 Worker                                                                                            | `I:\ai-studybuddy-composer\windows-native\03-job-worker`    | 格式转换 / AI / 报告 Job 串行执行                                                                                         | Phase 0.7 必接 |
| 本地文件                  | Node.js `fs` + 逻辑 `storage_key`                                                                                           | `I:\ai-studybuddy-composer\windows-native\02-local-storage` | 原始资料、导出和临时文件                                                                                                  | Phase 0.7 必接 |
| 数据库                    | [better-sqlite3](https://github.com/WiseLibs/better-sqlite3)                                                                | `I:\ai-studybuddy-composer\windows-native\01-sqlite`        | 单用户业务数据、任务、发送记录                                                                                            | Phase 0.7 必接 |
| 默认文本 AI               | GPT/Claude 中转（Pixel API）+ OpenAI SDK                                                                                    | `composer\ai-provider\gpt-test`；主仓库 `AiProviderRouter`  | T05 已以 OpenAI-compatible Provider 重新装配；按 priority fallback，测试通过注入 mock fetch，不依赖真实网络               | ✅ T05 已接入  |
| Windows 用户级秘密保护    | `@primno/dpapi` 2.0.1                                                                                                       | 主仓库 T08 Node 22 实机 roundtrip                           | `SecretProtector` 抽象 + `DpapiProtector`；仅保存加密 active/prev，不提供非 Windows 生产 fallback                         | ✅ T08 已接入  |
| 文本 AI 备选              | Kimi                                                                                                                        | `composer\ai-provider\kimi-test`                            | 文本理解、笔记整理、多模态；当前无 Key                                                                                    | 备选           |
| 文本 AI 备选              | Qwen                                                                                                                        | `composer\ai-provider\qwen-test`                            | 文本任务备选；Qwen-VL 只作多模态兜底                                                                                      | P1             |
| 复杂图片兜底              | Kimi 视觉 / Qwen-VL                                                                                                         | `composer\ai-provider\vision-fallback-test`                 | OCR/版面失败时兜底                                                                                                        | P2             |
| 最难推理兜底              | GPT/Claude 中转                                                                                                             | `composer\ai-provider\gpt-test`                             | 最难数学、证明、跨学科推理                                                                                                | P2/高级兜底    |

说明：Kimi / Qwen / GPT/Claude 是可替换 AI Provider，不属于“成熟开源组件下载清单”的开源组件范畴；它们出现在本表中，只表示也要先做最小接入验证。

T05 正式接入边界：主仓库不复制 composer 样例；使用 `openai` SDK 封装 `OpenAiProvider`，通过 `AiProviderRouter` 按 `AI_PROVIDERS` 的 `priority` 轮询。`AI_PROVIDERS` 为空时才兼容单 Provider 变量；Provider 未配置与全部失败分别返回稳定错误码，真实模型连通性仍由本机 `.env.local` smoke test 另行确认。

## 四、产品流程参考边界

### 4.1 KaoBuddy

参考：资料导入、知识点拆分、学习计划、模拟考、AI 批改、错题本闭环。

不搬：PWA / FastAPI 技术栈、原数据库结构、原 UI 细节。

### 4.2 MiaowTest

参考：题库组织、练习记录、错题统计、刷题体验。

不搬：原框架、原数据模型、与本项目家长面板冲突的产品逻辑。

### 4.3 考试粥助手

参考：轻量学习闭环、最小资料上传、AI 笔记和练习的 MVP 思路。

## 五、两层架构边界

### 5.1 格式转换层：成熟开源组件，不走 LLM

| 输入              | 组件                                    | 输出     |
| ----------------- | --------------------------------------- | -------- |
| PDF               | PDF.js / pdf-parse                      | 纯文本   |
| 图片 / 试卷       | RapidOCR（首选）/ PaddleOCR（备选对比） | OCR 文本 |
| 音频              | SenseVoice / FunASR                     | 转写文本 |
| 视频              | FFmpeg → ASR                            | 转写文本 |
| 网页链接          | Mozilla Readability + jsdom             | 正文文本 |
| Markdown / 纯文本 | TextConverter                           | 原文入库 |

### 5.2 LLM 理解层：只吃纯文本

| 任务                             | 默认 Provider       | 兑底策略                                           |
| -------------------------------- | ------------------- | -------------------------------------------------- |
| 结构化笔记 + 重点 + 思维导图数据 | GPT/Claude 中转     | Kimi/Qwen 备选；全部失败则保留待处理文本           |
| 教学解析步骤 / 解题路径          | GPT/Claude 中转     | Kimi/Qwen 备选；只给教学步骤，不暴露思维链         |
| 出题 / 变题                      | GPT/Claude 中转     | Kimi/Qwen 备选；失败不阻塞既有练习                 |
| 主观题评分 / 错因分类            | GPT/Claude 中转     | Kimi/Qwen 备选；进入分级质量门，不作单方面最终裁决 |
| OCR/版面失败兜底                 | Kimi 视觉 / Qwen-VL | 仅在开源 OCR 失败后使用；最终允许孩子手工校正      |

### 5.3 规则引擎层：不走 LLM

- 选择题 / 填空题精确批改；
- 艾宾浩斯排程；
- 超时任务检测；
- 考前提醒；
- 工作量累计；
- 家长时间线聚合。

## 六、接入验收标准

一个组件正式进入主系统前必须满足：

1. `COMPOSER_ROOT` 独立调通；
2. 形成组件能力卡；
3. 有最小 smoke test（见下方标准表）；
4. Adapter 输出结构稳定；
5. 日志写入 `LOG_ROOT`；
6. 临时文件写入 `TMP_ROOT`；
7. 运行数据不污染主 repo；
8. 许可证和部署方式可接受。

## 七、Smoke Test 标准表

以下是每个 MVP 必接组件的 smoke test 具体要求。"通过"不是模糊感觉，而是可验证的检查项。

| 组件                       | Smoke Test 操作                                   | 通过标准                                                                            | 失败处理                                           |
| -------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------- |
| **pdf-parse / PDF.js**     | 解析 1 个含中文的真实 PDF（至少 3 页）            | 文本完整提取、无乱码、中文字符正确、页码能区分                                      | 换备选组件或检查编码                               |
| **RapidOCR / PaddleOCR**   | 识别 1 张含中文文字的试卷图片                     | 能识别主要题干/标题；记录单页耗时、中文字符数和人工抽检误字；PaddleOCR 只作备选对比 | 调整模型版本、预处理或转入 LLM 视觉兜底            |
| **Markmap**                | 渲染 1 份 3 级层级的 Markdown 文本                | 浏览器可正常展示导图；节点可展开/收起；不报错                                       | 检查 Markdown 格式或 Markmap 版本                  |
| **react-markdown + KaTeX** | 渲染含行内公式 `$E=mc^2$` 和块级公式的 Markdown   | 公式美观渲染、不显示原始 LaTeX 源码、无 JS 报错                                     | 检查 KaTeX 插件配置                                |
| **BullMQ + Redis**         | 创建队列 → 入队 1 个 Job → 消费 → 模拟失败 → 重试 | Job 经历 waiting→active→completed 全生命周期；失败 Job 重试成功                     | 检查 Redis 连接和队列配置                          |
| **MinIO**                  | 上传 1 个文件 → 下载 → 生成临时 URL → URL 可访问  | 上传/下载内容一致；临时 URL 在有效期内可访问、过期后不可访问                        | 检查 Bucket 策略和端口                             |
| **PostgreSQL + pgvector**  | 建表 → 插入 → 查询 → 创建向量列 → 向量相似度搜索  | CRUD 正常；pgvector 扩展加载成功；向量搜索返回结果                                  | 检查扩展安装和 SQL 语法                            |
| **GPT/Claude 中转 API**    | 发送 1 段 500 字中文纯文本，要求返回结构化笔记    | API 调通；返回 Markdown 格式可解析；latency < 30s；token 消耗合理                   | 检查 API Key、Base URL、余额和模型权限；记录错误码 |
| **Kimi API**               | 同中转 API smoke test                             | 同上                                                                                | 检查 API Key 和网络；记录错误码                    |
| **Qwen API**（P1 备选）    | 同 Kimi smoke test                                | 同上                                                                                | 同上                                               |

### Smoke Test 执行规范

1. **测试文件位置**：每个组件的 smoke test 脚本放在 `composer\<组件目录>\smoke-test\` 下；
2. **测试数据**：使用真实的中文样本（教材截取或公开试卷），不用英文 lorem ipsum；
3. **结果记录**：通过后在能力卡中标注日期和版本；
4. **失败不阻塞其他组件**：某组件失败时，其他组件可继续，但该组件不得进入主系统；
5. **二次验证**：组件升级版本后，必须重新跑 smoke test。

### Smoke Test 状态追踪

| 组件                              | 状态    | 通过日期   | 版本                                                      | 备注                                                                                                                                            |
| --------------------------------- | ------- | ---------- | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| pdf-parse                         | ✅ 已测 | 2026-07-09 | 2.4.5                                                     | 文字型中文 PDF 通过：7 页、5155 字符、2422 个中文字符；扫描版 `电工考点.pdf` 需走 OCR                                                           |
| RapidOCR                          | ✅ 已测 | 2026-07-09 | rapidocr-onnxruntime 1.4.4                                | 22 张繁体书页批量通过；平均 1.94s/页；中文字符 3009；存在误字，需人工/LLM 清洗                                                                  |
| PaddleOCR                         | ⏳ 待测 | —          | —                                                         | —                                                                                                                                               |
| Markmap                           | ✅ 已测 | 2026-07-09 | 0.18.12                                                   | Node 脚本通过；Chrome 浏览器二次验证通过                                                                                                        |
| react-markdown + KaTeX            | ✅ 已测 | 2026-07-09 | KaTeX CDN 0.16.9                                          | Chrome 浏览器验证通过：5 个公式、中文、代码块均正常                                                                                             |
| BullMQ + Redis                    | ✅ 已测 | 2026-07-09 | BullMQ 5.79.3 / Redis 7.4.9                               | 失败重试 + completed 生命周期通过；Docker Hub token EOF 时使用 daocloud 镜像代理                                                                |
| MinIO                             | ✅ 已测 | 2026-07-09 | MinIO RELEASE.2025-09-07 / SDK 8.0.7                      | 上传/下载一致、presigned URL、对象删除、控制台登录通过；Docker Hub TLS 超时后使用 daocloud 镜像代理                                             |
| PostgreSQL + pgvector             | ✅ 已测 | 2026-07-09 | PostgreSQL 16.14 / pgvector 0.8.5                         | CRUD、向量搜索、IVFFlat 索引通过；测试后已清理容器                                                                                              |
| GPT/Claude 中转 API               | ✅ 已测 | 2026-07-09 | Pixel API / gpt-5.5 / Responses API                       | `gpt-test` 通过：11.9s，总 tokens 988，Markdown、中文、思维导图 JSON 均通过；最初 401 为 `.env.local` 手填 Key 与 cc-switch provider key 不一致 |
| Mammoth.js / DOCX                 | ✅ 已测 | 2026-07-11 | mammoth 1.12.0 / jszip 3.10.1 / jsdom 26.1.0              | `docx-test` 通过：中文正文、视觉占位、空文档错误；能力卡已填                                                                                    |
| JSZip / PPTX 文字层               | ✅ 已测 | 2026-07-11 | jszip 3.10.1                                              | `pptx-test` 通过：数字页序、图片 OCR 提示、纯图片成功、损坏容器失败；能力卡已填                                                                 |
| undici + Readability / URL + HTML | ✅ 已测 | 2026-07-11 | undici 7.28.0 / jsdom 26.1.0 / @mozilla/readability 0.6.0 | `url-fetch-test` 通过：SSRF 全阻断、5 MB/3 跳/10 秒限制、本地 HTML 清理、真实 URL 首次成功；能力卡已填                                          |
| Kimi API                          | ⏳ 待测 | —          | —                                                         | 当前无 Key                                                                                                                                      |
| Qwen API                          | ⏳ 待测 | —          | —                                                         | —                                                                                                                                               |

---

## 八、七子系统底座选型（2026-07-08 调研补充）

**来源**：两轮深度调研（对抗式验证）+ Phase 0.5 本机 smoke test。**目标**：每个子系统尽量套成熟开源底座，避免从零自建。**结论前提**：AI 走云 API，不在本地跑大模型；当前默认是 Pixel API 中转 GPT/Claude，Kimi/Qwen 只保留后续备选配置位。

### 8.1 整体判断：分子系统各取所长，不套单一 LMS

不存在与本项目栈（TypeScript/Node + Windows 本机 SQLite/本地文件）契合的单一整体教育平台底座：

- Frappe LMS：Python 全栈 + Vue，默认 MariaDB，Postgres 为二等支持、无原生 pgvector，且 **AGPL-3.0**（网络托管触发源码披露义务）。
- Open edX：Python + Django + React，机构级重量平台。

两者都只能作为独立 Python 外部服务运行。**采用「分子系统各取所长 + 自建薄胶水层」，不套整平台。**

### 8.2 各子系统底座

以下带链接项均经三票对抗式验证确认。

| 子系统          | 推荐底座                                                                                                                                                                                                   | License / 栈契合                                                  | 覆盖范围 · 需自建                                                                                                                                                                                                                         |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **S1 学习节奏** | [frappe-gantt](https://github.com/frappe/gantt) + [react-big-calendar](https://github.com/jquense/react-big-calendar)；复杂甘特可选 [DHTMLX Gantt](https://github.com/DHTMLX/gantt)                        | 全 **MIT**，React/JS 库可嵌入 ✅                                  | 覆盖时间线/日历/甘特渲染。自建：课程/任务数据模型、工作量聚合（甘特无原生工作量视图）、逾期提醒（SQLite Job Worker + Windows 调度）。**DHTMLX 仅 v10+ Community 版为 MIT，须锁版本，v9 及更早为 GPLv2**                                   |
| **S2 资料笔记** | [markmap](https://github.com/markmap/markmap)（导图）+ 既有 pdf-parse/RapidOCR/react-markdown/KaTeX；检索可参考 [Quivr](https://github.com/quivrhq/quivr)(Apache-2.0,原生 pgvector)                        | markmap **MIT**，JS/TS 原生 ✅                                    | 覆盖导图渲染与格式转换。自建：上传→转文本→喂中转 GPT/Claude→存 markdown/导图数据 的编排线                                                                                                                                                 |
| **S3 限时练习** | 自建最小题型（单选/多选、填空、简答）为 MVP 主路径；[@lumieducation/h5p-server](https://github.com/Lumieducation/H5P-Nodejs-library) 只作为后续 `H5PContentAdapter`                                        | H5P 为纯 TypeScript、npm 可嵌入，但内容模型和接入成本不应阻塞 MVP | MVP 先以稳定的数据模型和规则批改实现三种题型；主观题进入 AI 质量门，限时与作答记录自建。后续需要互操作内容或更多交互题型时，再以 Adapter 接入 H5P 渲染/导入；Moodle 题引擎(PHP 耦合)/E-Quiz(需 K8s)/obsidian 插件(绑 Obsidian) 均不宜嵌入 |
| **S4 错题改错** | [ts-fsrs](https://github.com/open-spaced-repetition/ts-fsrs)（~704★，FSRS-v6）                                                                                                                             | **MIT**，同栈原生 TS 库 ✅ 最契合                                 | 覆盖艾宾浩斯间隔复习调度引擎（喂评分→返回下次复习时间）。自建：错题本模型、错因分类、变题重做、录入 UI、卡片状态持久化到 SQLite                                                                                                           |
| **S5 期末冲刺** | ⚠️ **组卷算法无可复用 TS/Node 底座，需自研**                                                                                                                                                               | —                                                                 | 自建：按知识点/难度加权抽样组卷（TS 实现，不复杂）。真题解析/变题走 Kimi。限时模拟考复用 S3 的 H5P。（RecruitSystem 用遗传算法组卷但为 Java SSM 整站，不可复用）                                                                          |
| **S6 家长观察** | `nodemailer` + QQ SMTP、飞书自定义机器人 Webhook                                                                                                                                                           | Node 出站发送，无需公网入口                                       | 规则统计生成 HTML 报告与卡片；AI 仅可选润色；不做家长 Web 面板或远程登录                                                                                                                                                                  |
| **S7 课堂采集** | [FunASR](https://github.com/modelscope/FunASR) 或 [SenseVoice.cpp](https://github.com/lovemefan/SenseVoice.cpp)（CPU）；省心可用 [Scriberr](https://github.com/rishikanthc/Scriberr)(MIT) 独立服务或云 ASR | 中文优先；见 9.2 硬件注意                                         | 覆盖课堂转写。自建：说话人登记/命名（ASR 只给匿名 spk0/spk1）。**SenseVoice.cpp 无 Windows 预编译二进制，须自编译**                                                                                                                       |

### 8.3 S6 家长报告选型决策

**决策：不做家长 Web 看板；使用 QQ SMTP 邮件 + 飞书 Webhook 发送脱敏结构化报告。**

理由：Apache Superset 官方基线即需 8GB 内存（占单机 32GB 的 1/4）；Metabase 为 JVM、同样吃内存且 **AGPL-3.0** 对「未来半公开」有 copyleft 暴露；Chartbrew v4+ 为 FSL-1.1-MIT（非 OSI 开源，禁商业 SaaS 再分发）。家长当前需要的是知道学习节奏、完成情况和考前节点，而不是远程登录孩子电脑。邮件和飞书均由孩子电脑主动出站发送，不需要公网入口、隧道、域名或额外鉴权面；正式报告采用规则统计，AI 仅可选润色且失败不阻塞发送。

### 8.4 偷懒优先级（结合硬件修订版）

| 档位                        | 子系统 → 底座                                                                 | 自研量 |
| --------------------------- | ----------------------------------------------------------------------------- | ------ |
| **第一档 直接套库**         | S4→ts-fsrs；S1→frappe-gantt+react-big-calendar；S3 的 H5P 仅后续 Adapter 候选 | 极少   |
| **第二档 套组件配薄胶水**   | S2→markmap+OCR+PDF.js+react-markdown/KaTeX；S6→邮件 HTML + 飞书卡片           | 编排线 |
| **第三档 主要自研（但薄）** | S5→组卷算法自研+Kimi 解析；S7→本地 ASR 自编译或用云/独立服务                  | 较多   |

---

## 九、当前默认栈与历史验证的边界

### 9.1 当前单机成品默认栈

| 能力 | 当前默认                              | 原因                                          |
| ---- | ------------------------------------- | --------------------------------------------- |
| 运行 | Windows 11 + Express localhost        | 孩子本机按需启动，无 Docker/WSL2 常驻         |
| 数据 | SQLite WAL + `better-sqlite3`         | 单用户、单文件、低内存、可备份                |
| 文件 | 本地目录 + 逻辑 `storage_key`         | 不需 MinIO、对象存储或预签名 URL              |
| 任务 | SQLite `jobs` + 单进程串行 Worker     | 持久化、有限重试、重启恢复，不需 Redis        |
| OCR  | RapidOCR Python 子进程                | 用完退出，不常驻                              |
| 报告 | QQ SMTP + 飞书 Webhook                | 孩子电脑主动出站，无公网入口                  |
| 调度 | Windows Task Scheduler                | 22:30 独立执行 `report.js`                    |
| 配置 | Windows DPAPI + 加密 JSON active/prev | 密钥绑定当前 Windows 用户；浏览器只见脱敏状态 |

### 9.2 Phase 0.5 历史组件能力

PostgreSQL/pgvector、MinIO、Redis/BullMQ、Docker Desktop/WSL2 的 smoke test 结论仍有效，适用于未来多用户、云端或更重的部署形态；它们不构成孩子 16GB Windows 本机版的默认依赖，也不得在 Phase 0.8 中无重新决策地带回主路径。

### 9.3 试炼场到产品的唯一通道

```text
I:\ai-studybuddy-composer 的最小样例
  → 可重复 smoke test + COMPONENT-CARD
  → 04 记录任务状态 + 09 记录验收结果
  → 08 定义 Adapter 与安全边界
  → Phase 0.8 在 I:\ai-studybuddy\packages 重新实现
```

`.env.local`、`.venv`、`node_modules`、output、真实凭据和真实学习材料只留在本机试炼场或 `APP_DATA_ROOT`；不进入主仓库 Git。T04A 的审查修复同样只留在 composer：主仓库只登记计划、能力结论与验收证据，T04B 必须独立实现 Adapter 和正式测试。任何一环缺失，组件不得视为可接入产品。

---

### 9.3A S7-MVP 外置 whisper.cpp 引用边界（2026-07-25，已完成主线复验并推送 `origin/master`）

S7-MVP 只允许通过 `LOCAL_ASR_WHISPER_CLI_PATH`、`LOCAL_ASR_WHISPER_MODEL_PATH`、超时和大小限制等显式环境变量引用开发机已核验的外置 `whisper.cpp` 候选；主仓库不复制 CLI、DLL、模型、样例、harness 或证据。产品 Adapter 必须重新以真实 SQLite/API/前端闭环验证 WAV 输入、进程超时、临时文件清理、编辑后 S2 handoff 和无进程残留。候选级 `PARTIAL`、全零 PCM harness 前置判定和任何 G2 记录均不能被表述为完整 S7、通用静音或用户机能力。

### 9.4 当前单机主路径的分级 fallback

| 能力              | 主路径                 | 自动降级                                          | 最终人工出口                                       |
| ----------------- | ---------------------- | ------------------------------------------------- | -------------------------------------------------- |
| PDF / 文本        | `pdf-parse`            | PDF.js / 页面渲染 → OCR → 视觉 Provider           | 孩子粘贴或修正文本                                 |
| 图片 OCR          | RapidOCR               | 图像预处理重试 → PaddleOCR / 视觉 Provider        | 孩子校正识别结果                                   |
| AI 笔记、练习质量 | GPT/Claude 中转        | Kimi / Qwen 官方直连 → `pending_quality_check`    | 孩子核对、保存覆盖理由；不因 Provider 故障锁死学习 |
| 家长报告          | QQ SMTP + 飞书 Webhook | 仅重试失败渠道；下次登录补发                      | 保存本地 HTML 与错误摘要，维护者手工重发           |
| 单学期数据库      | SQLite WAL + 备份      | 停止该学期写入 → `integrity_check` → 最近备份恢复 | 维护者按恢复记录处理；其他学期保持可用             |

Fallback 是产品能力的一部分：组件或 Provider 失败时，必须保留输入、错误摘要和下一步，而不是静默丢失资料或把技术故障标为孩子未完成。

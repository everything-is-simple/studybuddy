# 06 API 契约
**版本**：v0.1.10
**日期**：2026-08-15
**状态**：✅ 已审查批准；T-M5-011 执行中。T-M5-010 已完成 Git 收口。

> API 方法存在、contract coverage 通过或 Job 被登记，不等于用户动作完成；当前契约按开发机真实主路径逐条复跑，问题总账见 [系统集成/02](./系统集成/02-系统问题总账与整改清单.md)。
**上游**：[02-PRD v0.1.4 §5](./02-PRD-产品需求-Product-Requirements.md)、[03-Architecture v0.1.3 §3/§6](./03-架构设计-Architecture-Design.md)、[05-ERD v0.1.2](./05-数据模型-ERD-Data-Model.md)
**下游**：07-Workflow、08-Test、09-UI
**架构依据**：pi-desktop contract 类型化 IPC + 自研 MessagePort RPC（非 HTTP REST）

---

## 1. API 总览

### 1.1 架构定位

pi-studybuddy 是**桌面应用**，不是 Web 服务。API 是 **renderer↔main↔agent-host 的 MessagePort RPC 契约**（借鉴 pi-desktop `contract/api.ts`），非 HTTP REST。

```
renderer (React)  ←PiBridge→  main (Electron)  ←RPC→  agent-host (utilityProcess)
     │                              │                          │
     └ contextBridge 受控桥接       └ MessageChannelMain        └ createRpcServer()
                                                                   │
                                                                   ├ pi 扩展层（registerTool 工具）
                                                                   └ 业务 Adapter
```

### 1.2 RPC 层（借鉴 pi-desktop，03-Architecture §6.3）

**五种 wire 消息**：`request` / `response` / `subscribe` / `unsubscribe` / `event`

**API**：
- `createRpcServer()` 在 agent-host 内 `attachPort(MessagePort)`
- `createRpcClient(port)` 在 renderer 提供 `call(method, ...args)` 和 `subscribe(topic, key, on)`
- `AnyMessagePort` 兼容 DOM MessagePort / utilityProcess / Node worker_threads

### 1.3 绑定与安全

- **仅 127.0.0.1**：无公网入口；loopback Origin 策略
- **sandbox:true + 严格 CSP**：renderer 沙箱化
- **preload 受控桥接**：仅 `contextBridge.exposeInMainWorld("piBridge", bridge)`，PiBridge 白名单接口
- **Host RPC 契约化**：`contract/{api,rpc}.ts` 类型约束

### 1.4 双层 API 体系

| 层 | 调用者 | 入口 | 用途 |
|---|---|---|---|
| **RPC 方法**（本文件主体） | renderer UI | `contract/api.ts` 的 `interface Api` | 学生操作（上传/练习/查看等） |
| **registerTool 工具** | AI agent | `pi.registerTool(tool)` | AI 受约束调用业务能力（03-Architecture §3） |

> 两者关系：部分 RPC 方法内部调用 registerTool 工具（如 `practice.submit` 调用 `studybuddy_submit_practice`）；部分是纯 UI 操作（如 `files.list`）。

---

## 2. API 信封规范

### 2.1 统一信封（02-PRD §5.4）

```typescript
// 成功
{
  success: true,
  data: T,
  meta?: {                          // 可选元信息
    total?: number,                  // 分页总数
    page?: number,
    pageSize?: number,
    timestamp: string               // ISO 8601 UTC
  }
}

// 失败
{
  success: false,
  error: {
    code: ErrorCode,                // 错误码枚举（见 §2.2）
    message: string                 // 中文可操作消息（永不暴露内部错误栈）
  }
}
```

### 2.2 统一错误码（6 个，02-PRD §5.4）

| 错误码 | HTTP 类比 | 含义 | 中文消息示例 |
|---|---|---|---|
| `NOT_FOUND` | 404 | 资源不存在 | "未找到该课程，请检查是否已删除" |
| `INVALID_JSON` | 400 | 请求体 JSON 格式错误 | "请求数据格式错误，请刷新后重试" |
| `FILE_TOO_LARGE` | 413 | 文件超过大小限制 | "文件过大，请压缩或分段上传" |
| `BAD_REQUEST` | 400 | 业务校验失败（状态机/权限/约束） | "该考试未确认，无法生成模拟卷" |
| `INTERNAL_ERROR` | 500 | 内部错误（脱敏后返回） | "操作失败，请稍后重试；如持续发生请重启应用" |
| `MODEL_NOT_CONFIGURED` | 400 | 生产 agent session 没有完整的业务模型配置或可用凭证 | "尚未配置可用 AI 模型，请先在设置中完成模型配置" |

**特殊错误码**（非通用，特定场景）：
- `PARENT_REPORT_PRIVACY_VIOLATION`（500）：UUID 泄漏检测失败（02-PRD §5.2）
- `MODEL_NOT_CONFIGURED`（400）：模型未配置或无法由受控运行时解析；生产路径不得静默回退测试夹具。

**错误码格式约束**：`errorCode` 必须匹配 `^[A-Z][A-Z0-9_]{1,63}$`（02-PRD §5.3）

### 2.3 中文可操作消息原则

- 永不暴露：内部错误栈、SQL 语句、文件路径、完整 UUID、API Key
- 面向学生：中文、可操作、告诉学生"怎么办"
- 失败可重试：提示重试方式
- 失败不可重试：提示具体操作（如"重启应用"/"检查文件格式"）

---

## 3. RPC 方法表（contract/api.ts 的 interface Api）

> 借鉴 pi-desktop `contract/api.ts`（~50 方法），pi-studybuddy 业务化扩展。方法名采用 `namespace.action` 风格。

### 3.1 会话管理（sessions.*，借鉴 pi-desktop）

> **对话 Tab 承载**（02-PRD §3.11 + 03-Architecture §6.7 + 09-UI §4.2）：sessions.* 是"💬 对话"标签页（默认主入口）的会话管理基础——应用启动即默认打开对话 Tab，左侧栏 SessionSidebar 选中会话，主内容区加载该会话；流式回复走 `Streams["agent.events"]`（见 §4），AI 自主调用 registerTool 工具的过程通过工具调用视图展示。**会话即对话 Tab 的内容**，是 pi 原生 AI 对话能力的承载层，不废弃、不降级。

| 方法 | 参数 | 返回 | 说明 |
|---|---|---|---|
| `sessions.list` | `{ limit?: number, cursor?: string }` | `SessionSummary[]` + meta | 按 dev+ino+birthtimeMs 哈希分页防陈旧 |
| `sessions.get` | `{ id: string }` | `Session` | 含上下文 |
| `sessions.context` | `{ id: string }` | `SessionContext` | 上下文压缩状态 |
| `sessions.rename` | `{ id: string, name: string }` | `Session` | 重命名 |
| `sessions.delete` | `{ id: string }` | `void` | 删除 |
| `sessions.export` | `{ id: string, format: 'md'\|'json' }` | `{ path: string }` | 导出 |
| `sessions.search` | `{ query: string }` | `SessionSummary[]` | 模糊搜索 |

> **sessions.search（T-M3-003 落地）**：L3 会话检索（05-ERD §4.3，conversation.sqlite bigram OR-combined MATCH）——query 经 bigram 分词 → chunks_fts MATCH → 按 session_id 聚合，映射内存仓库 SessionSummary（缺失时用检索库内容生成摘要条目）。检索库未建立时返回空数组（不阻塞）。sessions.rename/export 契约已定义，handler 归 T-M3-006 会话管理 UI。
>
> **SessionSummary 扩展（T-M3-003）**：增加可选学习场景元数据字段 `subject?`（学科标签）/ `goal?`（学习目标）/ `mistakeIds?`（关联错题 ID 列表），对齐 09-UI §4.2 头部语义（📐 学科 \| 目标：… \| 关联错题：#…）。会话级元数据写回走 agent.send 参数携带（不新增契约方法）。
>
> **agent.send（T-M3-001 新增）**：对话发送通道——renderer 发送用户消息 → agent-host 触发 `Streams["agent.events"]` 受控序列（message_start → token×N → context_compressed）。T-M3-001 范围为**受控夹具发射**（08-Test §5.4 不连真实 LLM，事件 payload 不携带完整 UUID/密钥）。
>
> **agent.send（T-M3-002 扩展）**：受控序列扩展 tool_call/tool_result 事件对（输入含触发词「出题/笔记/朗读」→ 模拟 studybuddy_* 工具调用，工具调用透明 09-UI §4.2）；事件 payload 结构化（见 §4 AgentEvent payload 说明）。
>
> **agent.send（T-M3-003 扩展）**：参数新增可选 `sessionMeta { subject?, goal?, mistakeIds? }`（09-UI §4.2 学习场景业务化）——受控序列在 message_start 后同步注入 `[学习上下文]` token（学科/目标/错题段，保持序列确定性），并写回会话元数据到内存仓库（sessions.get 可见）。
>
> **agent.send（T-M4-023 修订）**：生产环境只能使用 `<dataRoot>/config/models.json` 与 credential-vault 解密凭证构造的 pi `ModelRuntime` session；未配置、凭证不可读或模型无法解析时返回 `MODEL_NOT_CONFIGURED`。`runMockFixture` 仅可由 VITEST 显式注入，不能作为生产 fallback。

### 3.2 文件体验（files.*，借鉴 pi-desktop）

| 方法 | 参数 | 返回 | 说明 |
|---|---|---|---|
| `files.selectDirectory` | `{}` | `{ path: string }` | 仅桌面 PiBridge 可调用；agent-host 直接调用显式返回 BAD_REQUEST |
| `files.list` | `{ dir: string }` | `FileEntry[]` | 受 allowed-roots 校验的 lazy 加载 |
| `files.read` | `{ path: string }` | `{ content: string, encoding: string }` | 受 allowed-roots 校验（T-M3-002 实现：白名单门禁 + 相对 storageKey 解析 + 1MB 截断） |
| `files.previewMarkdown` | `{ path: string }` | `{ html: string }` | 当前安全转义的文本预览；富 Markdown/KaTeX/Mermaid 渲染待对应 UI 任务 |
| `files.previewDocx` | `{ path: string }` | `{ html: string }` | 未配置 DOCX 预览组件时显式返回 BAD_REQUEST |
| `files.watch` | `{ path: string }` | `subscribe` | fs.watch recursive，100ms 防抖→Streams["files.changed"] |
| `files.unwatch` | `{ path: string }` | `void` | 取消监听 |

> **§3.2 落地注解（T-M3-002）**：`files.read` 已由 T-M3-002 实现——路径必须经 allowed-roots 白名单校验（AGENTS.md §9.4 符号链接逃逸防护，realpath 归一化），相对路径（materials.storageKey）先相对业务数据根解析，内容 ≤1MB 截断；越权路径 → BAD_REQUEST（不泄漏真实路径细节），不存在 → NOT_FOUND。

### 3.3 S1 学习节奏

#### 学期管理（semesters.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `semesters.list` | `{ status?: string }` | `Semester[]` | 按状态过滤 |
| `semesters.create` | `{ label, startDate, endDate, timezone }` | `Semester` | 初始化学期库（db_relative_path） |
| `semesters.get` | `{ id }` | `Semester` | |
| `semesters.update` | `{ id, ...fields }` | `Semester` | |
| `semesters.transition` | `{ id, status }` | `Semester` | 状态机 active→teaching_ended→follow_up→archived；归档前后强制触发完整备份 |
| `semesters.archive` | `{ id }` | `Semester` | 归档，只读，留审计痕迹 |

#### 课程管理（courses.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `courses.list` | `{ semesterId }` | `CourseInstance[]` | |
| `courses.create` | `{ semesterId, courseName, subject, ... }` | `CourseInstance` | |
| `courses.get` | `{ id }` | `CourseInstance` | |
| `courses.update` | `{ id, ...fields }` | `CourseInstance` | |
| `courses.importSchedule` | `{ courseId, imageFile }` | `{ preview: SchedulePreview }` | OCR 识别预览，学生确认后原子化建条目 |

#### 考试管理（exams.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `exams.list` | `{ courseId?, confirmationStatus? }` | `AssessmentAttempt[]` | |
| `exams.add` | `{ courseId, examName, examType, scheduledDate, source, confidence? }` | `AssessmentAttempt` | confirmation_status=pending |
| `exams.confirm` | `{ id, confirmed: boolean }` | `AssessmentAttempt` | 写 confirmation_status/confirmed_at；未确认不驱动冲刺 |
| `exams.supersede` | `{ id, newAttemptId }` | `AssessmentAttempt` | superseded 状态 |

#### 课表（schedule.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `schedule.list` | `{ courseId }` | `ScheduleEntry[]` | |
| `schedule.create` | `{ courseId, weekday, startTime, endTime, location? }` | `ScheduleEntry` | CHECK end_time > start_time |
| `schedule.update` | `{ id, ...fields }` | `ScheduleEntry` | |
| `schedule.delete` | `{ id }` | `void` | 软删除 |

#### 任务与每日首页（tasks.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `tasks.list` | `{ courseId?, status?, dueBefore? }` | `StudyTask[]` | |
| `tasks.create` | `{ courseId, title, taskType, dueDate?, priority? }` | `StudyTask` | source_system |
| `tasks.complete` | `{ id }` | `StudyTask` | 写 StudyEvent（source_system='S1'） |
| `tasks.dailyBrief` | `{ semesterId }` | `DailyBrief` | 规则聚合（非 AI），少量待闭合项 |

#### 学习事件（events.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `events.list` | `{ semesterId?, courseId?, eventType?, since? }` | `StudyEvent[]` | 时间线 |
| `events.markReviewed` | `{ refType, refId }` | `StudyEvent` | TTS 朗读标记"已复习"→practice_reviewed 事件 |

### 3.4 S2 资料笔记

#### 资料管理（materials.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `materials.list` | `{ courseId?, status? }` | `Material[]` | |
| `materials.upload` | `{ courseId, file: FileMeta }` | `Material` | 生产 S2 renderer 必须提供 main 签发的一次性 `file.importToken`；host 消费 capability、校验普通文件、按源文件 stat 写入真实大小，并原子复制到 `<dataRoot>/<storageKey>` 后再写 Material；归档学期拒绝写入；storage_key 仍拒绝 `..`/`:\`/`:/`，MIME 服务端验证；不把源文件绝对路径交给 agent-host |
| `materials.get` | `{ id }` | `Material` | |
| `materials.convert` | `{ id }` | `Job` | 触发转换 Job（PDF/OCR/DOCX/PPTX 各有超时） |
| `materials.retryConversion` | `{ id }` | `Job` | 最多 3 次 |
| `materials.replaceText` | `{ id, text }` | `Material` | 手动粘贴纯文本跳过转换 |
| `materials.generateNote` | `{ id }` | `Job` | AI 笔记生成 Job |
| `materials.retryAiGeneration` | `{ id }` | `Job` | 最多 3 次 |
| `materials.delete` | `{ id }` | `void` | 软删除 |

#### 笔记（notes.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `notes.get` | `{ materialId }` | `StructuredNote` | 含 Markdown + highlights |
| `notes.update` | `{ materialId, noteMarkdown, highlights? }` | `StructuredNote` | 学生手动编辑 |
| `notes.getMindMap` | `{ materialId }` | `MindMap` | Markmap JSON |

#### 知识模块（modules.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `modules.list` | `{ courseId?, learnStatus? }` | `KnowledgeModule[]` | |
| `modules.create` | `{ courseId, materialId, moduleName, summary?, importance?, difficulty? }` | `KnowledgeModule` | 用户在 NotesTab 对已显式选择资料创建模块；校验课程与资料归属，写入 `source_evidence_json`，`ai_generated=0`；归档学期拒绝 |
| `modules.get` | `{ id }` | `KnowledgeModule` | 含 source_evidence 回链 |
| `modules.updateLearnStatus` | `{ id, learnStatus }` | `KnowledgeModule` | 状态机 not_started→learning→mastered→needs_review |

#### 作业（jobs.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `jobs.get` | `{ id }` | `Job` | 状态机 |
| `jobs.list` | `{ materialId?, status? }` | `Job[]` | |

### 3.5 S3 限时练习

#### 练习会话（practice.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `practice.createSession` | `{ courseId, moduleIds, questionCount, timeLimit?, difficulty?, questionTypes? }` | `PracticeSession` | questionCount 5-20；题型分布 single 60%/multiple 20%/fill 20% |
| `practice.getQuestions` | `{ sessionId }` | `QuestionDTO[]` | **作答前 DTO 不含 correct_answer/acceptable_answers/explanation**（防泄露） |
| `practice.submit` | `{ sessionId, answers: Answer[] }` | `PracticeResult` | 触发规则批改（非 AI）；三策略 |
| `practice.getResult` | `{ sessionId }` | `PracticeResult` | 含逐题结果；is_correct=false 只读输出给 S4 |
| `practice.listSessions` | `{ courseId? }` | `PracticeSession[]` | |

**QuestionDTO（作答前）**：
```typescript
{
  id: string,
  questionType: 'single_choice' | 'multiple_choice' | 'fill_blank',
  questionStem: string,
  options?: string[],            // 选择题选项
  score: number
  // 不含：correct_answer / acceptable_answers / explanation
}
```

### 3.6 S4 错题改错

#### 错题（mistakes.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `mistakes.list` | `{ courseId?, status? }` | `Mistake[]` | |
| `mistakes.get` | `{ id }` | `MistakeWithEvidence` | 含错因、重做历史证据；T-M5-004 方案 A（用户裁决）补登可选 question 摘要：`questionStem/questionType/studentAnswer/correctAnswer/acceptableAnswers/explanation`（S4 完整复盘，handler 既有数据，向后兼容） |
| `mistakes.confirmErrorCause` | `{ id, category, causeNote? }` | `Mistake` | AI 只提建议带"不确定"标记，学生必须确认 |
| `mistakes.suggestErrorCause` | `{ id }` | `{ suggestion: string, confidence: 'low'\|'medium'\|'high' }` | AI 建议（带"不确定"标记） |
| `mistakes.redo` | `{ id, correct? }` | `RedoResult` | MVP 原题重做（T-M5-004 补登 contract 类型：handler 已支持 `correct?: boolean`，正确增加掌握证据，错误保持 needs_review；renderer 显式提供「重做正确/重做错误」两个动作） |
| `mistakes.archive` | `{ practiceAnswerId }` | `Mistake` | 幂等归档（UNIQUE question_id）；重复扫描不重复建 |

#### 薄弱点（weakPoints.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `weakPoints.list` | `{ courseId?, status? }` | `WeakPoint[]` | |
| `weakPoints.get` | `{ id }` | `WeakPoint` | 含 evidence_count |
| `weakPoints.resolve` | `{ id }` | `WeakPoint` | status=resolved（可回退） |
| `weakPoints.regress` | `{ id }` | `WeakPoint` | status=regressed（"已掌握"非终态） |

### 3.7 S5 期末冲刺

#### 模拟考（mockExams.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `mockExams.generatePaper` | `{ assessmentAttemptId, questionCount, timeLimit? }` | `MockExamPaper` | 触发器校验 assessment_attempt 必须 confirmed；source_hash 防重复 |
| `mockExams.getPaper` | `{ paperId }` | `MockExamPaper` | |
| `mockExams.startAttempt` | `{ paperId }` | `MockExamAttempt` | status=in_progress |
| `mockExams.submitAttempt` | `{ attemptId, answers }` | `MockExamResult` | 规则批改客观题；展示总分/正确率/耗时/模块分析 |
| `mockExams.getResult` | `{ attemptId }` | `MockExamResult` | |
| `mockExams.getModuleAnalyses` | `{ attemptId }` | `MockExamModuleAnalysis[]` | 强弱项分析 |

#### 临考速背（cramCards.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `cramCards.get` | `{ assessmentAttemptId }` | `CramCard[]` | **确定性只读 DTO**；不持久化、不依赖 AI、不暴露题干/答案/作答 |

**CramCard DTO**：
```typescript
{
  moduleId: string,
  moduleName: string,
  coreConcept: string,          // 核心概念
  keyPoints: string[],          // 必背要点
  mnemonic?: string,           // 记忆口诀
  commonExamPattern?: string,  // 常见考法
  easyMistake?: string,        // 易错提醒
  importance: number           // 1-5
}
```

#### 冲刺计划（cramPlan.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `cramPlan.get` | `{ assessmentAttemptId }` | `CramPlanDay[]` | **确定性即时只读 7 天 DTO**；不持久化、不替学生改写事实 |

**CramPlanDay DTO**：
```typescript
{
  date: string,
  dayOffset: number,            // 距考天数
  tasks: {
    reviewModules: string[],   // 复习模块
    redoMistakes: string[],    // 重做错题
    practiceCount: number,    // 建议练习题数
    notes: string              // 建议说明
  }
}
```

### 3.8 S6 家长报告

#### 报告（reports.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `reports.generate` | `{ semesterId, reportType, periodStart, periodEnd }` | `ParentReport` | 规则优先 + AI 仅润色；AI 失败保留规则报告 |
| `reports.freeze` | `{ reportKey }` | `ParentReport` | 冻结快照 content_json + content_hash；assertNoSensitiveLeak |
| `reports.get` | `{ reportKey }` | `ParentReport` | |
| `reports.list` | `{ semesterId?, reportType? }` | `ParentReport[]` | |

#### 投递（deliveries.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `deliveries.deliver` | `{ reportKey, channel }` | `ReportDelivery` | 从已保存的同通道报告目标读取非秘密路由配置；按 report_key+channel 去重；状态/错误只暴露脱敏分类，渠道独立失败隔离 |
| `deliveries.retry` | `{ reportKey, channel }` | `ReportDelivery` | 重用既有投递目标；最多重试 3 次，达上限 retained_locally |
| `deliveries.list` | `{ reportKey? }` | `ReportDelivery[]` | 用于投递状态、错误和可重试性回读 |

#### 报告目标（reportTargets.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `reportTargets.list` | `{ semesterId }` | `ParentReportTarget[]` | 仅返回非秘密目标配置 |
| `reportTargets.create` | `{ semesterId, targetName, channelType, channelConfig, credentialKey? }` | `ParentReportTarget` | `channelConfig` 不含收件地址、endpoint 或密钥；真实凭据只以 credential-vault 键名引用 |
| `reportTargets.update` | `{ id, ...fields }` | `ParentReportTarget` | 不回显 credential 值；投递连通性、状态、错误和重试走 `deliveries.*`，不设 `reportTargets.testDelivery` |
| `reportTargets.delete` | `{ id }` | `void` | 软删除 |

### 3.9 S7 课堂采集

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `classCapture.transcribe` | `{ courseId, audioFile, permissionConfirmed }` | `{ transcription: string }` | 受控 PCM WAV（服务端重新验证文件头）；本机 whisper.cpp 同步转写；许可确认强制 |
| `classCapture.saveTranscription` | `{ courseId, transcription, title }` | `Material` | 创建 file_type='text' material，初始 converted |

### 3.10 TTS 朗读（跨子系统，02-PRD §3.9）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `tts.speak` | `{ text: string, engine?: 'sapi'\|'edge-tts' }` | `{ playbackId: string }` | 任意 Markdown/纯文本；SAPI 默认（离线） |
| `tts.control` | `{ playbackId, action: 'play'\|'pause'\|'stop', rate?: number }` | `void` | 播放/暂停/停止/语速调节 |
| `tts.switchEngine` | `{ engine: 'sapi'\|'edge-tts' }` | `void` | 切换引擎 |
| `tts.getStatus` | `{ playbackId }` | `{ state: 'playing'\|'paused'\|'stopped', position: number, duration: number }` | 朗读状态 |

### 3.11 备份恢复（02-PRD §3.10）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `backup.course` | `{ courseInstanceId, targetPath }` | `BackupRecord` | 单课程备份为 zip；写 backup_records |
| `backup.allCourses` | `{ semesterId, targetPath }` | `BackupRecord` | 单一完整学期备份 zip（`backup_type=semester`），包含学期库、资料 storage、exports 和关联报告目标；归档前后强制 |
| `backup.restore` | `{ zipPath, targetSemesterId, conflictResolution?: 'overwrite'\|'create_new' }` | `RestoreResult` | content_hash 校验完整性；同名冲突学生确认 |
| `backup.list` | `{ semesterId?, courseInstanceId? }` | `BackupRecord[]` | 从 backup_records 读取 |
| `backup.configureSchedule` | `{ semesterId, courseInstanceId?, cronExpression, timezone }` | `BackupSchedule` | 配置定期调度（每周一/每月一） |
| `backup.listSchedules` | `{ semesterId }` | `BackupSchedule[]` | |
| `backup.toggleSchedule` | `{ id, enabled }` | `BackupSchedule` | 启用/禁用调度 |

**RestoreResult DTO**：
```typescript
{
  success: boolean,
  restoredCourseId: string, // 学期包恢复时为空字符串
  conflictResolved: 'overwrite' | 'create_new' | 'none',
  tablesImported: string[],
  filesRestored: number,
  integrityCheck: 'ok' | 'warning',
  schemaVersion?: string
}
```

### 3.12 技能管理（skills.*，借鉴 pi-desktop）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `skills.list` | `{}` | `SkillManifest[]` | 当前返回受控空集，不触网扫描 |
| `skills.search` | `{ query }` | `SkillManifest[]` | 当前返回受控空集，不触网搜索 |
| `skills.install` | `{ source: 'github', hub, name }` | `SkillManifest` | 当前显式拒绝：GitHub 安装尚未启用，不隐式联网 |
| `skills.getContent` | `{ name }` | `{ skillMd: string, helpers: string[] }` | 当前未安装时返回 NOT_FOUND |
| `skills.uninstall` | `{ name }` | `void` | 当前未安装时返回 NOT_FOUND |

### 3.13 模型配置（models.*，借鉴 pi-desktop）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `models.list` | `{}` | `ModelProvider[]` | 读取 `<dataRoot>/config/pi-models.json` 的非敏感 provider/model 目录；旧安装自动合并默认目录 |
| `modelsConfig.get` | `{}` | `ModelConfig` | 读 `<dataRoot>/config/models.json`（存在则返回默认 provider/model） |
| `modelsConfig.set` | `{ provider, model }` | `ModelConfig` | 持久化到 `<dataRoot>/config/models.json`（`__studybuddy_managed` 标记） |
| `modelsConfig.test` | `{ provider, model, apiKey? }` | `{ ok, latencyMs, error? }` | 先在 `<dataRoot>/config/pi-models.json` 校验 provider/model，再对选中聊天模型发送最小 OpenAI-compatible 请求；优先临时 key，否则只在 host 从 vault 读取 `modelProvider:<provider>`；不传学生数据，不回显 key/base URL/远端正文 |
| `models.probe` | `{ provider }` | `ModelInfo[]` | 用户主动触发 `/models` 目录发现；host 从 vault 读取该 provider 的 key，成功后仅将模型别名原子写入 `<dataRoot>/config/pi-models.json`；失败不覆盖原目录 |
| `models.addProvider` | `{ providerConfig }` | `ModelProvider` | 当前只做参数回显，不持久化 |

<!-- supersedes: v0.1.4 原写 models.list"从 ~/.pi/agent/models.json"、modelsConfig.set 未标落点；T-M3-005 裁决 1 改业务数据根 <dataRoot>/config/models.json（AGENTS.md §9.5 物理隔离，pi-studybuddy 不侵入 ~/.pi） -->

### 3.14 设置（settings.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `settings.get` | `{}` | `AppSettings` | 含 simpleMode/backupSchedule 等 |
| `settings.update` | `{ ...fields }` | `AppSettings` | |
| `settings.getSimpleMode` | `{}` | `boolean` | Simple Mode 总开关（03-Architecture §2.5） |
| `settings.setSimpleMode` | `{ enabled }` | `void` | 切换 L2 知识库开关 |

### 3.15 密钥管理（credentials.*）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `credentials.set` | `{ key: string, value: string }` | `void` | DPAPI 加密；键名匹配 modelProvider:xxx/parentContact:xxx |
| `credentials.get` | `{ key: string }` | `{ value: string }` | DPAPI 解密 |
| `credentials.delete` | `{ key: string }` | `void` | |
| `credentials.listKeys` | `{ prefix?: string }` | `string[]` | 仅返回键名，不返回值 |

### 3.16 工具发现（toolchains.*，借鉴 pi-desktop）

| 方法 | 参数 | 返回 | 约束 |
|---|---|---|---|
| `toolchains.list` | `{}` | `ToolchainStatus[]` | 发现-探测结果（health: unsupported/unverified/healthy） |
| `toolchains.install` | `{ capabilityId }` | `ToolchainStatus` | 安装到 userData，不改系统 PATH |
| `toolchains.rescan` | `{}` | `ToolchainStatus[]` | 窗口 focus 时 60s TTL 重扫 |

---

## 4. Streams（服务端推送主题）

> 借鉴 pi-desktop `contract/api.ts` 的 `interface Streams`。renderer 通过 `subscribe(topic, key, on)` 订阅。

| Stream 主题 | 触发条件 | 推送数据 | 说明 |
|---|---|---|---|
| `agent.events` | pi agent 事件 | `AgentEvent` | 流式回复、工具调用视图、上下文压缩状态 |

> **AgentEvent payload 结构化说明（T-M3-002 增补，用户 2026-08-08 批准）**：payload 按 kind 区分为结构化联合（`src/contract/types.ts`）：
>
> | kind | payload | 说明 |
> |---|---|---|
> | `message_start` | `{}` | 消息开始 |
> | `token` | `{ text }` | 流式文本增量 |
> | `tool_call` | `{ toolCallId, toolName, inputSummary }` | 工具调用开始（字段子集对齐 pi 底座 ToolCallEvent） |
> | `tool_result` | `{ toolCallId, toolName, isError, resultSummary }` | 工具调用结果（字段子集对齐 pi 底座 ToolResultEvent） |
> | `context_compressed` | `{ compressed: true }` | 长对话上下文压缩 |
>
> **脱敏铁律（AGENTS.md §9.3）**：tool_call/tool_result 的 inputSummary（≤120 字符）/resultSummary（≤160 字符）为脱敏截断摘要，不含完整输入/输出/密钥/完整 UUID/文件路径；toolCallId 用短 id（call-<n>）非 UUID。renderer 渲染前二次脱敏（UUID 正则过滤）。
| `files.changed` | file-watch 检测 | `{ path: string, changeType: 'add'\|'change'\|'unlink' }` | 100ms 防抖 |
| `jobs.progress` | Job 状态变更 | `Job` | 转换/生成进度 |
| `practice.timer` | 练习计时 | `{ sessionId, elapsedMs, remainingMs? }` | 前端计时，限时可超时标记 |
| `tts.state` | TTS 播放状态 | `{ playbackId, state, position, duration }` | 朗读状态由前端管理 |
| `backup.progress` | 备份进度 | `{ backupRecordId, phase, progress }` | 备份/恢复进度 |
| `delivery.status` | 投递状态变更 | `ReportDelivery` | 投递成功/失败/重试 |
| `toolchains.changed` | 工具发现变更 | `ToolchainStatus[]` | 窗口 focus 重扫后 |
| `schedule.reminder` | 调度提醒 | `{ taskType, message }` | 桌面通知 + 应用内消息中心 |

---

## 5. DTO 规范

### 5.1 防泄露原则（02-PRD §3.4）

**作答前 DTO 不含敏感字段**：
- `practice.getQuestions` 返回的 `QuestionDTO` **不含** `correct_answer` / `acceptable_answers` / `explanation`
- `mockExams.getPaper`（未提交时）同样不含
- 提交后 `getResult` 才返回完整信息

### 5.2 脱敏原则（02-PRD §5.2）

**家长报告 DTO 不含**：
- 资料原文、笔记正文
- 完整题干、完整答案、学生作答
- 错因正文（error_cause_note）
- 聊天内容
- 真实渠道地址（邮箱/Webhook URL）
- 完整 UUID

**UUID 泄漏检测**（`assertNoSensitiveLeak`）：
- 序列化整个 ParentReportResult
- UUID 正则 `/[0-9a-f]{8}-...-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i` 检测
- 发现任何完整 UUID → 抛 `PARENT_REPORT_PRIVACY_VIOLATION`(500)

### 5.3 分页规范

```typescript
{
  success: true,
  data: T[],
  meta: {
    total: number,
    page: number,
    pageSize: number,
    timestamp: string
  }
}
```

- 默认 pageSize=20，最大 100
- cursor 分页（session 列表用 dev+ino+birthtimeMs 哈希防陈旧）

### 5.4 时间戳规范

- 所有时间戳：ISO 8601 UTC（如 `2026-08-07T12:00:00Z`）
- 日期（无时间）：ISO 日期（如 `2026-08-07`）
- 时区： Asia/Shanghai（学生本地时区）

---

## 6. 路由分组与权限

### 6.1 方法命名空间

| 命名空间 | 子系统 | 说明 |
|---|---|---|
| `sessions.*` / `files.*` / `toolchains.*` | 桌面壳 | 借鉴 pi-desktop |
| `semesters.*` / `courses.*` / `exams.*` / `schedule.*` / `tasks.*` / `events.*` | S1 | 学习节奏 |
| `materials.*` / `notes.*` / `modules.*` / `jobs.*` | S2 | 资料笔记 |
| `practice.*` | S3 | 限时练习 |
| `mistakes.*` / `weakPoints.*` | S4 | 错题改错 |
| `mockExams.*` / `cramCards.*` / `cramPlan.*` | S5 | 期末冲刺 |
| `reports.*` / `deliveries.*` / `reportTargets.*` | S6 | 家长报告 |
| `classCapture.*` | S7 | 课堂采集 |
| `tts.*` | 横切 | TTS 朗读 |
| `backup.*` | 横切 | 备份恢复 |
| `skills.*` / `models.*` / `settings.*` / `credentials.*` | 系统 | 技能/模型/设置/密钥 |

### 6.2 权限模型

- **单用户单机**：学生拥有全部读写权限，无需 RBAC
- **家长不进系统**：家长无任何 API 端点；报告是"推"不是"拉"
- **workspace-path-guard**：write/edit 类操作受路径守卫拦截（03-Architecture §3.4）
- **credential-vault**：密钥读写经 DPAPI 加密

---

## 7. 版本历史

| 版本 | 日期 | 变更 |
| v0.1.9 | 2026-08-13 | **用户明确同意的最小闭环扩展**：新增 `modules.create`（`courseId`、当前 NotesTab 显式选择的 `materialId`、模块名称及可选摘要/重要度/难度），用于让 S2 资料经可见 UI 形成可练习知识模块并进入 S3/S4 真机 UAT。原因：用户裁决 S2/S3/S4 创建前置条件必须属于 T-M5-004，现有生产契约仅有 list/get/updateLearnStatus，无法在禁止 DB 预置、直调与真实外部 AI 的边界内建立练习前置。影响：typed RPC 方法数 127→128；新增最小 S2 handler 与 NotesTab 局部入口；不改 SQLite schema/Stream/跨 Tab 全局状态，不连真实外部 AI。依据：用户 2026-08-13 “同意” + AGENTS.md §2、§5、§7、§11。 |
| v0.1.8 | 2026-08-10 | 修正 T-M4-011 文件导入契约：main 的 open-file dialog 返回一次性 `importToken/fileName/fileSize`，生产 S2 renderer 以 capability 调用 `materials.upload`，host 消费 token 并从 staging 源文件取得真实大小；`FileMeta.path` 不用于 S2 生产上传；无新增 RPC 方法。 |
| v0.1.7 | 2026-08-10 | T-M4-011 资料上传契约落地：生产 S2 `materials.upload` 使用 Electron 选择器返回的 `FileMeta.path`，host 校验普通文件并复制到业务 storage，真实大小来自 `stat`；S2 写操作在 host 侧拒绝 archived 学期；无新增 RPC 方法。 |
| v0.1.6 | 2026-08-09 | 交叉审查修订：新增 `MODEL_NOT_CONFIGURED`；明确生产 `agent.send` 只能路由到业务数据根配置构造的真实 session，测试夹具必须显式注入；同步实际文件/技能/模型安全占位 handler 与契约覆盖检查。 |
| v0.1.5 | 2026-08-08 | §3.13 模型配置落点修订（T-M3-005 裁决 1）：models.list 约束列"从 ~/.pi/agent/models.json" → "受控 fixture（不读 ~/.pi；T-M3-002 裁决）"；modelsConfig.get/set 约束列标清落点 `<dataRoot>/config/models.json`（__studybuddy_managed 标记）。原因：AGENTS.md §9.5 物理隔离（pi-studybuddy 不侵入 ~/.pi）。影响：仅约束列文字修订 + supersedes 注记，无契约方法新增/变更（Api 方法总数仍 127）。依据：AGENTS.md §11.1 + T-M3-005 裁决 1 |
| v0.1.4 | 2026-08-08 | §3.1 落地注解：sessions.search（T-M3-003 实现，L3 bigram OR-combined MATCH + session_id 聚合映射）+ SessionSummary 扩展学习场景元数据（subject/goal/mistakeIds 可选字段）+ §3.1.1 agent.send T-M3-003 扩展注解（sessionMeta 参数 + [学习上下文] token 同步注入 + 元数据写回）。原因：T-M3-003 学习场景业务化实施（学科标签/学习目标/错题关联/L1 注入/L3 检索承载层）。影响：§3.1/§3.1.1 说明性增补 + SessionSummary 类型扩展（可选字段向后兼容），无契约方法新增（Api 方法总数仍 127）。依据：AGENTS.md §11.1 治理基线修改规则 + T-M3-003 计划 |
| v0.1.3 | 2026-08-08 | §4 增补 AgentEvent payload 结构化说明（tool_call/tool_result 脱敏载荷字段子集对齐 pi 底座 ToolCallEvent/ToolResultEvent + 脱敏铁律）+ §3.2 files.read 落地注解（T-M3-002 实现：allowed-roots 白名单门禁 + 相对 storageKey 解析 + 1MB 截断）+ §3.1.1 agent.send T-M3-002 扩展注解（tool_call/tool_result 事件对）。原因：T-M3-002 pi 原生能力承载实施（用户批准 payload 结构化 + files.read 现成契约方案）。影响：§4 AgentEvent 说明性增补 + §3.2/§3.1.1 注解，无契约方法新增/变更（Api 方法总数仍 127）。依据：AGENTS.md §11.1 治理基线修改规则 + T-M3-002 计划 |
| v0.1.2 | 2026-08-08 | §3.1.1 新增 `agent.send` RPC 契约（params: `{ sessionId, text }`，result: `{ eventCount }`）：对话 Tab 发送通道，renderer 发送用户消息 → agent-host 触发 Streams["agent.events"] 受控序列（message_start → token×N → context_compressed）。范围注解：T-M3-001 受控夹具发射（08-Test §5.4 全 mock，不连真实 LLM），完整流式/工具视图/上下文压缩属 T-M3-002。原因：07-WF §2.8 对话路径步骤 2 需要 renderer→agent-host 的发送通道，现有 RPC 方法表无 agent.* 方法。影响：契约新增 1 方法（Api 方法总数 127），无既有方法变更。依据：AGENTS.md §11.2 修订纪律 + T-M3-001 计划 |——sessions.* 是"💬 对话"标签页（默认主入口）的会话管理基础，会话即对话 Tab 内容，承载 pi 原生 AI 对话能力（02-PRD §3.11 + 03-Architecture §6.7 + 09-UI §4.2 贯通） |
| v0.1.0 | 2026-08-07 | 初始草案：API 总览（RPC 架构非 REST）；API 信封（{success,data,error} + 5 错误码）；RPC 方法表（sessions/files/S1-S7/TTS/备份恢复/skills/models/settings/credentials/toolchains 共 100+ 方法）；Streams（9 个推送主题）；DTO 规范（防泄露/脱敏/分页/时间戳）；路由分组与权限。输入：03-Architecture §3/§6 + 02-PRD §5 + 05-ERD |

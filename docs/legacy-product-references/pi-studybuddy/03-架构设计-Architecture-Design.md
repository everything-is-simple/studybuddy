# 03 架构设计

**版本**：v0.1.3
**日期**：2026-08-09
**状态**：✅ 已审查批准；T-M5-011 执行中。

> 当前架构落地顺序：开发机先固定 Electron/Node、Python/OCR、whisper、WPS 和默认配置，按真实用户主路径跑通；完成后复制同一运行拓扑到使用机。问题总账见 [系统集成/02](./系统集成/02-系统问题总账与整改清单.md)。
**上游**：[docs/00 索引](./00-文档索引-Index.md)、[01-TRD v0.2.4](./01-TRD-技术需求-Technical-Requirements.md)、[02-PRD v0.1.4](./02-PRD-产品需求-Product-Requirements.md)、[docs/prep-参考点核对表.md](./prep-参考点核对表.md)
**下游**：05-ERD、06-API、07-Workflow、08-Test、09-UI

---

## 1. 架构总览

### 1.1 一句话架构

**pi-studybuddy = pi（AI 底座，不动内核）+ StudyBuddy 扩展层（registerTool + pi.on 钩子）+ 业务 Adapter（S1-S7 + TTS + 备份恢复）+ pi-desktop 五件骨架（三进程 + 契约 + 安全 + 工具发现 + 文件体验）**

### 1.2 四层架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│  桌面壳层（pi-desktop 五件骨架，Apache-2.0，搬运改名）              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ main     │ │ preload  │ │ renderer │ │agent-host│ │ contract │ │
│  │ (窗口/托盘│ │ (受控桥接│ │ (React 19│ │(utility  │ │ (类型化  │ │
│  │  /协议)  │ │  PiBridge)│ │  +Vite)  │ │ Process) │ │  IPC+RPC)│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│  安全骨架：sandbox:true + 严格 CSP + credential-vault(DPAPI)        │
│  公用零件：toolchain 发现-探测-安装-绝对路径 + file-watch           │
└─────────────────────────────────────────────────────────────────────┘
                                ▲ MessagePort RPC
┌─────────────────────────────────────────────────────────────────────┐
│  pi 扩展层（单一 extension factory，永不修改内核）                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ studybuddy-extension.ts（createStudyBuddyExtension()）      │   │
│  │  ├─ registerTool 批量注册业务工具（S1-S7+TTS+备份恢复）     │   │
│  │  ├─ pi.on 钩子（before_agent_start/tool_call/tool_result/   │   │
│  │  │              model_select/session_start/turn_end）       │   │
│  │  ├─ pi.registerProvider() 注入模型供应商                    │   │
│  │  └─ Simple Mode 总开关（学习场景精简模式）                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  底座：@earendil-works/pi-coding-agent + @earendil-works/pi-ai      │
└─────────────────────────────────────────────────────────────────────┘
                                ▲ registerTool / pi.on
┌─────────────────────────────────────────────────────────────────────┐
│  业务 Adapter 层（S1-S7 业务能力 + 横切能力）                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │ S1   │ │ S2   │ │ S3   │ │ S4   │ │ S5   │ │ S6   │ │ S7   │  │
│  │学习  │ │资料  │ │限时  │ │错题  │ │期末  │ │家长  │ │课堂  │  │
│  │节奏  │ │笔记  │ │练习  │ │改错  │ │冲刺  │ │报告  │ │采集  │  │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘  │
│  横切：TTS 朗读 + 备份恢复 + workspace-path-guard + observability   │
│  外部桥：WPS COM(pywin32) + whisper.cpp + OCR venv                  │
└─────────────────────────────────────────────────────────────────────┘
                                ▲ 读写
┌─────────────────────────────────────────────────────────────────────┐
│  数据层（物理隔离：~/.pi vs %LOCALAPPDATA%\PiStudyBuddy）           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────────┐  │
│  │ pi 会话目录  │ │ 业务数据根  │ │ 三层记忆（inno-agent 借鉴） │  │
│  │ ~/.pi/agent/│ │ %LOCALAPPDATA│ │ L1 学习者画像（profile.json)│  │
│  │  auth.json  │ │ \PiStudyBuddy│ │ L2 知识库（BM25+图谱）      │  │
│  │  models.json│ │  ├ global.db │ │ L3 会话检索（SQLite FTS5   │  │
│  │  settings.  │ │  │  semesters│ │     bigram 分词）          │  │
│  │   json      │ │  │  backup_  │ │                             │  │
│  │  extensions/│ │  │   records │ │ credential-vault（DPAPI）   │  │
│  │  skills/    │ │  │  parent_  │ │  modelProvider:xxx          │  │
│  │  prompts/   │ │  │   targets │ │  parentContact:xxx          │  │
│  └─────────────┘ │  ├ semester/│ └─────────────────────────────┘  │
│                  │  │  └ sem.db│                                  │
│                  │  └ storage/ │                                  │
│                  └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 数据流（学生触发一次学习行为）

```
学生操作 → renderer(PiBridge) → main(IPC) → agent-host(RPC)
  → pi 扩展层(registerTool 工具执行)
    → 业务 Adapter(S1-S7 工具)
      → 数据层(semester.db 读写 / storage_key 文件 / 三层记忆)
    → pi.on("tool_result") 集中日志（observability）
  → 流式回复 → renderer(React) → 学生
```

### 1.4 设计原则（铁律）

1. **永不修改 pi 内核**：所有业务能力通过 `registerTool`、扩展（Extension）、技能（Skill）接入；内核源码只读
2. **registerTool 是业务能力唯一入口**：S1-S7 + TTS + 备份恢复所有工具必须经 `pi.registerTool(tool)` 注入
3. **规则优先、AI 辅助**：日期/统计/去重/状态/批改由确定性规则负责，AI 只负责受约束生成或润色
4. **单机零云依赖**：仅 127.0.0.1，无公网入口、无云数据库、无自动同步
5. **骨架稳定、业务可演化**：pi-desktop 五件骨架直接搬运改名（稳定层），业务 Adapter 独立自建（可演化层）
6. **progressive disclosure**：技能 description 常驻 system prompt，正文与 helper 按需加载，扁平目录一层深
7. **物理隔离**：pi 会话目录 `~/.pi` 与业务数据根 `%LOCALAPPDATA%\PiStudyBuddy` 互不侵入

---

## 2. pi 扩展层设计

> 输入：prep-参考点核对表 §一（pi）、§三（inno-agent）。inno-agent 的 `createInnoExtension()` 是直接路线图。

### 2.1 单一扩展工厂

**设计**：pi-studybuddy 以单一扩展工厂 `createStudyBuddyExtension()` 接入 pi 内核，对应 inno-agent 的 `createInnoExtension()`（prep §三第 1 行）。

**文件**：`src/agent/studybuddy-extension.ts`

**结构**：

```typescript
// 伪代码，仅示结构，非实现
export function createStudyBuddyExtension(): PiExtension {
  return {
    name: "pi-studybuddy",
    setup(pi) {
      // 1. 注册模型供应商（pi.registerProvider）
      registerModelProviders(pi);

      // 2. 批量注册业务工具（registerTool）
      for (const tool of [
        ...createS1RhythmTools(),      // 学习节奏
        ...createS2NoteTools(),        // 资料笔记
        ...createS3PracticeTools(),    // 限时练习
        ...createS4ErrorTools(),       // 错题改错
        ...createS5CramTools(),        // 期末冲刺
        ...createS6ReportTools(),      // 家长报告
        ...createS7CaptureTools(),     // 课堂采集
        ...createTtsTools(),           // TTS 朗读
        ...createBackupTools(),        // 备份恢复
      ]) {
        pi.registerTool(tool);  // 唯一入口，返回 void
      }

      // 3. 注册生命周期钩子（pi.on）
      registerHooks(pi);

      // 4. Simple Mode 总开关
      if (config.simpleMode) enableSimpleMode(pi);
    },
  };
}
```

### 2.2 registerTool 工具注册契约

**契约依据**（prep §一第 8 行）：`packages/coding-agent/src/core/extensions/types.ts:1251-1253`

```typescript
registerTool<TParams, TDetails, TState>(tool: ToolDefinition<...>): void
```

**ToolDefinition 必填字段**：`name` / `label` / `description` / `parameters` / `execute`
**可选字段**：`promptSnippet` / `promptGuidelines` / `constrainedSampling` / `renderShell` / `prepareArguments` / `executionMode`

**execute 返回**：`{ content, details, usage?, terminate? }`，错误须 `throw`（不返回 error 对象）

**单件测试断言依据**：每个学习工具单测须断言 execute 返回形状与抛错语义，并断言 registerTool 返回 void。

### 2.3 pi.on 生命周期钩子清单

**借鉴 inno-agent**（prep §三第 1 行）：`inno-extension.ts` 通过 `pi.on` 多钩子做路径守卫、错误集中日志、上下文注入、L3 增量索引。

| 钩子 | pi-studybuddy 用途 | 借鉴来源 |
|---|---|---|
| `before_agent_start` | 多源上下文注入：L1 学习者画像 + 当前学期/课程上下文 + 私有技能清单 + 最近学习事件 | inno-agent before_agent_start |
| `session_start` | 初始化学期库连接、加载 L1 画像 | inno-agent session_start |
| `tool_call` | **workspace-path-guard 拦截**：write/edit 类工具校验路径不逃逸业务数据根 | inno-agent workspace-path-guard |
| `tool_result` | **集中错误日志**：所有工具失败统一走此钩子记录（observability） | inno-agent tool_result |
| `model_select` | 持久化学生选择的默认模型到 `<dataRoot>/config/models.json`（`__studybuddy_managed` 标记） | inno-agent model_select |
| `turn_end` | L3 会话检索增量索引（基于 last_offset + last_mtime_ms） | inno-agent turn_end |

<!-- supersedes: v0.1.1 原写 "~/.pi/agent/models.json"，T-M3-005 裁决 1 改业务数据根 <dataRoot>/config/models.json（AGENTS.md §9.5 物理隔离，pi-studybuddy 不侵入 ~/.pi） -->

### 2.4 pi-ai provider 注入

**契约依据**（prep §一第 9 行）：`@earendil-works/pi-ai` 的 `Provider<TApi>` 接口 + `createProvider<TApi>()` 工厂 + `builtinProviders()` 38 个内置 provider 工厂。

**pi-studybuddy 用法**：
- **不重写 provider**，仅在扩展层用 `pi.registerProvider()` 注入学习场景专用 provider
- 所有 model 选择、鉴权、流式派发复用 pi-ai 抽象（`stream`/`streamSimple` 契约）
- 国内供应商（ZAI/Qwen/Xiaomi）覆盖对学习场景合规与成本控制是直接红利（prep §一第 5 行）
- 学生可接本地推理（Ollama）或自建代理走 `~/.pi/agent/models.json`（prep §一第 6 行）

**密钥管理**：provider 的 API Key 走 credential-vault（DPAPI），键名 `modelProvider:xxx`（TRD §7 决策 3）。

### 2.5 Simple Mode 总开关

**借鉴 inno-agent**（prep §三第 2 行）：`config.memory.{l1,l2,l3}Enabled` 控制，Simple Mode 全局总开关。

**pi-studybuddy 语义**：
- **完整模式**（默认）：L1 画像 + L2 知识库（BM25 + DIRECT_LINK）+ L3 会话检索 全开
- **Simple Mode**：仅 L1 + L3，L2 知识图谱关闭（个人学习场景图谱规模小，可降级）
- 学生可在设置中切换；切换不影响已持久化数据

---

## 3. 业务 Adapter 层

> 输入：02-PRD §3（S1-S7 + TTS + 备份恢复）、prep §三（inno-agent 范本）、prep §五.3（必须独立设计）。

### 3.1 工具注册清单（按子系统）

> 每个工具是一个 `ToolDefinition`，经 `pi.registerTool(tool)` 注入。工具名前缀 `studybuddy_*` 避免与 pi 内置工具冲突。

#### S1 学习节奏 StudyRhythm

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_init_semester` | 学期初始化（日期→课程表 OCR→学生确认→原子化建学期/课程/课表） | OCR 识别预览后学生一次确认；未确认考试不驱动倒计时 |
| `studybuddy_add_exam` | 补全考试日期（保留来源/置信度/确认/变更历史） | 考试确认四态：pending/confirmed/rejected/superseded |
| `studybuddy_confirm_exam` | 学生确认考试（写 confirmation_status/confirmed_at） | 未确认不驱动冲刺 |
| `studybuddy_daily_brief` | 每日首页"明日准备/到期/待质检/错题复习/下一步" | 规则聚合（非 AI），只呈现少量待闭合项 |
| `studybuddy_complete_task` | 任务完成写 StudyEvent | source_system='S1' |
| `studybuddy_transition_semester` | 学期状态机 active→teaching_ended→follow_up→archived | 归档前后强制触发完整备份（见 §3.9） |

#### S2 资料笔记 NoteBuilder

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_upload_material` | 上传资料（PDF/DOCX/PPTX/图片/TXT/MD；doc/ppt/xls 经 WPS COM 转中间格式） | storage_key 相对路径，触发器拒绝 `..`/`:\`/`:/` |
| `studybuddy_convert_material` | 转换 Job（PDF/OCR/DOCX/PPTX 各有超时） | Material 状态机 pending→converting→converted→note_generating→completed |
| `studybuddy_generate_note` | AI 笔记生成（Markdown + highlights + Markmap + 知识模块） | 知识模块必须带 source_evidence 回链；AI 不可用保留 normalized_text + pending_quality_check |
| `studybuddy_retry_conversion` | 失败恢复（retry-conversion） | 最多 3 次 |
| `studybuddy_retry_ai_generation` | 失败恢复（retry-ai-generation） | 最多 3 次 |
| `studybuddy_replace_text` | 手动粘贴纯文本跳过转换 | replace-text |
| `studybuddy_s7_handoff` | S7 课堂转写文本创建 file_type='text' material | 初始 converted，不自动建 Job |

#### S3 限时练习 PracticeRunner

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_generate_questions` | 同步调 AI 生成客观题（单选 60%/多选 20%/填空 20%） | AI 失败不创建空 session；作答前 DTO 不含 correct_answer/acceptable_answers/explanation |
| `studybuddy_submit_practice` | 提交答题触发**规则批改**（非 AI） | 三策略：单选精确/多选 deepEquals/填空 normalize |
| `studybuddy_get_practice_result` | 读取 session 汇总 + 逐题答题 | is_correct=false 只读输出给 S4 |

#### S4 错题改错 ErrorFixer

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_archive_mistake` | 幂等归档 is_correct=false 答题为 mistake | UNIQUE(question_id) + UNIQUE(source_practice_answer_id) |
| `studybuddy_confirm_error_cause` | 学生确认/修改错因（六分类） | AI 只提建议带"不确定"标记，学生必须确认 |
| `studybuddy_redo_mistake` | 重做（MVP 原题重做） | 重做正确增加掌握证据，错误保持 needs_review |
| `studybuddy_aggregate_weak_point` | 多条错误证据归纳为 weak_point | evidence_count≥2 才形成；UNIQUE(course_instance_id, knowledge_module_id) |

#### S5 期末冲刺 ExamCrammer

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_generate_mock_exam` | AI 生成限时模拟卷（独立于 S3） | 触发器校验 assessment_attempt 必须 confirmed；source_hash 防重复生成 |
| `studybuddy_submit_mock_exam` | 学生限时作答 + 规则批改客观题 | 展示总分/正确率/耗时/逐题结果/模块覆盖 |
| `studybuddy_get_cram_cards` | 确定性只读聚合速背卡 DTO | 不持久化、不依赖 AI、不暴露题干/答案/作答 |
| `studybuddy_get_cram_plan` | 确定性即时只读 7 天每日建议 DTO | 不持久化、不替学生改写事实 |

#### S6 家长报告 ParentReport

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_generate_report` | 规则报告优先生成（5 section + data_quality） | 规则优先 + AI 仅润色；AI 失败保留规则报告 |
| `studybuddy_freeze_report` | 冻结脱敏快照（content_json + content_hash） | assertNoSensitiveLeak UUID 泄漏检测 |
| `studybuddy_deliver_report` | 按 report_key+channel 去重投递 | 渠道独立失败隔离；最多重试 3 次 |

#### S7 课堂采集 ClassCapture

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_transcribe_class` | 本机 whisper.cpp 同步转写受控 PCM WAV | CLI/模型路径只来自配置；不回退云端；许可确认强制 |
| `studybuddy_save_transcription` | 学生修改后保存为 S2 笔记输入 | 创建 file_type='text' material，初始 converted |

### 3.2 横切能力工具

#### TTS 朗读（跨子系统随时可击发，02-PRD §3.9）

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_tts_speak` | 触发朗读（任意 Markdown/纯文本） | SAPI 默认（离线）；edge-tts 可选 skill |
| `studybuddy_tts_control` | 播放/暂停/停止/语速调节 | 朗读状态由前端管理 |
| `studybuddy_tts_switch_engine` | 切换 SAPI/edge-tts | 封装为 skill，progressive disclosure |

**场景化朗读**（非穷举，由 renderer 在对应位置触发）：
- S2 笔记朗读：每日整理完毕当日学习笔记 → TTS
- S4 错题复盘朗读：错题复盘笔记/解析 → TTS
- S5 考前冲刺朗读：考前冲刺要点 → 每日 TTS
- 任意 Markdown 内容均可触发

**数据契约**：无独立 TTS 表（朗读是即时行为不持久化）；学生主动标记"已复习"走 S1 StudyEvent 的 `practice_reviewed` 类事件。

#### 备份恢复（按课程 zip 包 + 定期调度，02-PRD §3.10）

| 工具名 | 用途 | 关键约束 |
|---|---|---|
| `studybuddy_backup_course` | 单课程备份为 zip（semester.db 相关表数据 + storage_key 资料文件） | 按 course_instance_id 过滤导出；写 backup_records |
| `studybuddy_backup_all_courses` | 全课程备份（考前/归档前/重大变更后） | 强制触发（归档前后） |
| `studybuddy_restore_course` | 从本地备份 zip 恢复对应课程 | content_hash 校验完整性；同名冲突学生确认覆盖/新建 |
| `studybuddy_list_backups` | 列出备份历史 | 从 backup_records 读取 |
| `studybuddy_configure_backup_schedule` | 配置定期调度（每周一/每月一） | 写 backup_records 调度配置 |

**SQLite 崩溃应对**：WAL 模式 + 定期 zip 备份双保险；崩溃/损坏后从最近备份恢复，最多丢失一个备份周期（一周/一月）的数据。

### 3.3 外部桥 Adapter

#### WPS COM 桥（TRD §7 决策 1：Python pywin32 子进程）

**设计**：复用 OCR venv 的 Python 运行时（`H:\AIStudyBuddy\runtime\venv\Scripts\python.exe`），零新依赖。

**契约**：
- 主进程（Node）通过 `child_process.spawn(python, [wps_bridge.py, ...args])` 调用
- 输入/输出经 stdin/stdout JSON 协议
- 子进程隔离 WPS 崩溃不影响主进程
- 转换：doc→docx、ppt→pptx、xls→xlsx，再走现有管道

**五阶段治理位置**：新组件，严格走五阶段（下载储存→单件测试→集成测试→组装→系统冒烟/E2E）。

#### whisper.cpp Adapter（S7-MVP 底座迁移）

**设计**：本机 whisper.cpp 同步转写受控 PCM WAV。

**契约**：
- CLI/模型路径只来自配置（`~/.pi/agent/settings.json` 或业务数据根配置）
- 不猜路径、不回退云端
- 子进程调用，stdout 返回转写文本
- 路径/stdout/stderr/密钥不泄漏；固定错误码

**toolchain 依赖**：依赖 §6.5 的 toolchain 发现机制发现健康的 Python/uv/Node。

#### OCR venv Adapter

**设计**：onnxruntime/PIL 原生支持全图片格式（jpg/jpeg/png/webp/gif/bmp/tiff）。

**契约**：
- 复用 `H:\AIStudyBuddy\runtime\venv\Scripts\python.exe`
- 子进程调用，JSON 协议
- 手写 OCR 走本地 RapidOCR（不走多模态 AI，02-PRD §4.1 吸收结论）

### 3.4 workspace-path-guard（路径守卫）

**借鉴 inno-agent**（prep §三第 7 行）：`src/agent/workspace-path-guard.ts` 的 `checkWorkspaceMutationPath(workspaceDir, requestedPath)`。

**pi-studybuddy 落地**：
- 在 `pi.on("tool_call")` 拦截 write/edit 类工具
- 流程：`normalizeToolPath`（处理 `@`/`~`/`file://`/Unicode 空格）→ `resolve` → `findExistingAncestor` → `realpathSync` 解析符号链接 → `isWithin` 判断
- 越界 `block: true`
- 业务数据根 `%LOCALAPPDATA%\PiStudyBuddy` 是工作区边界
- storage_key 相对路径，触发器拒绝 `..`/`:\`/`:/`（02-PRD §3.3）

### 3.5 observability-extension（可观测扩展）

**借鉴 inno-agent**（prep §三第 7 行）：`src/agent/observability-extension.ts`。

**pi-studybuddy 落地**：
- 两层观测：扩展层 `pi.on` + Prompt 观察者 `session.subscribe`
- 事件：agent_start/end、turn_start/end、tool_execution_start/end（带 args/result 摘要 + durationMs）
- 提取 token 用量
- `safeHandler` 全包 try-catch 确保观测不影响 agent loop
- `summarizeArgs`/`summarizeResult` 按工具类型做摘要（不记录全文）
- **AI 日志 allowlist**（02-PRD §5.3）：非 allowlist 字段抛错

---

## 4. 数据层设计

> 输入：02-PRD §3 数据契约要点、prep §三（inno-agent 三层记忆）、TRD §7 决策 3（物理隔离）。

### 4.1 物理隔离（TRD §7 决策 3）

```
~/.pi/agent/                          ← pi 自管，pi-studybuddy 不侵入
  ├ auth.json (0600)                  ← providers.md 的 OAuth 凭据
  ├ models.json                       ← pi 自定义 provider/model（供 pi 底座，pi-studybuddy 不标记）
  ├ settings.json                    ← pi 设置
  ├ extensions/                       ← pi 扩展（studybuddy-extension 在此加载）
  ├ skills/                           ← pi 技能（学习技能包在此）
  └ prompts/                          ← pi prompt 模板

%LOCALAPPDATA%\PiStudyBuddy\          ← 业务数据根，pi-studybuddy 自管
  ├ global.db                         ← 全局库（学期注册表 + backup_records + parent_report_targets）
  ├ semester/
  │  └ <semester-id>/
  │     ├ sem.db                      ← 学期库（course_instances/assessment_attempts/...）
  │     └ storage/                    ← 资料文件（storage_key 指向此处）
  ├ memory/                           ← 三层记忆
  │  ├ l1/learner-profile.json        ← L1 学习者画像
  │  ├ l2/wiki-index/                 ← L2 知识库索引
  │  └ l3/conversation.sqlite         ← L3 会话检索（FTS5）
   ├ config/
   │  ├ models.json                    ← 默认模型选择（__studybuddy_managed 标记，T-M3-005）
   │  └ credentials.json                ← credential-vault DPAPI 加密 JSON（safeStorage 密文 base64）
   └ ...                               ← 不使用独立 credential-vault/*.enc 文件树
```

**隔离原则**（prep §一第 8 行 + TRD §7 决策 3）：
- pi 会话目录 `~/.pi` 由 pi 自管，pi-studybuddy 不侵入
- 业务数据根 `%LOCALAPPDATA%\PiStudyBuddy` 存学期注册表/semester.db/家长报告/学情
- 密钥由 `src/main/credential-vault.ts` 通过 safeStorage/DPAPI 加密后写入业务数据根 `config/credentials.json`；键名仍为 `modelProvider:xxx`/`parentContact:xxx`（从 pi-desktop 的 `channel:xxx` 改名）

### 4.2 三层记忆（借鉴 inno-agent，prep §三第 2 行）

#### L1 学习者画像

**借鉴**：inno-agent `src/memory/learner/`（profile-store.ts + auto-profile.ts + context-pack.ts）

**pi-studybuddy 落地**：
- `profile.json` + `events.jsonl` 持久化
- 画像字段映射 StudyBuddy 学习者模型（学科/学段/可用时间表/目标分数/薄弱点），**不照搬 inno-agent 通用画像**
- `auto-profile.ts` 自动从 StudyEvent 提取画像更新
- `context-pack.ts` 在 `before_agent_start` 注入系统提示词

#### L2 知识库（BM25 + 知识图谱）

**借鉴**：inno-agent `src/memory/l2/`（l2-search.ts 实现 BM25 词法候选 30→前 8 作图谱种子→一跳图谱扩展）

**pi-studybuddy 简化**（prep §三装配纪律影响第 4 行）：
- 个人学习场景图谱规模小，可先只做 **BM25 + DIRECT_LINK**（权重 0.5）
- SOURCE_OVERLAP(0.4)/ADAMIC_ADAR(0.3)/TYPE_AFFINITY(0.1) 视后续需要再开
- Simple Mode 关闭 L2

#### L3 会话检索（SQLite FTS5 bigram）

**借鉴**：inno-agent `src/memory/l3/`（sqlite-store.ts 基于 `node:sqlite`，Node ≥ 22.5）

**pi-studybuddy 直接复用**：
- schema：`chunks` + `chunks_fts`（FTS5/unicode61）+ 预留 `embeddings`
- CJK 切 **bigram**（学习计划→学习 习计 计划）
- ASCII 整词小写，OR-combined MATCH
- `recall.ts` 阈值门控
- `indexer.ts` 基于 `last_offset + last_mtime_ms` 增量（turn_end 钩子触发）

### 4.3 全局库 global.db

**表**（02-PRD §3.2/§3.7/§3.10）：
- `semesters`：学期索引（含 `db_relative_path`/`ready` 标志）
- `parent_report_targets`：家长报告目标配置
- `backup_records`：备份历史（课程 ID/备份时间/目标路径/content_hash/备份类型[manual/scheduled/pre_archive/post_archive]/状态）

### 4.4 学期库 semester.db

**表**（02-PRD §3.2-§3.6 数据契约要点）：
- `course_instances` / `assessment_attempts`（含 confirmation_status/confirmed_at）
- `schedule_entries` / `study_tasks` / `study_events`（source_system S1-S7）
- `materials` / `normalized_texts` / `structured_notes` / `mind_maps` / `knowledge_modules` / `material_chunks` / `jobs`
- `questions` / `practice_sessions` / `practice_answers`
- `mistakes`（UNIQUE(question_id)）/ `mistake_evidence`（UNIQUE(source_practice_answer_id)）/ `weak_points`（UNIQUE(course_instance_id, knowledge_module_id)）
- `mock_exam_papers` / `mock_exam_questions` / `mock_exam_attempts` / `mock_exam_answers` / `mock_exam_module_analyses`
- `parent_reports`（PK report_key）/ `report_deliveries`（PK report_key+channel）

**触发器**：
- 6 个关系一致性触发器校验 question/course/module/answer 关系（S4 数据完整性核心）
- storage_key 路径逃逸防护触发器（拒绝 `..`/`:\`/`:/`）
- mock_exam_papers 触发器校验 assessment_attempt 必须 confirmed
- mock_exam_questions CHECK 约束选择题 vs 填空题字段互斥

### 4.5 credential-vault（DPAPI 密钥库）

**借鉴 pi-desktop**（prep §四第 9 行）：`src/main/credential-vault.ts`

**pi-studybuddy 落地**：
- `import { safeStorage } from "electron"`
- `safeStorage.isEncryptionAvailable()` 校验后用 `safeStorage.encryptString`/`decryptString`
- Windows 上 `safeStorage` 后端即 DPAPI
- 写文件 `mode: 0o600`（原子写：temp + rename）
- 键格式严格校验：`/^modelProvider:[a-z0-9._-]{1,160}$/i` 和 `/^parentContact:[a-z0-9._-]{1,160}$/i`（从 pi-desktop 的 `channel:xxx` 改名）

---

## 5. 技能体系设计

> 输入：prep §二（pi-skills）、prep §三（inno-agent content-source）、02-PRD §3.9（TTS skill）。

### 5.1 学习技能包体系（自建，与 pi-skills 同构）

**与 pi-skills 同构**（prep §二装配纪律影响第 2 行）：
- 同 frontmatter：`name` + `description`（极简，与 pi 生态原生兼容）
- 同 `{baseDir}` 占位符引用 helper 脚本
- 同扁平目录（一层深，README:43 "only looks one level deep for SKILL.md"）
- 同 helper 脚本模式（不预读入 prompt，仅执行时调用）
- 同 progressive disclosure（description 常驻，正文按需加载）

**pi-skills 缺失的三项纪律（pi-studybuddy 必须补）**：
1. **显式 `## Out of Scope` 章节**：每个技能明确不做什么
2. **frontmatter 版本与依赖声明**：扩展 `version` + `requires`（如 `requires: node>=20, python>=3.10, whisper.cpp`）
3. **单件测试夹具**：每个引入技能写夹具（pi-skills 自身无测试）

**统一章节名**（prep §二第 2 行）：
```
## When to Use      （触发条件）
## Usage            （流程）
## Output           （输出格式）
## Gotchas          （陷阱）
## Out of Scope     （不做什么，pi-studybuddy 必补）
```

### 5.2 引入的 pi-skills（prep §二装配纪律影响第 4 行）

| 技能 | 来源 | 处置 |
|---|---|---|
| `youtube-transcript` | pi-skills 直接采用 | 学生看教学视频转讲义是核心场景；video-id/URL→带时间戳字幕 |
| `brave-search` | pi-skills 直接采用 | 学生查资料/查文档；API key 走 credential-vault（免费层需信用卡，可能换 Bing/Google 或走代理） |
| `transcribe` | pi-skills 取设计模式，实现重做 | 仅 Apple Silicon macOS，pi-studybuddy 在 Windows 需自建等价物（whisper.cpp）；"本地优先、无云端、无 API key"边界设计保留 |
| `browser-tools` | pi-skills 取 content 子能力 + CDP 设计模式 | 只引入 `browser-content.js`（Readability+Turndown 提取）；用于"在线题库/学习平台"窄场景 |
| `gccli`/`gdcli`/`gmcli`/`vscode` | 默认不引入 | 与学生学习工作台关联弱 |

### 5.3 自建学习技能包（studybuddy-* 系列）

| 技能包 | 用途 | 引擎依赖 |
|---|---|---|
| `studybuddy-tts` | TTS 朗读（SAPI 默认 + edge-tts 可选） | SAPI（系统自带）/ edge-tts（需网络） |
| `studybuddy-ocr-schedule` | 课程表 OCR 识别预览 | OCR venv（onnxruntime/PIL） |
| `studybuddy-wps-convert` | doc/ppt/xls 转 docx/pptx/xlsx | WPS COM（pywin32） |
| `studybuddy-whisper` | 受控 PCM WAV 转写 | whisper.cpp |
| `studybuddy-format-pdf` | PDF 转换 | pdf-parse |
| `studybuddy-format-docx` | DOCX 转换 | jszip + mammoth |
| `studybuddy-format-pptx` | PPTX 转换 | jszip |
| `studybuddy-format-xlsx` | XLSX 转换 | jszip 提取 sharedStrings |
| `studybuddy-format-odt-ods-odp` | ODF 格式提取 | jszip |
| `studybuddy-format-rtf` | RTF 提取 | 自写剥离 |
| `studybuddy-format-epub` | EPUB 提取 | jszip |

### 5.4 content-source 技能中心（借鉴 inno-agent，prep §三第 3 行）

**借鉴**：inno-agent `src/content-source/index.ts` 的 `createContentSource(hub)` 根据 `hub.type` 返回 `GitHubContentSource` 或 `BundleServiceSource`。

**pi-studybuddy 落地**：
- **GitHub hub 路径直接复用**：Git Trees API（recursive=1）取整树，缓存 5 分钟；文件从 raw.githubusercontent.com 拉取，带 token + 429/5xx 指数退避
- `isSafeItemName` 路径安全校验
- `CATEGORY_MARKER`（SKILL.md/preset.json）识别
- **bundle 服务**：面向私有部署，pi-studybuddy 单机桌面可暂不实现，留扩展点
- **内置兜底预设**：`presets/lesson-plan`、`presets/exam-cram`、`presets/error-review` 等
- **工作区级私有技能** `<workspace>/.skills/` 自动发现

### 5.5 skills.manifest.json（pi-skills 缺失，pi-studybuddy 补）

**设计**（prep §二第 5 行）：pi-skills 无 manifest/registry 文件，技能发现纯靠目录扫描。

**pi-studybuddy 补**：生成 `skills.manifest.json`（name/description/version/deps），便于：
- 启动校验（技能完整性 + 依赖可用性）
- 按需加载（progressive disclosure 索引）
- **漂移教训**（prep §二第 3 行）：禁止 README 手维护清单，CI 强制 manifest 与目录扫描一致

### 5.6 技能目录结构

```
~/.pi/agent/skills/                   ← pi 技能根
  ├ studybuddy-tts/
  │  ├ SKILL.md                       ← frontmatter(name+description+version+requires) + 正文 5 章节
  │  ├ speak.js                       ← helper 脚本（{baseDir}/speak.js）
  │  └ package.json
  ├ studybuddy-whisper/
  │  ├ SKILL.md
  │  ├ transcribe.js
  │  └ package.json
  ├ youtube-transcript/               ← pi-skills 引入
  │  ├ SKILL.md
  │  ├ transcript.js
  │  └ package.json
  └ brave-search/                     ← pi-skills 引入
     ├ SKILL.md
     ├ search.js
     ├ content.js
     └ package.json

<workspace>/.skills/                  ← 工作区级私有技能（自动发现）
  └ my-custom-skill/
     └ SKILL.md
```

---

## 6. 桌面壳架构（pi-desktop 五件骨架）

> 输入：prep §四（pi-desktop）、TRD §7 决策 2（自建业务化壳）。Apache-2.0 允许 fork 但会携带无关功能与技术债，故取五件骨架直接搬运改名。

### 6.1 五件架构骨架（直接搬运改名）

| 骨架 | pi-desktop 来源 | pi-studybuddy 落点 |
|---|---|---|
| **三进程** | `src/{main,preload,renderer}` + `agent-host` | `src/{main,preload,renderer}` + `agent-host`（业务化） |
| **contract 类型化 IPC** | `src/contract/{api,rpc,desktop,browser,types}.ts` | `src/contract/{api,rpc,desktop,types}.ts`（删除 browser，无内置浏览器） |
| **credential-vault** | `src/main/credential-vault.ts` | `src/main/credential-vault.ts`（键名改 modelProvider/parentContact） |
| **toolchain 发现** | `shared/toolchains/` + `main/toolchains/` | `shared/toolchains/` + `main/toolchains/`（OCR venv/whisper.cpp 依赖） |
| **file-watch** | `src/agent-host/file-watch.ts` | `src/agent-host/file-watch.ts` |

### 6.2 三进程 + agent-host

**借鉴 pi-desktop**（prep §四第 1-3 行）：

```
src/
  ├ main/              ← 窗口/托盘/协议/Host 监督（No business logic）
  │  ├ main.ts
  │  ├ window.ts       ← BrowserWindow sandbox:true
  │  ├ protocol.ts     ← app:// 自定义协议 + 严格 CSP
  │  ├ ipc.ts          ← desktop:* IPC 处理
  │  ├ credential-vault.ts
  │  ├ toolchains/     ← 发现-探测-安装-绝对路径
  │  └ host-manager.ts ← utilityProcess.fork(agent-host)
  ├ preload/
  │  └ preload.ts      ← 仅 contextBridge.exposeInMainWorld("piBridge", bridge)
  ├ renderer/           ← React 19 + Vite
  │  └ ...（业务化 UI，见 09-UI）
  ├ agent-host/         ← utilityProcess，pi coding agent + 业务工具
  │  ├ index.ts        ← process.parentPort 收消息，createRpcServer() 提供服务
  │  ├ studybuddy-extension-loader.ts  ← 加载 studybuddy-extension
  │  ├ session-*/      ← 会话管理（reader/history/index/cache/watcher）
  │  └ handlers/       ← 业务化层（学科/学习计划/错题/学情独立成模块）
  ├ contract/           ← 类型化 IPC 契约
  │  ├ api.ts          ← interface Api（~50 方法）
  │  ├ rpc.ts          ← 自研轻量 MessagePort RPC（< 200 行，无依赖）
  │  ├ desktop.ts      ← PiBridge 接口（renderer↔main IPC 表面）
  │  └ types.ts
  └ shared/            ← 跨进程共享类型
```

### 6.3 自研 RPC 层

**借鉴 pi-desktop**（prep §四第 5 行）：`src/contract/rpc.ts`，自研"轻量 MessagePort RPC，无外部框架"。

**五种 wire 消息**：`request` / `response` / `subscribe` / `unsubscribe` / `event`

**API**：
- `createRpcServer()` 在 agent-host 内 `attachPort(MessagePort)`
- `createRpcClient(port)` 在 renderer 提供 `call(method, ...args)` 和 `subscribe(topic, key, on)`
- `AnyMessagePort` 兼容 DOM MessagePort / utilityProcess / Node worker_threads

**MessagePort 经主进程转发**（prep §四第 6 行）：
- preload 接收 `desktop:host-port` IPC 事件，把 MessagePort transfer 给页面
- main 在 `desktop:connect-host` 处理函数中 `manager.createRendererChannel()` 创建 `MessageChannelMain`

### 6.4 安全骨架（不变量必须保留）

**借鉴 pi-desktop**（prep §四第 7-9 行 + 装配纪律影响第 4 行）：

| 不变量 | pi-desktop 实现 | pi-studybuddy 落地 |
|---|---|---|
| `sandbox: true` | `window.ts:36-42` webPreferences | ✅ 直接复用 |
| 严格 CSP | `protocol.ts:11-25` CSP 常量 | ✅ 直接复用（default-src 'self' app:; script-src 'self' app:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'） |
| preload 受控桥接 | `preload.ts:223-225` 仅 exposeInMainWorld("piBridge", bridge) | ✅ 直接复用（PiBridge 白名单接口） |
| credential-vault 用 safeStorage | `credential-vault.ts:1` import { safeStorage } | ✅ 直接复用（键名改 modelProvider/parentContact） |
| Host RPC 契约化 | `contract/{api,rpc}.ts` | ✅ 直接复用 |
| HTML 预览独立 CSP | `HTML_PREVIEW_CSP`（form-action 'none'） | ✅ 直接复用（学情报告/笔记预览） |

**不变量校验脚本**（prep §四装配纪律影响第 4 行）：pi-studybuddy 必须有等价的 `check-desktop-security.mjs` 风格不变量校验脚本，硬断言上述六条。

### 6.5 toolchain 发现-探测-安装-绝对路径

**借鉴 pi-desktop**（prep §四第 12-14 行）：

**TOOL_CAPABILITY_IDS**（prep §四第 12 行）：
```
["shell.bash","shell.powershell","vcs.git","js.node","js.npm","js.npx","js.bun",
 "python.interpreter","python.uv","python.uvx","search.rg","search.fd",
 "data.jq","network.curl"]
```

**四段式**：
1. **发现**：`discovery-registry.ts` 扫描系统 PATH
2. **探测**：`probes/node.ts`（MINIMUM_NODE_VERSION="22.19.0"，MAXIMUM_VERIFIED_NODE_MAJOR=24，health=unsupported/unverified/healthy）
3. **安装**：安装到 `app.getPath("userData")`，不修改系统 PATH/注册表
4. **绝对路径执行**：`toolchain-runtime.ts` 的 `prependPath(env, directories, platform)` 把托管工具目录前缀到 PATH

**OCR venv/whisper.cpp 依赖**：调用必须走"统一绝对路径"，否则 Windows PATH 不全时极易失败。

**内置 ripgrep/fd**（prep §四第 14 行）：`["search.rg","search.fd"]` 必须有 `bundled` provider 且 `healthy`，学习资料/笔记本地搜索基础能力，离线可用。

**窗口 focus 重扫**：60s TTL，窗口 focus 时重扫。

### 6.6 文件体验

**借鉴 pi-desktop**（prep §四第 15 行）：

- **项目目录选择**：`desktop:select-directory`→`dialog.showOpenDialog`，记录 `recentCwds`（最多 12 条）
- **文件浏览**：`FileExplorer.tsx` lazy 加载
- **@文件引用**：`allowed-roots.ts` 校验 + `session-file-references.ts` 跟踪
- **Markdown 预览**：react-markdown + remark-gfm + remark-math + rehype-katex + rehype-raw + rehype-sanitize + SyntaxHighlighter
- **Mermaid**：`mermaid` 包
- **docx 预览**：`mammoth` + DOCX_PREVIEW_MAX_BYTES
- **文件变更监听**：`file-watch.ts` 的 `fs.watch({ recursive: true }, emitChange)` 100ms 防抖→`Streams["files.changed"]`

**学习场景硬需求**：Markdown + KaTeX 是公式渲染硬需求，技术栈直接复用；学生 `@` 引用学习资料/错题截图是核心交互。

### 6.7 会话管理（默认主入口，pi 原生 AI 对话承载）

**借鉴 pi-desktop**（prep §四第 11 行）：

- **API 层**：`sessions.list/get/context/rename/delete/export`
- **Host 层**：session-reader（读 ~/.pi/agent/）、session-index、session-content-cache、session-history（分页 cursor 用 `dev+ino+birthtimeMs` 哈希防陈旧）
- **UI 层**：SessionSidebar（按日期分组、模糊搜索、unread 计数）
- **流式回复**：通过 `Streams["agent.events"]`
- **工具调用视图**：`countToolCallBlocks`
- **上下文压缩状态**：`onContextUsageChange`

**pi 原生 AI 对话是默认主入口**（02-PRD §3.11 + 09-UI §4.2）：
- 应用启动即默认打开"💬 对话"标签页——这是 pi-studybuddy 作为"专属 studybuddy"的根基，**不废弃 pi 原生对话能力**
- 会话即"💬 对话 Tab"的内容：左侧栏选中会话，主内容区对话 Tab 加载该会话
- 学生在对话里零碎问答（"帮我理解极限定义"/"这题怎么做"），AI 可自主调用 S1-S7 + TTS + 备份恢复全部 registerTool 工具
- **双层并存**：对话 Tab（自由探索）+ S1-S7 标签页（结构化工具）数据贯通
- 对话与 S1-S7 闭环的关系：对话是"任意入口"，S1-S7 是"闭环路径"——学生可从对话零碎提问开始，AI 调用工具把学生引入闭环（如对话中出题 → 跳转练习 Tab）

**pi-studybuddy 业务化**（prep §四装配纪律影响第 3 行）：会话语义从 coding agent 对话改为学习对话——需附加学科标签/学习目标/错题关联。

### 6.8 省略的 pi-desktop 组件

**依据 prep §四装配纪律影响第 3 行 + §五.2**：

| pi-desktop 组件 | pi-studybuddy 处置 | 理由 |
|---|---|---|
| Plugins | **省略** | 不让学生接触 pi 插件机制 |
| Skills.sh | **替换为学习技能包** | pi 的 Skills.sh 面向开发者，学生需要"学科/章节/题型模板"语义 |
| 内置浏览器（WebContentsView） | **视需要** | TRD §7 决策 2：学生端以本机内容为主，浏览能力按需；若要做"在线题库/学习网站"必须照 pi-desktop 实现 |
| 微信/Telegram/飞书渠道 | **省略** | 桌面单机无此需求；家长报告走本地导出 + 可选邮件/打印 |

---

## 7. 调度层设计

> 输入：02-PRD §3.10（备份恢复定期调度）、prep §三（inno-agent cron-scheduler）。

### 7.1 cron-scheduler（借鉴 inno-agent，prep §三第 5 行）

**借鉴**：inno-agent `src/scheduler/cron-scheduler.ts` 的 `CronScheduler`。

**核心机制**：
- 进程内 `setInterval` 每 60 秒 tick（首次延迟 5 秒）
- 每 tick 遍历 `JobStore.list()`，跳过 disabled 和已在运行的（`this.running` Set 防重叠）
- `isCronDue(cron, timezone, lastRunAt, now)` 判断到期
- `executeJob` 调 `runPromptSerialized(prompt)`
- 一次性 cron 执行后自动 `enabled=false`
- 持久化：`jobs.json` + `runs.jsonl`

### 7.2 学习相关 taskType（借鉴 inno-agent）

**inno-agent 枚举**（prep §三第 5 行）：`daily_review`/`weekly_summary`/`learner_profile_reflection`/`spaced_review`/`push_reminder`/`custom_prompt`

**pi-studybuddy 借鉴**：
- `spaced_review`：艾宾浩斯复习（直接契合学习工作台）
- `daily_review`：每日总结
- `weekly_summary`：周报
- `learner_profile_reflection`：L1 画像反思
- `backup_course`：**备份恢复定期调度**（02-PRD §3.10，每周一/每月一）

### 7.3 备份恢复调度

**设计**（02-PRD §3.10）：
- **默认每周一自动执行**（cron `0 0 * * 1`，周一 00:00）
- 学生可配置为每月一（cron `0 0 1 * *`，每月 1 日 00:00）
- 调度任务写 `backup_records`（备份类型 `scheduled`）
- **归档前后强制触发**完整备份（所有课程，备份类型 `pre_archive`/`post_archive`）
- **手动触发**：学生随时手动触发某门课程或全部课程备份（备份类型 `manual`）

### 7.4 推送目标（大幅简化 inno-agent channels）

**inno-agent**（prep §三第 4 行）：飞书/微信/QQ 多渠道回推 + PersonalChannelDispatcher + 流式卡片。

**pi-studybuddy 简化**（prep §五.2）：
- 整体删除 feishu/wechat/bridge 具体实现
- 保留 `ChatChannel`/`ChannelRegistry` 接口抽象（便于未来扩展）
- 推送目标改为**桌面通知 + 应用内消息中心**
- scheduler 的 channel 枚举同步替换

---

## 8. 安全与不变量

> 输入：01-TRD §5（安全与隐私边界）、02-PRD §5（家长报告边界与隐私）、prep §三（workspace-path-guard）、prep §四（pi-desktop 安全骨架）。

### 8.1 workspace-path-guard（路径守卫，必须）

**借鉴 inno-agent**（prep §三第 7 行）：详见 §3.4。

**边界**：业务数据根 `%LOCALAPPDATA%\PiStudyBuddy` 是工作区边界；符号链接逃逸、`~`/`file://`/Unicode 空格边角必须处理。

### 8.2 check-desktop-security.mjs 风格不变量校验

**借鉴 pi-desktop**（prep §四装配纪律影响第 4 行）：`scripts/check-desktop-security.mjs:75` 硬断言。

**pi-studybuddy 必须有的不变量**（六条，§6.4）：
1. `sandbox: true`（BrowserWindow webPreferences）
2. 严格 CSP（default-src 'self' app:; ...）
3. preload 仅 `contextBridge.exposeInMainWorld("piBridge", bridge)`
4. credential-vault 用 `safeStorage`
5. Host RPC 契约化（contract/api.ts + rpc.ts）
6. HTML 预览独立 CSP（form-action 'none'）

### 8.3 资料导入安全

- **zip 炸弹防护**：条目/解压比限制
- **MIME 严格匹配**：不信任浏览器 MIME（S7 服务端重新验证文件头）
- **不解析宏文档**：xlsm/docm/pptm 明确提示不解析
- **路径逃逸防护**：storage_key 相对路径，触发器拒绝 `..`/`:\`/`:/`
- **zip 澄清**（02-PRD §6）：资料导入拒绝压缩包（zip/7z/rar 当学习内容解析），备份恢复用 zip 作容器不冲突

### 8.4 隐私边界（02-PRD §5）

- **API 信封**：`{ success, data, error }`，统一 6 错误码，中文可操作消息
- **仅 127.0.0.1**：无公网入口；loopback Origin 策略
- **AI 日志 allowlist**（02-PRD §5.3）：非 allowlist 字段抛错
- **UUID 泄漏检测**（02-PRD §5.2）：`assertNoSensitiveLeak` 序列化整个 ParentReportResult，UUID 正则检测
- **家长报告脱敏**：禁止读取/输出资料原文/题干/答案/作答/错因/完整 UUID
- **S7 原始音频**：只暂存 tmp，finally 清理，不进日志/StudyEvent/S6 报告

### 8.5 日志脱敏

- **日志根与受保护根互不包含**：拒绝符号链接
- **单文件 5MiB 轮转保留 3 份**
- **不记录**：API Key、输入全文、输出全文、学生隐私正文、完整 UUID、Provider URL
- **允许字段**（02-PRD §5.3）：event/level/taskType/provider/model/tokenUsed/latencyMs/fallbackUsed/errorCode/timestamp
- **字符串值最大 128 字符**；`errorCode` 必须匹配 `^[A-Z][A-Z0-9_]{1,63}$`

---

## 9. 装配纪律映射（五阶段 → 架构组件）

> 输入：docs/00 §四（五阶段组件治理）、prep §一-§四装配纪律影响。

### 9.1 五阶段与架构组件对应表

| 阶段 | 架构组件 | 产物 |
|---|---|---|
| **1. 下载储存** | pi（npm peerDependencies 5 件套）、pi-skills（git clone）、pi-desktop（Apache-2.0 骨架）、inno-agent（MIT 范本）、OCR venv、whisper.cpp | `H:\pi-references\*` + `node_modules` + venv |
| **2. 单件测试** | 每个学习工具（registerTool 契约断言）、每个引入技能（夹具）、WPS COM 桥、whisper.cpp Adapter、OCR venv Adapter、TTS skill | 独立冒烟 + 合成夹具 |
| **3. 集成测试** | studybuddy-extension 与 pi 底座对接契约验证、`createAgentSession({ customTools })` 拼装真实 pi-ai provider、工具与 pi.on 钩子协作 | 与 pi 底座对接契约验证 |
| **4. 系统配件组装** | 进入主仓 `src/agent/studybuddy-extension.ts` + `src/agent/adapters/` + `src/main/` + `src/agent-host/` + `src/contract/` + `~/.pi/agent/skills/` | Adapter/扩展 |
| **5. 系统冒烟 + 系统 E2E** | S1-S7 全链路、TTS 跨子系统、备份恢复、家长报告脱敏、workspace-path-guard、credential-vault | 全链回归 |

### 9.2 骨架稳定、业务可演化原则

**装配顺序**（prep §四装配纪律影响第 5 行）：
1. 先落地"main + preload + renderer + agent-host"四进程骨架与 `contract/` 契约（可逐字搬运）
2. 再叠加 toolchain 发现 / credential-vault / file-watch 三个公用零件
3. 最后才在其上自建学习业务模块

**原则**：避免业务与壳耦合，确保五阶段治理中"壳层稳定、业务可演化"。

### 9.3 参考仓库本身也按此纪律治理

**依据 v2 Prompt §二装配纪律**：四个参考仓库本身也只处于"下载储存"阶段（`H:\pi-references\*`），引用其结论必须先回填到 pi-studybuddy 的有效编号文档（本 03-Architecture + prep-参考点核对表），再独立设计决策，不得直接把参考代码复制进主仓。

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
| v0.1.3 | 2026-08-09 | 交叉审查修订：修正 credential-vault 实际拓扑为 `config/credentials.json`，并明确生产模型运行时从业务数据根配置与 DPAPI 解密凭证构造，不读取 `~/.pi`。 |
| v0.1.2 | 2026-08-08 | §2.3 model_select 行落点修订：`~/.pi/agent/models.json` → `<dataRoot>/config/models.json`（T-M3-005 裁决 1，AGENTS.md §9.5 物理隔离；supersedes 注记见 §2.3 表后） |
| v0.1.1 | 2026-08-07 | §6.7 会话管理补"pi 原生 AI 对话是默认主入口"——应用启动即默认打开"💬 对话"标签页，会话即对话 Tab 内容，学生零碎问答 AI 自主调用 S1-S7+TTS+备份恢复工具，对话 Tab（自由探索）+ S1-S7 标签页（结构化工具）双层并存（02-PRD §3.11 + 09-UI §4.2 贯通） |
| v0.1.0 | 2026-08-07 | 初始草案：四层架构总览（桌面壳/pi 扩展/业务 Adapter/数据层）；pi 扩展层（单一 extension factory + registerTool + pi.on 钩子 + pi-ai provider + Simple Mode）；业务 Adapter（S1-S7 + TTS + 备份恢复工具清单 + WPS COM/whisper.cpp/OCR 桥 + workspace-path-guard + observability）；数据层（物理隔离 + 三层记忆 + global.db + semester.db + credential-vault）；技能体系（学习技能包同构 + 引入 pi-skills + content-source + skills.manifest）；桌面壳五件骨架（三进程 + contract + RPC + 安全 + toolchain + file-watch）；调度层（cron-scheduler + 备份恢复 + 学习 taskType）；安全与不变量；装配纪律映射。输入：prep-参考点核对表 + 02-PRD + 01-TRD |

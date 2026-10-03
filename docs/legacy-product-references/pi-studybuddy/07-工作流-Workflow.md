# 07 工作流设计

**版本**：v0.1.3
**日期**：2026-08-09
**状态**：✅ 已审查批准；T-M5-011 执行中。

> 当前唯一执行顺序：开发机从空数据走 S1 → S2 资料/笔记 → S3 → S4 → S5 → S6/S7/TTS/备份，逐步修复并重启回读；开发机闭环后再复制到使用机。
**上游**：[02-PRD v0.1.4 §3](./02-PRD-产品需求-Product-Requirements.md)、[03-Architecture v0.1.3 §3/§7](./03-架构设计-Architecture-Design.md)、[05-ERD v0.1.2](./05-数据模型-ERD-Data-Model.md)、[06-API v0.1.6](./06-API契约-API-Contracts.md)
**下游**：08-Test、09-UI

---

## 1. 概述

### 1.1 工作流分类

| 分类 | 工作流 | 触发者 | 章节 |
|---|---|---|---|
| **通用 AI 对话路径** | pi 原生对话（默认主入口，零碎问答 + AI 自主调用工具） | 学生随时触发 | §2.8 |
| **学生主路径** | S1-S7 核心闭环 | 学生主动操作 | §2.1-§2.7 |
| **家长报告路径** | 生成→冻结→投递→重试 | 学生触发 / 调度自动 | §3 |
| **TTS 朗读路径** | 随时可击发朗读 | 学生随时触发 | §4 |
| **备份恢复路径** | 手动/定期/归档触发备份 + 恢复 | 学生触发 / 调度自动 / 归档强制 | §5 |
| **组件治理流程** | 五阶段组件装配 | 开发阶段 | §6 |
| **调度层** | cron-scheduler 主动任务 | 系统自动 | §7 |

> **对话路径与主路径的关系**：对话是"任意入口"（自由探索），S1-S7 主路径是"闭环路径"（结构化工具）。学生在对话里零碎提问，AI 可自主调用 S1-S7 工具把学生引入闭环（如对话中出题 → 跳转练习 Tab）。两者数据贯通，详见 02-PRD §3.11 + 09-UI §4.2。

### 1.2 工作流设计原则（铁律）

1. **证据驱动闭环**：每个环节产出 StudyEvent 写入时间线，下一环节只读上一环节事实，**不反写历史**
2. **规则优先、AI 辅助**：日期/统计/去重/状态/批改由确定性规则负责，AI 只负责受约束生成或润色
3. **学生确认是事实成立的必要条件**：考试日期/错因/掌握状态等必须学生确认
4. **AI 失败降级为确定性规则输出**：不阻塞学生操作
5. **幂等归档**：重复扫描不重复建（mistake UNIQUE(question_id)、mistake_evidence UNIQUE(source_practice_answer_id)）
6. **防泄露**：作答前 DTO 不含 correct_answer/acceptable_answers/explanation
7. **脱敏**：家长报告绝不包含原文/题干/答案/作答/错因/完整 UUID

### 1.3 工作流与 API 映射

每个工作流步骤标注调用的 RPC 方法（06-API）和写入的数据表（05-ERD）。

---

## 2. 学生主路径（考试驱动学习闭环）

### 2.1 闭环全景

```
学期初始化(S1) → 资料笔记(S2) → 知识模块(S2)
                                      ↓
限时练习(S3) ← ← ← ← ← ← ← ← ← ← ←
  ↓ (is_correct=false)
错题改错(S4) → 薄弱点回流
  ↓
期末冲刺(S5: 模拟考/临考速背/冲刺计划)  ←已确认考试驱动
  ↓
课堂采集(S7: 录音转写→S2 handoff)
```

### 2.2 S1 学期初始化流程

**触发**：学生首次打开应用 / 新学期开始

```
1. 学生调用 semesters.create({label, startDate, endDate, timezone})
   → 写 global.db:semesters（status=active, ready=0）
   → 初始化 semester/<id>/sem.db

2. 学生调用 courses.create({semesterId, courseName, subject, ...})
   → 写 sem.db:course_instances

3. 学生调用 courses.importSchedule({courseId, imageFile})
   → OCR venv 识别课表图片 → 返回 SchedulePreview（不落库）
   → 学生确认预览
   → 原子化批量 schedule.create() 写 schedule_entries
   → 写 study_events（event_type=semester_initialized, source_system='S1'）

4. 学生持续补全考试：exams.add({courseId, examName, examType, scheduledDate, source, confidence?})
   → 写 assessment_attempts（confirmation_status=pending）
   → 未确认考试不驱动冲刺

5. 学生确认考试：exams.confirm({id, confirmed: true})
   → 写 confirmation_status=confirmed, confirmed_at, confirmed_by='student'
   → 写 study_events（event_type=exam_confirmed）
   → semesters.update({id, ready: 1}) 标记学期就绪
```

**关键约束**：
- 考试确认四态：`pending / confirmed / rejected / superseded`
- 补考不重建课程（原 course_instance 下新增 attempt）；重修新学期建新 course_instance 关联 `retake_of`
- 学期状态机：`active → teaching_ended → follow_up → archived`（归档前后强制触发完整备份，见 §5.4）

**错误处理**：
- OCR 识别失败 → 返回 BAD_REQUEST + 中文消息"课表识别失败，请重新上传清晰图片"；学生可手动录入课表
- 学期库初始化失败 → 返回 INTERNAL_ERROR + 回滚 semesters 记录

### 2.3 S2 资料笔记流程

**触发**：学生选课程后上传资料

```
1. 学生调用 materials.upload({courseId, file})
   → 服务端 MIME 验证（不信浏览器）
   → storage_key 相对路径落盘（触发器拒绝 ../:/路径逃逸）
   → 写 materials（status=pending, source_type=upload）
   → 写 study_events（event_type=material_uploaded, source_system='S2'）

2. 学生调用 materials.convert({id})
   → 写 jobs（status=pending, job_type=convert_*）
   → 按 file_type 分派转换器：
     - pdf → pdf-parse
     - docx → jszip + mammoth
     - pptx → jszip
     - xlsx → jszip 提取 sharedStrings
     - doc/ppt/xls → WPS COM 桥（pywin32 子进程）转中间格式 → 再走现有管道
     - image → OCR venv（onnxruntime/PIL）
     - odt/ods/odp/rtf/epub → jszip/自写剥离
   → 转换成功：写 normalized_texts + materials.status=converted
   → 转换失败：materials.status=conversion_failed + jobs.status=failed

3. 学生调用 materials.generateNote({id})
   → 写 jobs（status=pending, job_type=generate_note）
   → AI 生成：structured_notes（Markdown + highlights）+ mind_maps（Markmap）+ knowledge_modules（带 source_evidence 回链）
   → 写 materials.status=note_generating → completed
   → 写 study_events（event_type=note_generated, source_system='S2'）

4. AI 不可用时：
   → materials.status=pending_quality_check
   → 保留 normalized_text 供学生查看原文
   → 学生可 retryAiGeneration（最多 3 次）或 replaceText（手动粘贴纯文本跳过转换）

5. 学生手动编辑：notes.update({materialId, noteMarkdown, highlights?})
6. 学生查看导图：notes.getMindMap({materialId})
7. 学生更新模块学习状态：modules.updateLearnStatus({id, learnStatus})
   → 状态机：not_started → learning → mastered → needs_review
```

**关键约束**：
- Material 状态机：`pending → converting → converted → note_generating → completed`（失败分支 `conversion_failed` / `pending_quality_check`）
- 知识模块**必须带 source_evidence 回链**（降低幻觉）
- 失败恢复：retry-conversion / retry-ai-generation（最多 3 次）/ replace-text
- S7 handoff：课堂转写文本创建 `file_type='text'` material，初始 `converted`，不自动建 Job

**错误处理**：
- WPS COM 桥崩溃 → 子进程隔离，主进程不受影响；返回 INTERNAL_ERROR + "文档转换失败，请检查文件是否损坏或 WPS 是否运行"
- AI 生成超时 → 保留 normalized_text + pending_quality_check，不阻塞查看原文

### 2.4 S3 限时练习流程

**触发**：学生选 1-10 个知识模块开始练习

```
1. 学生调用 practice.createSession({courseId, moduleIds, questionCount, timeLimit?, difficulty?, questionTypes?})
   → 校验 questionCount 5-20
   → 同步调 AI 生成客观题（单选 60%/多选 20%/填空 20%）
   → AI 失败 → 不创建空 session，返回 INTERNAL_ERROR
   → AI 成功 → 写 questions（含 correct_answer/acceptable_answers/explanation，但 DTO 隔离）+ practice_sessions（status=in_progress）
   → 前端开始计时（Streams["practice.timer"]）

2. 学生调用 practice.getQuestions({sessionId})
   → 返回 QuestionDTO[]（不含 correct_answer/acceptable_answers/explanation，防泄露）

3. 学生逐题作答（前端计时，限时可超时标记但不锁屏）

4. 学生调用 practice.submit({sessionId, answers})
   → 触发规则批改（非 AI）：
     - 单选：精确匹配
     - 多选：全选 deepEquals
     - 填空：normalize（trim+全角转半角+统一大小写+去多余空格，支持多等价答案 OR）
   → 写 practice_answers（含 is_correct）+ practice_sessions（status=submitted→graded, total_score, correct_count）
   → 写 study_events（event_type=practice_submitted/practice_graded, source_system='S3'）
   → is_correct=false 的答题只读输出给 S4

5. 学生调用 practice.getResult({sessionId})
   → 返回 PracticeResult（含逐题结果 + 正确答案 + 解析，此时才返回完整信息）
```

**关键约束**：
- **作答前 DTO 不含 correct_answer/acceptable_answers/explanation**（防泄露）
- 题目归属单个 session 保证历史稳定（不跨 session 引用）
- S3 **不做**错题归档/薄弱点/排程（S4 负责）、不做主观题/跨课程混合组卷（S5 负责）
- session 状态机：`in_progress → submitted → graded`

**错误处理**：
- AI 生成失败 → 不创建空 session，返回 INTERNAL_ERROR + "题目生成失败，请稍后重试或检查模型配置"
- 超时提交 → 允许提交，标记超时但不锁屏

### 2.5 S4 错题改错流程

**触发**：S3 提交批改后，is_correct=false 的答题幂等归档为 mistake

```
1. S3 提交后自动扫描 is_correct=false 的 practice_answers
   → 调用 mistakes.archive({practiceAnswerId})
   → 幂等归档：检查 UNIQUE(question_id) 是否已有 mistake
     - 已有 → 追加 mistake_evidence（UNIQUE(source_practice_answer_id) 防重复）
     - 没有 → 新建 mistake（status=needs_review）
   → 写 study_events（event_type=mistake_archived, source_system='S4'）

2. 学生查看错题列表：mistakes.list({courseId?, status?})

3. 学生请求 AI 错因建议（可选）：mistakes.suggestErrorCause({id})
   → AI 返回 {suggestion, confidence}（带"不确定"标记）
   → AI 建议非事实，学生必须确认

4. 学生确认/修改错因：mistakes.confirmErrorCause({id, category, causeNote?})
   → 六分类：concept_unclear / misread / formula_error / step_missing / time_pressure / other
   → 写 error_cause_category + error_cause + error_cause_confirmed_by='student'
   → 写 study_events（event_type=error_cause_confirmed, source_system='S4'）

5. 学生重做（MVP 原题重做）：mistakes.redo({id})
   → 重做正确 → 增加 mistake_evidence（evidence_type=redo_wrong=null）+ mistakes.redo_count++ + last_redo_correct=1
     → 若 evidence_count≥2 且无对应 weak_point → 归纳为 weak_point
     → mistakes.status=mastered + mastered_at
   → 重做错误 → 增加 mistake_evidence（evidence_type=redo_wrong）+ mistakes.status 保持 needs_review
   → 写 study_events（event_type=practice_reviewed, source_system='S4'）

6. 薄弱点管理：
   → weakPoints.list({courseId?, status?})
   → weakPoints.resolve({id}) → status=resolved（可回退）
   → weakPoints.regress({id}) → status=regressed（"已掌握"非终态）
```

**关键约束**：
- **幂等归档**：`source_practice_answer_id` 唯一约束 + `question_id` 唯一约束
- **S4 只读 S3 事实，不反写 S3 原始作答/批改结果**
- 单次错误不形成永久薄弱点（需 `evidence_count≥2`）
- "已掌握"非终态，可回退到 `needs_review`
- 6 个关系一致性触发器校验 question/course/module/answer 关系（05-ERD §6.1）
- 错题正文/答案/作答/错因**不进 S6 家长报告**

**错误处理**：
- 触发器拦截关系不一致 → 返回 BAD_REQUEST + "数据关系不一致，请刷新后重试"
- AI 错因建议失败 → 返回 INTERNAL_ERROR + "AI 建议暂时不可用，请手动选择错因"

### 2.6 S5 期末冲刺流程

**触发**：已确认考试（confirmation_status=confirmed）+ 距考≤N 天

```
1. 工作台展示冲刺区（三入口）

2. 模拟考流程：
   a. 学生调用 mockExams.generatePaper({assessmentAttemptId, questionCount, timeLimit?})
      → 触发器校验 assessment_attempt 必须 confirmed（05-ERD §6.3）
      → AI 生成限时模拟卷（独立于 S3）
      → source_hash 防重复生成同一套卷
      → 写 mock_exam_papers + mock_exam_questions
   b. 学生调用 mockExams.startAttempt({paperId})
      → 写 mock_exam_attempts（status=in_progress）
   c. 学生限时作答
   d. 学生调用 mockExams.submitAttempt({attemptId, answers})
      → 规则批改客观题（同 S3 三策略）
      → 写 mock_exam_answers + mock_exam_attempts（status=submitted→graded, total_score, correct_count, duration_ms）
      → 写 mock_exam_module_analyses（强弱项分析：strong/medium/weak）
      → 写 study_events（event_type=mock_exam_completed, source_system='S5')
   e. 学生调用 mockExams.getResult({attemptId}) + mockExams.getModuleAnalyses({attemptId})
      → 展示总分/正确率/耗时/逐题结果/模块覆盖和弱项分析

3. 临考速背流程：
   a. 学生调用 cramCards.get({assessmentAttemptId})
      → 确定性只读聚合（不持久化、不依赖 AI、不暴露题干/答案/作答）
      → 从薄弱点 + 错题证据 + 关键知识模块生成短卡片 DTO
      → 返回 CramCard[]

4. 冲刺计划流程：
   a. 学生调用 cramPlan.get({assessmentAttemptId})
      → 确定性即时只读 7 天每日建议 DTO（不持久化、不替学生改写事实）
      → 按剩余天数 + 未完成任务 + 练习表现 + 错题 + 薄弱点排序
      → 返回 CramPlanDay[]
```

**关键约束**：
- 模拟卷独立于 S3（`mock_exam_*` 独立表）
- `source_hash` 防重复生成同一套卷
- 速背卡 + 冲刺计划是**确定性只读 DTO**，不建表、不依赖 AI
- S5 **只读复用 S2/S3/S4 摘要，不反写历史事实**
- 未确认考试不触发冲刺；AI 不可用时不创建空模拟卷/空速背卡
- 题干/答案/作答/速背正文**不进 S6 家长报告**

**错误处理**：
- 触发器拦截未确认考试 → 返回 BAD_REQUEST + "该考试未确认，无法生成模拟卷"
- AI 生成模拟卷失败 → 不创建空卷，返回 INTERNAL_ERROR + "模拟卷生成失败，请稍后重试"

### 2.7 S7 课堂采集流程

**触发**：学生在已选课程的资料页选择"课堂采集"

```
1. 学生勾选许可确认（"已获老师和相关同学允许，仅用于本机学习整理"）

2. 学生选择受控 PCM WAV 文件（RIFF/WAVE/PCM/16kHz/单声道/16-bit）

3. 学生调用 classCapture.transcribe({courseId, audioFile, permissionConfirmed})
   → 服务端重新验证文件头（不信任浏览器 MIME）
   → 本机 whisper.cpp 同步转写（CLI/模型路径只来自配置，不猜路径不回退云端）
   → 返回可编辑转写文本
   → 原始音频只暂存 tmp/class-capture/<request-id>/，finally 清理

4. 学生修改转写文本

5. 学生点击"保存为 S2 笔记输入"：classCapture.saveTranscription({courseId, transcription, title})
   → 创建 S2 materials（file_type='text', source_type='class_audio_transcription', status='converted'）
   → 写 normalized_texts（source_type='class_audio_transcription'）
   → 写 study_events（event_type=class_handoff_saved, source_system='S7')
   → 学生随后在 S2 自行 generateNote 生成笔记
```

**关键约束**：
- **受控 PCM WAV 单一输入**（服务端重新验证文件头）
- **本机 whisper.cpp 同步转写**（不回退云端，不猜路径）
- **不建独立表/Job/Worker**（复用 S2 materials/normalized_texts）
- **原始音频只暂存** tmp，finally 清理
- **许可确认强制**（合规要求）
- S7 **不做**：MP3/M4A/WebM/视频/FFmpeg 转码、实时录音/流式字幕、说话人分离、云端上传、原始音频留存
- CLI/模型路径/stdout/stderr/密钥不泄漏；固定错误码，不返回路径或全文

**错误处理**：
- 文件头验证失败 → 返回 BAD_REQUEST + "仅支持 PCM WAV 格式（16kHz/单声道/16-bit）"
- whisper.cpp 路径未配置 → 返回 INTERNAL_ERROR + "语音转写未配置，请在设置中指定 whisper.cpp 路径"
- 转写失败 → 返回 INTERNAL_ERROR + "转写失败，请检查音频文件是否完整"

### 2.8 通用 AI 对话路径（pi 原生，默认主入口）

**依据**：02-PRD §3.11 + 03-Architecture §6.7 + 09-UI §4.2

**触发**：应用启动即默认打开"💬 对话"标签页；学生随时发送消息

```
1. 应用启动
   → main 创建 BrowserWindow
   → renderer 加载默认"💬 对话"标签页
   → agent-host 加载最近会话（或新建会话）
   → pi 扩展层 before_agent_start 钩子注入：L1 学习者画像 + 当前学期/课程上下文 + 私有技能清单
   → session_start 钩子初始化学期库连接 + 加载 L1 画像
   → 学生看到"你好，今天想学点什么？"

2. 学生发送消息（零碎问答）
   → renderer(PiBridge) → main → agent-host → pi 扩展层
   → pi 原生流式回复（Streams["agent.events"]）
   → 学生看到流式回复 + 工具调用视图

3. AI 自主调用工具（按需）
   → 学生问"帮我出 5 道导数定义题"
   → AI 调用 registerTool 工具 studybuddy_generate_questions
   → tool_call 钩子：workspace-path-guard 校验（write 类）
   → 工具返回题目 → tool_result 钩子：observability 记录
   → renderer 展示"已生成 5 题 [去练习]"按钮
   → 学生点击"去练习" → 跳转练习 Tab（带 sessionId）

4. @文件引用
   → 学生输入 @ → 弹出当前课程资料选择器
   → 选中文件经 allowed-roots 校验 + session-file-references 跟踪
   → 文件内容作为上下文注入对话

5. AI 回复 TTS 朗读（任意时刻）
   → 学生点击 AI 回复的"朗读"按钮
   → 调用 studybuddy_tts_speak
   → 朗读控制条状态更新（Streams["tts.state"]）

6. turn_end 钩子
   → L3 会话检索增量索引（last_offset + last_mtime_ms）
   → 长对话触发上下文压缩（onContextUsageChange）
```

**关键约束**：
- **对话是基础功能，不是可选**（02-PRD §3.11）——pi 天生自带对话能力，不废弃
- **AI 受约束辅助**：AI 只负责受约束生成/抽取/批改/润色；考试日期/错因/掌握状态等必须学生确认；AI 建议带"不确定"标记
- **工具调用透明**：每次 AI 调用 registerTool 工具都可视化展示
- **双层并存**：对话 Tab（自由探索）+ S1-S7 标签页（结构化工具）数据贯通
- **数据不独立**：对话复用 pi 原生会话目录 `~/.pi/agent/`（03-Architecture §4.1 物理隔离），无独立"对话表"
- **会话可检索**：L3 FTS5 bigram 索引对话内容，支持历史搜索

**与 S1-S7 主路径的衔接**（工具调用可跳转，09-UI §4.2）：

对话中 AI 调用 registerTool 工具后，renderer 工具卡片展示跳转按钮（统一文案 `[去<Tab名>]`），点击跳转对应结构化 Tab（T-M3-004 落地）。工具→目标 Tab 映射表（35 工具全覆盖）：

| 工具域 | 工具 | 目标 Tab | 衔接语义 |
|---|---|---|---|
| S3 练习 | generate_questions / submit_practice / get_practice_result | ✏️ 练习 | 出题后去练习（E2E-11） |
| S2 笔记 | generate_note / update_note | 📝 笔记 | "查看"跳笔记（09-UI §4.2） |
| S2 学习状态 | update_learn_status | 📝 笔记 | 学习状态归笔记域 |
| S2 资料 | upload_material / convert_material / replace_material_text | 📁 资料 | 上传后去资料（S2） |
| S4 错题 | confirm_error_cause / redo_mistake / archive_mistake / aggregate_weak_point | ❌ 错题 | 错题改错（S4） |
| S5 冲刺 | generate_mock_exam / submit_mock_exam | 🎯 冲刺 | 模拟考（S5） |
| S6 报告 | generate_parent_report / deliver_parent_report / manage_report_targets | 📋 报告 | 请求报告（S6） |
| S7 采集 | transcribe_class / save_transcription | 🎤 采集 | 课堂转写（S7） |
| S1 首页 | init_semester / transition_semester / add_exam / confirm_exam / complete_task / daily_brief / ocr_schedule | 📊 首页 | 学习节奏（S1） |
| TTS | tts_speak / tts_control / tts_switch_engine | — | 无跳转（朗读控制条全局） |
| 备份 | backup_course / backup_all_courses / restore_course / list_backups / configure_backup_schedule | — | 无跳转（TabBar 无备份 Tab，留会话管理 UI 落位） |

跳转规则：仅工具调用 done 状态且有目标 Tab 时渲染跳转按钮；无目标 Tab 工具（TTS/备份域）不渲染。跳转携带会话上下文（sessionId，后续扩展 courseId）。

补充衔接：
- 学生在对话里问错题 → @引用错题 ID → AI 读取 S4 错题上下文

**错误处理**：
- AI provider 失败 → 返回 INTERNAL_ERROR + "AI 暂时不可用，请检查模型配置或稍后重试"
- 工具调用失败 → tool_result 钩子记录，AI 收到错误可自行降级回复
- 上下文压缩失败 → 保留原始上下文，提示学生新建会话

---

## 3. 家长报告路径

### 3.1 报告生成流程

**触发**：学生手动触发 / 调度自动（daily/weekly/monthly/exam_reminder）

```
1. 触发 reports.generate({semesterId, reportType, periodStart, periodEnd})
   → 规则报告优先生成（非 AI）：
     - study_rhythm section：从 S1 study_events + study_tasks 聚合
     - materials section：从 S2 materials 聚合（计数/状态，不含原文）
     - practice section：从 S3 practice_sessions 聚合（正确率/趋势）
     - mistakes section：从 S4 mistakes 聚合（错因分类计数，不含错题正文）
     - exam_reminder section：从 S1 assessment_attempts 聚合（考前提醒）
     - data_quality section：数据完整性检查
   → AI 可选润色（失败保留规则报告）
   → 写 parent_reports（rule_generated=1, ai_polished=0/1）
   → 写 study_events（event_type=report_generated, source_system='S6'）

2. 报告冻结：reports.freeze({reportKey})
   → 冻结脱敏快照：content_json + content_hash（SHA-256）
   → assertNoSensitiveLeak（UUID 泄漏检测）：
     - 序列化整个 ParentReportResult
     - UUID 正则检测
     - 发现完整 UUID → 抛 PARENT_REPORT_PRIVACY_VIOLATION(500)
     - AI 摘要内容也经此检测，失败降级为规则报告
```

### 3.2 报告投递流程

**触发**：报告冻结后

```
1. 学生调用 deliveries.deliver({reportKey, channel})
   → 按 report_key+channel 去重（PK）
   → 渠道独立失败隔离：
     - local_export：导出文件到本地目录
     - smtp：邮件发送（真实邮箱在 credential-vault）
     - feishu_webhook：飞书 Webhook（真实 URL 在 credential-vault）
     - print：打印
   → 写 report_deliveries（status=pending→sent/failed）
   → 写 study_events（event_type=report_delivered, source_system='S6'）

2. 投递失败重试：deliveries.retry({reportKey, channel})
   → 最多重试 3 次
   → 达上限 → status=retained_locally（本机脱敏留档）
   → Streams["delivery.status"] 推送投递状态
```

**关键约束**：
- **规则优先 + AI 仅润色**：AI 失败保留规则报告，不阻塞
- **冻结快照**：`content_json` + `content_hash`，保证投递内容一致
- **至少一次投递语义**：外部成功但本机未写 `sent` 前崩溃，恢复可能重复投递同一冻结快照
- **渠道独立失败隔离**：SMTP 失败不影响飞书，反之亦然
- **报告类型**：`daily` / `weekly` / `monthly` / `exam_reminder`（考前 7/3/1 天，只对 `confirmed` 考试触发）
- **家长不登录系统、不编辑任务、不看本机页面**

**错误处理**：
- UUID 泄漏检测失败 → 抛 PARENT_REPORT_PRIVACY_VIOLATION + 降级为规则报告
- 渠道投递失败 → 渠道独立隔离，其他渠道不受影响；最多重试 3 次
- credential-vault 解密失败 → 返回 INTERNAL_ERROR + "家长联系方式解密失败，请重新配置"

---

## 4. TTS 朗读路径（跨子系统随时可击发）

### 4.1 随时可击发流程

**触发**：学生打开 pi-studybuddy 后，任何有文字内容的位置均可触发

```
1. 学生在任意 Markdown/纯文本内容处触发朗读
   → 调用 tts.speak({text, engine?: 'sapi'|'edge-tts'})
   → SAPI 默认（Windows 系统自带、零依赖、离线可用）
   → edge-tts 可选（音质好、需网络）
   → 返回 {playbackId}
   → Streams["tts.state"] 推送朗读状态

2. 朗读控制：tts.control({playbackId, action, rate?})
   → action: play / pause / stop
   → rate: 语速调节
   → 朗读状态由前端管理

3. 朗读状态查询：tts.getStatus({playbackId})
   → 返回 {state, position, duration}

4. 切换引擎：tts.switchEngine({engine})
   → 切换 SAPI / edge-tts
```

### 4.2 场景化朗读（非穷举）

| 场景 | 触发位置 | 朗读内容 |
|---|---|---|
| **S2 笔记朗读** | 每日整理完毕当日学习笔记后 | Markdown 笔记正文（"听一遍自己的笔记"，强化记忆） |
| **S4 错题复盘朗读** | 错题复盘笔记/解析 | 错题解析（"听错题解析加深记忆"） |
| **S5 考前冲刺朗读** | 考前冲刺要点 | 速背卡内容（"考前每日听冲刺要点磨耳朵"） |
| **任意内容朗读** | 任何 Markdown/纯文本 | 资料摘要/知识模块/速背卡等 |

### 4.3 标记已复习流程

**触发**：学生主动把某次朗读标记为"已复习"

```
学生调用 events.markReviewed({refType, refId})
  → 写 study_events（event_type=practice_reviewed, source_system='S1'）
  → 朗读本身不持久化，仅"已复习"标记写 StudyEvent
```

**关键约束**：
- **无独立 TTS 表**（朗读是即时行为不持久化）
- 朗读本身不写入 StudyEvent，除非学生主动标记"已复习"
- **封装为 skill**：遵循 progressive disclosure——description 常驻 system prompt，正文按需加载
- SAPI 默认离线，edge-tts 可选需网络

**错误处理**：
- SAPI 不可用（非 Windows） → 返回 INTERNAL_ERROR + "系统 TTS 不可用，请安装 edge-tts 或检查系统设置"
- edge-tts 网络失败 → 返回 INTERNAL_ERROR + "edge-tts 连接失败，已自动切换到 SAPI"

---

## 5. 备份恢复路径

### 5.1 手动备份流程

**触发**：学生随时手动触发某门课程或全部课程备份（考前/归档前/重大变更后）

```
1. 单课程备份：backup.course({courseInstanceId, targetPath})
   → 按 course_instance_id 过滤导出 semester.db 相关表数据为 data/*.jsonl
   → 复制该课程 storage_key 指向的资料文件到 storage/
   → 生成 manifest.json（course_instance_id/course_name/semester_id/backup_type/content_hash/schema_version/tables/file_count/total_size_bytes）
   → 打包为 zip（<course-name>-<backup-date>.zip）
   → 写 global.db:backup_records（backup_type=manual, status=completed, content_hash=SHA-256）
   → Streams["backup.progress"] 推送备份进度

2. 全课程备份：backup.allCourses({semesterId, targetPath})
   → 遍历该学期所有 course_instances，逐个调用 backup.course()
   → 写 backup_records[]（backup_type=manual）
```

### 5.2 定期调度备份流程

**触发**：cron-scheduler 到期（默认每周一 00:00 / 学生配置每月一）

```
1. 学生配置调度：backup.configureSchedule({semesterId, courseInstanceId?, cronExpression, timezone})
   → 写 global.db:backup_schedules（cron_expression, enabled=1）
   → cron_expression: "0 0 * * 1"（每周一）或 "0 0 1 * *"（每月一）

2. 调度到期：
   → cron-scheduler tick（每 60 秒）→ isCronDue 判断到期
   → 自动执行 backup.course() 或 backup.allCourses()
   → 写 backup_records（backup_type=scheduled）
   → 更新 backup_schedules.last_run_at + next_run_at

3. 学生管理调度：
   → backup.listSchedules({semesterId})
   → backup.toggleSchedule({id, enabled})
```

### 5.3 恢复流程

**触发**：学生从本地备份 zip 恢复对应课程（SQLite 崩溃/损坏后）

```
1. 学生调用 backup.restore({zipPath, targetSemesterId, conflictResolution?: 'overwrite'|'create_new'})
   → 解压 zip 到临时目录
   → 读取 manifest.json，校验 content_hash 完整性
   → 校验 schema_version 兼容性
   → 检查目标学期是否存在同名课程：
     - 无冲突 → 直接导入
     - 有冲突 → 学生确认 overwrite（覆盖）或 create_new（新建）
   → 导入 data/*.jsonl 到 semester.db（按 course_instance_id）
   → 复制 storage/ 文件到目标学期 storage 目录
   → 恢复后 PRAGMA integrity_check
   → 返回 RestoreResult（restoredCourseId/conflictResolved/tablesImported/filesRestored/integrityCheck）
   → 写 backup_records（备份类型 manual 恢复记录）
```

### 5.4 归档触发备份流程

**触发**：学期状态机 transition 到 archived

```
1. 归档前：学生调用 semesters.transition({id, status: 'archived'})
   → 强制触发 backup.allCourses()（backup_type=pre_archive）
   → 所有课程备份成功后才允许归档

2. 归档后：
   → 归档完成后再触发一次 backup.allCourses()（backup_type=post_archive）
   → 学期状态变为 archived（只读，更正留审计痕迹）
```

### 5.5 备份 zip 内部结构

> 详见 [05-ERD §8.1](./05-数据模型-ERD-Data-Model.md)

```
<course-name>-<backup-date>.zip
  ├ manifest.json          ← 备份清单
  ├ data/*.jsonl           ← 按 course_instance_id 过滤导出的表数据
  └ storage/               ← 该课程 storage_key 指向的资料文件
```

**关键约束**：
- **备份粒度**：每门课程（course_instance）一个独立 zip 包
- **备份目标**：本地其他目录（学生自选）；**不传云端**
- **SQLite 崩溃应对**：WAL 模式 + 定期 zip 备份双保险；崩溃/损坏后从最近备份恢复，最多丢失一个备份周期（一周/一月）的数据
- **归档前后强制备份**：所有课程
- **zip 作为备份容器**（与"资料导入拒绝压缩包"不冲突——资料导入拒绝 zip/7z/rar 当学习内容解析，备份恢复用 zip 作容器）

**错误处理**：
- content_hash 校验失败 → 返回 BAD_REQUEST + "备份文件已损坏，content_hash 不匹配"
- schema_version 不兼容 → 返回 BAD_REQUEST + "备份版本不兼容，当前系统不支持该版本"
- 恢复时 integrity_check 失败 → 返回 INTERNAL_ERROR + "恢复后数据完整性检查失败，请联系技术支持"

---

## 6. 组件治理流程（五阶段）

### 6.1 五阶段流程

> 详见 [00 索引 §四](./00-文档索引-Index.md) + [03-Architecture §9](./03-架构设计-Architecture-Design.md)

```
1. 组件下载储存 → H:\pi-references 或组件专用目录
2. 组件单件测试 → 独立冒烟（合成夹具）
3. 组件集成测试 → 与 pi 底座对接契约验证
4. 系统配件组装 → 进入主仓 Adapter/扩展
5. 系统冒烟测试 + 系统端到端测试 → 全链回归
```

### 6.2 阶段产物与组件对应

| 阶段 | 架构组件 | 产物 |
|---|---|---|
| **1. 下载储存** | pi（npm 5 件套 peerDependencies）、pi-skills（git clone）、pi-desktop（Apache-2.0 骨架）、inno-agent（MIT 范本）、OCR venv、whisper.cpp | `H:\pi-references\*` + `node_modules` + venv |
| **2. 单件测试** | 每个学习工具（registerTool 契约断言）、每个引入技能（夹具）、WPS COM 桥、whisper.cpp Adapter、OCR venv Adapter、TTS skill | 独立冒烟 + 合成夹具 |
| **3. 集成测试** | studybuddy-extension 与 pi 底座对接契约验证、`createAgentSession({ customTools })` 拼装真实 pi-ai provider、工具与 pi.on 钩子协作 | 与 pi 底座对接契约验证 |
| **4. 系统配件组装** | 进入主仓 `src/agent/studybuddy-extension.ts` + `src/agent/adapters/` + `src/main/` + `src/agent-host/` + `src/contract/` + `~/.pi/agent/skills/` | Adapter/扩展 |
| **5. 系统冒烟 + 系统 E2E** | S1-S7 全链路、TTS 跨子系统、备份恢复、家长报告脱敏、workspace-path-guard、credential-vault | 全链回归 |

### 6.3 失败退回流程

```
任一阶段失败 → 退回上一阶段重做，不进 master
  ↓
冒烟失败 = 该工位不合格退件，不是事故
  ↓
修复后重新走当前阶段 → 通过则进入下一阶段
```

### 6.4 四参考仓库治理

四个参考仓库本身也只处于"下载储存"阶段（`H:\pi-references\*`）：
- 引用其结论必须先回填到 pi-studybuddy 的有效编号文档（prep-参考点核对表 → 03-Architecture）
- 再独立设计决策
- **不得直接把参考代码复制进主仓**

### 6.5 装配顺序（骨架稳定、业务可演化）

```
1. 先落地"main + preload + renderer + agent-host"四进程骨架与 contract/ 契约（可逐字搬运）
2. 再叠加 toolchain 发现 / credential-vault / file-watch 三个公用零件
3. 最后才在其上自建学习业务模块
```

**原则**：避免业务与壳耦合，确保五阶段治理中"壳层稳定、业务可演化"。

---

## 7. 调度层

### 7.1 cron-scheduler 设计

> 借鉴 inno-agent `src/scheduler/cron-scheduler.ts`（03-Architecture §7.1）

**核心机制**：
- 进程内 `setInterval` 每 60 秒 tick（首次延迟 5 秒）
- 每 tick 遍历 `JobStore.list()`，跳过 disabled 和已在运行的（`this.running` Set 防重叠）
- `isCronDue(cron, timezone, lastRunAt, now)` 判断到期
- `executeJob` 调 `runPromptSerialized(prompt)`
- 一次性 cron 执行后自动 `enabled=false`
- 持久化：`jobs.json` + `runs.jsonl`

### 7.2 taskType 枚举

| taskType | 用途 | 触发 |
|---|---|---|
| `spaced_review` | 艾宾浩斯复习 | 调度自动 |
| `daily_review` | 每日总结 | 调度自动 |
| `weekly_summary` | 周报 | 调度自动 |
| `learner_profile_reflection` | L1 画像反思 | 调度自动 |
| `backup_course` | **备份恢复定期调度**（每周一/每月一） | 调度自动 |
| `push_reminder` | 提醒推送（直接格式化文本不调 LLM） | 调度自动 |
| `custom_prompt` | 自定义 prompt | 学生配置 |

### 7.3 推送目标（简化 inno-agent channels）

- **删除** feishu/wechat/bridge 具体实现
- **保留** `ChatChannel`/`ChannelRegistry` 接口抽象（便于未来扩展）
- 推送目标改为**桌面通知 + 应用内消息中心**
- Streams["schedule.reminder"] 推送 `{taskType, message}`

---

## 8. 状态机汇总

### 8.1 学期状态机

```
active → teaching_ended → follow_up → archived
```
- 归档前后强制触发完整备份（§5.4）
- 归档后只读，更正留审计痕迹

### 8.2 考试确认状态机

```
pending → confirmed（驱动冲刺）
pending → rejected
confirmed → superseded（被新 attempt 取代）
```
- 未确认考试不驱动冲刺

### 8.3 Material 状态机

```
pending → converting → converted → note_generating → completed
                ↓                              ↓
        conversion_failed              pending_quality_check
```
- AI 不可用保留 `normalized_text` + `pending_quality_check`

### 8.4 Job 状态机

```
pending → running → completed
                  → failed（retry_count < max_retries 可重试）
```

### 8.5 练习会话状态机

```
in_progress → submitted → graded
```

### 8.6 错题状态机

```
needs_review → mastered（重做正确）
mastered → needs_review（再次答错回退）
```
- "已掌握"非终态

### 8.7 薄弱点状态机

```
active → resolved（可回退）
resolved → regressed（"已掌握"非终态）
```
- 需 `evidence_count≥2` 才形成

### 8.8 模拟考状态机

```
mock_exam_attempts: in_progress → submitted → graded
```

### 8.9 报告投递状态机

```
pending → sent
       → failed（retry_count < max_retries 可重试）
       → retained_locally（达上限本机脱敏留档）
```
- 渠道独立失败隔离

### 8.10 知识模块学习状态机

```
not_started → learning → mastered
                       → needs_review（可回退到 learning）
```

### 8.11 备份状态机

```
backup_records: in_progress → completed
                         → failed
```

---

## 9. 错误处理与降级策略

### 9.1 统一错误码（06-API §2.2）

| 错误码 | 含义 | 降级策略 |
|---|---|---|
| `NOT_FOUND` | 资源不存在 | 提示检查是否已删除 |
| `INVALID_JSON` | 请求体 JSON 格式错误 | 提示刷新后重试 |
| `FILE_TOO_LARGE` | 文件超过大小限制 | 提示压缩或分段上传 |
| `BAD_REQUEST` | 业务校验失败 | 提示具体原因（如"该考试未确认"） |
| `INTERNAL_ERROR` | 内部错误 | 提示稍后重试或重启应用 |
| `PARENT_REPORT_PRIVACY_VIOLATION` | UUID 泄漏 | 降级为规则报告 |

### 9.2 AI 失败降级原则

- **AI 失败不阻塞学生操作**：保留确定性规则输出或 `pending_quality_check`
- **AI 不可用时**：
  - S2 笔记生成 → 保留 `normalized_text` + `pending_quality_check`
  - S3 题目生成 → 不创建空 session，返回错误
  - S4 错因建议 → 返回错误，学生手动选择
  - S5 模拟卷 → 不创建空卷，返回错误
  - S6 报告 → 保留规则报告
- **AI 输出必须标注**：`ai_generated=1` 标记，不可冒充事实

### 9.3 中文可操作消息原则

- 永不暴露：内部错误栈、SQL 语句、文件路径、完整 UUID、API Key
- 面向学生：中文、可操作、告诉学生"怎么办"
- 失败可重试：提示重试方式
- 失败不可重试：提示具体操作（如"重启应用"/"检查文件格式"）

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1.3 | 2026-08-09 | 交叉审查修订：仅同步上游文档版本引用，不改状态机与业务流程。 |
|---|---|---|
| v0.1.2 | 2026-08-08 | §2.8 衔接段扩充为工具→目标 Tab 映射表（35 工具全覆盖，T-M3-004 裁决 1b）：S3→练习 / S2 笔记+学习状态→笔记 / S2 资料→资料 / S4→错题 / S5→冲刺 / S6→报告 / S7→采集 / S1+OCR→首页 / TTS 与备份域无目标 Tab 不渲染跳转；跳转规则（仅 done 且有目标 Tab 渲染 [去<Tab名>]，携带会话上下文）。依据：T-M3-004 五裁决 1/1a/3 + AGENTS.md §11.2 修订纪律。影响：权威条款增补映射表，原四条衔接 bullet 并入映射表语义，无 supersedes |
| v0.1.1 | 2026-08-07 | 按用户反馈增强：§1.1 工作流分类新增"通用 AI 对话路径"（默认主入口）；新增 §2.8 通用 AI 对话工作流（应用启动默认打开 + 零碎问答 + AI 自主调用 S1-S7 工具 + @文件引用 + TTS 朗读 + L3 索引 + 与 S1-S7 衔接）；响应用户反馈"pi 天生自带对话，不能把 ai 输入基础功能废弃" |
| v0.1.0 | 2026-08-07 | 初始草案：学生主路径（S1-S7 核心闭环 7 个工作流）；家长报告路径（生成→冻结→投递→重试）；TTS 朗读路径（随时可击发+场景化+标记已复习）；备份恢复路径（手动/定期/归档触发/恢复 4 个工作流+zip 结构引用）；组件治理流程（五阶段+失败退回+四参考仓库治理+装配顺序）；调度层（cron-scheduler+taskType 枚举+推送目标）；状态机汇总（11 个状态机）；错误处理与降级策略。输入：02-PRD §3 + 03-Architecture §3/§7/§9 + 05-ERD 状态机/触发器 + 06-API 方法表 |

# 02-PRD 产品需求

**版本**：v0.1.4
**日期**：2026-08-09
**状态**：✅ 已审查批准；T-M5-011 执行中。

> T-M5-011 当前产品验收口径：先在开发机从空数据完成真实学生主路径，再复制同一运行拓扑到使用机。产品目标不是页面和 API 数量，而是孩子能够连续完成学习闭环。已知问题见 [系统集成/02](./系统集成/02-系统问题总账与整改清单.md)。
**上游**：docs/00 索引、[01-TRD v0.2.4](./01-TRD-技术需求-Technical-Requirements.md)、[docs/prep-参考点核对表.md](./prep-参考点核对表.md)
**业务来源**：ai-studybuddy S1-S7 业务认知迁移、kaobuddy 功能基本面吸收结论
**下游**：03-Architecture、05-ERD、07-Workflow、09-UI

---

## 1. 项目定位与产品愿景

### 1.1 一句话定位

**pi-studybuddy = 以 pi 为 AI 底座的单用户单机 Windows 桌面学习工作台**，把课程/考试目标、学习节奏、资料笔记、练习、错题和考前冲刺连成可持续闭环，家长接收脱敏异步摘要。

### 1.2 产品愿景

学生在本机一个桌面应用里完成"学期初始化 → 资料整理 → 知识模块抽取 → 限时练习 → 错题改错 → 期末冲刺 → 家长报告"的完整学习闭环；AI 在每个环节提供受约束的辅助（生成/抽取/批改/润色），但**不接管决策、不替学生改写事实**；家长通过脱敏报告了解学习进展，**不登录系统、不看原文、不编辑任务**。

**pi 原生 AI 对话是基础能力，不是可选**：pi-studybuddy 以 pi coding agent 为 AI 底座，pi 天生自带对话能力——这是"专属 studybuddy"的根基。学生在"💬 对话"标签页（默认打开）可随时与 AI 自由问答（"帮我理解极限的 ε-δ 定义"/"这题怎么做"/"导数和积分的关系"），AI 可自主调用 S1-S7 全部 registerTool 工具（生成笔记/出题/朗读/备份等）。学生不必为了零碎提问而使用别的 AI。对话与 S1-S7 结构化工具双层并存：对话是"自由探索"区，S1-S7 是"结构化工具"区，数据贯通。详见 §3.11。

### 1.3 与三个来源的关系

| 来源 | 角色 | 处置 |
|---|---|---|
| ai-studybuddy（S1-S7 已验证） | **业务内核**（342 后端测试 + 149 前端测试 + 24 E2E + 真实冒烟） | 业务认知与数据模型迁移，**实现重构**（不复制代码） |
| kaobuddy（无 LICENSE） | **功能基本面参考**（考试项目/资料导入/知识模块/模拟考/临考速背/备考工作台） | 仅做产品与架构研究，**禁止复制源码/视觉/文案/品牌资产**；采用任何设计必须先独立设计决策 |
| pi 生态四仓库 | **AI 底座 + 组件供给 + 业务化范本 + 使用者介面** | 见 [docs/prep-参考点核对表.md](./prep-参考点核对表.md) |

### 1.4 核心价值主张

1. **证据驱动闭环**：每个学习对象（任务/错题/薄弱点/报告）都有来源证据回链，AI 生成内容必须标注来源，降低幻觉
2. **规则优先、AI 辅助**：日期/统计/去重/状态/批改由确定性规则负责，AI 只负责受约束生成或润色
3. **隐私是信任根基**：家长报告脱敏聚合 + UUID 泄漏检测；AI 日志 allowlist；密钥 DPAPI 加密；仅 127.0.0.1
4. **单机零云依赖**：学生本机运行，无公网入口、无云数据库、无自动同步；AI 可用本地推理或学生自配供应商
5. **听觉复习通道**：TTS 跨子系统随时可击发，把"看"变"听"——笔记整理后听一遍、错题复盘听解析、考前每日听冲刺要点，形成视觉之外的听觉记忆通道

---

## 2. 使用者与角色边界

### 2.1 使用者画像

| 角色 | 描述 | 在系统中的行为 |
|---|---|---|
| **学生**（主用户） | 一名在 Windows 本机学习的学生（K12/大学/自考等） | 唯一登录用户；初始化学期、上传资料、生成笔记、做练习、改错题、看冲刺、确认事实；拥有全部读写权限 |
| **家长**（报告接收者） | 学生的家长，关心学习进展但不过度干预 | **不登录系统、不编辑任务、不看本机页面、不看原文**；仅通过脱敏报告（邮件/飞书/本地导出）接收异步摘要 |

### 2.2 角色边界（铁律）

- **单用户单机单写进程**：系统只服务一名学生，一台 Windows 机器，一个 Node 写进程（WAL 模式）；不支持多用户、多终端并发、远程协作
- **家长不进系统**：家长不是系统用户，没有任何 API 端点；家长报告是"推"不是"拉"，且只推脱敏快照
- **AI 不接管决策**：AI 生成的计划/错因/摘要必须由学生确认；AI 建议带"不确定"标记；AI 不可用时保留确定性规则输出，不阻塞
- **AI 解读必须标注**：任何 AI 生成或润色的内容必须明确标注"AI 辅助生成"，不可冒充事实

### 2.3 不在范围内的人员

- 教师/同学/辅导员（不作为系统用户；课堂采集 S7 仅由学生操作录音）
- 多个家长（v0.1 单一家长渠道；多家长报告是后续能力）
- 远程协作者/审核者（v0.1 不支持任何远程协作）

---

## 3. 业务闭环定义（考试驱动学习闭环）

### 3.1 闭环全景

```
学期初始化(S1) → 资料笔记(S2) → 知识模块(S2) → 限时练习(S3) → 错题改错(S4)
                                      ↑                                    ↓
                                      └────────── 薄弱点回流 ──────────────┘
                                                        ↓
                                        期末冲刺(S5: 模拟考/临考速背/冲刺计划)
                                                        ↓
                                        家长报告(S6: 脱敏异步摘要)
                                                        ↓
                                        课堂采集(S7: 录音转写→S2 handoff)
```

**闭环原则**：
- 每个环节产出"证据"写入 StudyEvent 时间线，下一环节只读上一环节的事实，**不反写历史**
- 学生确认是事实成立的必要条件（考试日期/错因/掌握状态等）
- AI 在每个环节受约束辅助，失败降级为确定性规则输出

### 3.2 S1 学习节奏 StudyRhythm

**业务认知**：学期初始化（日期→课程表 OCR 识别预览→学生一次确认→原子化建学期/课程/课表/目录）→ 持续补全考试日期（保留来源/置信度/确认/变更历史，未确认不驱动倒计时）→ 每日首页呈现"明日准备/到期/待质检/错题复习/下一步"少量证据驱动待闭合项 → 任务完成写入 StudyEvent → 学期状态机 `active→teaching_ended→follow_up→archived`。

**关键产品规则**：
- 考试确认四态：`pending / confirmed / rejected / superseded`；未确认考试不驱动冲刺
- 补考不重建课程（原 course_instance 下新增 attempt）；重修新学期建新 course_instance 并关联 `retake_of`
- 合理特例（如病假）由 AI 提证据、学生确认，不计入负面趋势
- 归档学期默认只读，更正留审计痕迹
- 每日首页只呈现少量待闭合项，不堆砌全部任务

**数据契约要点**：全局库 `semesters`（学期索引，含 `db_relative_path`/`ready` 标志）；学期库 `course_instances`/`assessment_attempts`（含 `confirmation_status`/`confirmed_at`）/`schedule_entries`/`study_tasks`/`study_events`（`source_system` S1-S7）。

### 3.3 S2 资料笔记 NoteBuilder

**业务认知**：学生选课程 → 上传资料（PDF/DOCX/PPTX/图片/TXT/MD；旧格式 doc/ppt/xls 经 WPS COM 转中间格式）→ 落盘 `storage_key` + 建 material 记录 → 转换 Job（PDF/OCR/DOCX/PPTX 各有超时）→ 保存 `normalized_text` → AI 笔记生成 Job（Markdown 笔记 + highlights + Markmap 导图 + 知识模块带 `source_evidence` 回链）→ 写 StudyEvent。

**关键产品规则**：
- Material 状态机：`pending→converting→converted→note_generating→completed`（失败分支 `conversion_failed`/`pending_quality_check`）
- AI 不可用时保留 `normalized_text` + `pending_quality_check`，不阻塞查看原文
- 知识模块**必须带 `source_evidence` 回链**（降低幻觉的关键约束）
- 失败恢复：retry-conversion / retry-ai-generation（最多 3 次）/ replace-text（手动粘贴纯文本跳过转换）
- `storage_key` 是相对路径，触发器拒绝 `..`/`:\`/`:/`（路径逃逸防护）
- S7 handoff：学生确认的课堂转写文本创建 `file_type='text'` material，初始 `converted`，不自动建 Job

**数据契约要点**：`materials`/`normalized_texts`/`structured_notes`（含 `prompt_version`/`model`/`token_count`）/`mind_maps`/`knowledge_modules`（含 `importance`/`difficulty`/`learn_status`/`source_evidence`）/`material_chunks`/`jobs`。

### 3.4 S3 限时练习 PracticeRunner

**业务认知**：学生选 1-10 个知识模块 → 可选设题数(5-20)/限时/难度 → 同步调 AI 生成客观题（单选 60%/多选 20%/填空 20%）→ AI 失败不创建空 session → 学生逐题作答（前端计时，限时可超时标记但不锁屏）→ 提交触发**规则批改**（非 AI 批改）→ 保存逐题答题 + session 汇总 → 写 StudyEvent → `is_correct=false` 的答题只读输出给 S4。

**关键产品规则**：
- 规则批改三策略：单选精确匹配、多选全选 deepEquals、填空 normalize（trim+全角转半角+统一大小写+去多余空格，支持多等价答案 OR）
- **作答前 DTO 不含 correct_answer/acceptable_answers/explanation**（防泄露）
- 题目归属单个 session 保证历史稳定（不跨 session 引用）
- S3 **不做**错题归档/薄弱点/排程（S4 负责）、不做主观题/跨课程混合组卷（S5 负责）
- session 状态机：`in_progress→submitted→graded`

**数据契约要点**：`questions`（含 `source_evidence`/`ai_model`/`prompt_version`）/`practice_sessions`/`practice_answers`。

### 3.5 S4 错题改错 ErrorFixer

**业务认知**：S3 提交批改后，`is_correct=false` 的答题**幂等归档**为 mistake（同一 question 唯一，重复扫描不重复建）→ 学生查看错题列表 → 确认或修改错因（六分类：`concept_unclear`/`misread`/`formula_error`/`step_missing`/`time_pressure`/`other`，AI 只提建议带"不确定"标记，学生必须确认）→ 选择重做（MVP 原题重做）→ 重做正确增加掌握证据，错误保持 `needs_review` → 多条错误证据（`evidence_count≥2`）归纳为 `weak_point` → "已掌握"非终态，再次答错可回退。

**关键产品规则**：
- **幂等归档**：`source_practice_answer_id` 唯一约束
- **S4 只读 S3 事实，不反写 S3 原始作答/批改结果**
- 单次错误不形成永久薄弱点（需 `evidence_count≥2`）
- "已掌握"非终态，可回退到 `needs_review`
- 6 个关系一致性触发器校验 question/course/module/answer 关系（数据完整性核心）
- 错题正文/答案/作答/错因**不进 S6 家长报告**

**数据契约要点**：`mistakes`（UNIQUE(question_id)）/`mistake_evidence`（UNIQUE(source_practice_answer_id)）/`weak_points`（UNIQUE(course_instance_id, knowledge_module_id)）。

### 3.6 S5 期末冲刺 ExamCrammer

**业务认知**：已确认考试 + 距考≤N 天 → 工作台展示冲刺区（模拟考/临考速背/冲刺计划三入口）。

- **模拟考**：读取考试范围+知识模块+错题/薄弱点摘要 → AI 生成限时模拟卷（独立于 S3）→ 学生限时作答 → 规则批改客观题 → 展示总分/正确率/耗时/逐题结果/模块覆盖和弱项分析
- **临考速背**：确定性只读聚合，从薄弱点+错题证据+关键知识模块生成短卡片 DTO，**不持久化、不依赖 AI、不暴露题干/答案/作答**
- **冲刺计划**：确定性即时只读 7 天每日建议 DTO，按剩余天数+未完成任务+练习表现+错题+薄弱点排序，**不持久化、不替学生改写事实**

**关键产品规则**：
- 模拟卷独立于 S3（`mock_exam_*` 独立表）
- `source_hash` 防重复生成同一套卷
- 速背卡+冲刺计划是**确定性只读 DTO**，不建表、不依赖 AI
- S5 **只读复用 S2/S3/S4 摘要，不反写历史事实**
- 未确认考试不触发冲刺；AI 不可用时不创建空模拟卷/空速背卡
- 题干/答案/作答/速背正文**不进 S6 家长报告**

**数据契约要点**：`mock_exam_papers`（触发器校验 `assessment_attempt` 必须 `confirmed`）/`mock_exam_questions`（CHECK 约束选择题 vs 填空题字段互斥）/`mock_exam_attempts`/`mock_exam_answers`/`mock_exam_module_analyses`。

### 3.7 S6 家长报告 ParentReport

**业务认知**：从 S1/S2/S3/S4 读取脱敏聚合 → 规则报告优先生成（5 个 section：`study_rhythm`/`materials`/`practice`/`mistakes`/`exam_reminder` + `data_quality`）→ AI 可选在规则报告基础上做摘要/语气润色（失败保留规则报告）→ 冻结脱敏快照（`content_hash`）→ 按 `report_key+channel` 去重投递 → 渠道独立成功/失败/重试，互不阻塞 → 渠道失败最多重试 3 次，达上限保留本机脱敏留档。

**关键产品规则**：
- **规则优先 + AI 仅润色**：AI 失败保留规则报告，不阻塞
- **冻结快照**：`content_json` + `content_hash`，保证投递内容一致
- **至少一次投递语义**：外部成功但本机未写 `sent` 前崩溃，恢复可能重复投递同一冻结快照
- **渠道独立失败隔离**：SMTP 失败不影响飞书，反之亦然
- **报告类型**：`daily`/`weekly`/`monthly`/`exam_reminder`（考前 7/3/1 天，只对 `confirmed` 考试触发）
- **家长不登录系统、不编辑任务、不看本机页面**
- 详见 §5 家长报告边界与隐私

**数据契约要点**：全局库 `parent_report_targets`；学期库 `parent_reports`（PK `report_key`）/`report_deliveries`（PK `report_key+channel`）。

### 3.8 S7 课堂采集 ClassCapture

**业务认知**：学生在已选课程的资料页 → 勾选"已获老师和相关同学允许，仅用于本机学习整理"许可确认 → 选择受控 PCM WAV（RIFF/WAVE/PCM/16kHz/单声道/16-bit）→ 同步调用本机 whisper.cpp（CLI/模型路径只来自配置，不猜路径不回退云端）→ 返回可编辑转写文本 → 学生修改并点击"保存为 S2 笔记输入" → 创建 S2 `file_type='text'` material，初始 `converted` → 学生随后自行在 S2 生成笔记。

**关键产品规则**：
- **受控 PCM WAV 单一输入**（服务端重新验证文件头，不信任浏览器 MIME）
- **本机 whisper.cpp 同步转写**（不回退云端，不猜路径）
- **不建独立表/Job/Worker**（复用 S2 materials/normalized_texts）
- **原始音频只暂存** `tmp/class-capture/<request-id>/`，finally 清理
- **许可确认强制**（合规要求）
- **S7 不做**：MP3/M4A/WebM/视频/FFmpeg 转码、实时录音/流式字幕、说话人分离、云端上传、原始音频留存
- CLI/模型路径/stdout/stderr/密钥不泄漏；固定错误码，不返回路径或全文

**数据契约要点**：无独立 S7 表；复用 S2 `materials`(file_type='text', status='converted') + `normalized_texts`(source_type='class_audio_transcription')。

### 3.9 TTS 朗读（跨子系统随时可击发）

**业务认知**：TTS 是 pi-studybuddy 桌面工作台的**跨子系统随用随击发能力**，不是某个子系统的附属功能。只要 pi-studybuddy 打开，学生可在任何有文字内容的位置触发朗读——把"看"变成"听"，在整理、复盘、冲刺各环节形成听觉复习通道。

**核心产品规则**：
- **随时可击发**：工作台全局可用，不限于特定页面或子系统；任何 Markdown/纯文本内容均可朗读
- **场景化朗读**（按学习环节，非穷举）：
  - **S2 笔记朗读**：每日整理完毕当日的学习笔记 → TTS 朗读（"听一遍自己的笔记"，强化记忆）
  - **S4 错题复盘朗读**：错题的复盘笔记/解析 → TTS 朗读（"听错题解析加深记忆"）
  - **S5 考前冲刺朗读**：考前冲刺要点 → 考前每日 TTS 朗读（"听冲刺要点磨耳朵"）
  - 其他任意学习内容（资料摘要/知识模块/速背卡等）均可触发
- **引擎**：SAPI 默认（Windows 系统自带、零依赖、离线可用）；edge-tts 可选 skill（音质好、需网络），学生按需切换
- **封装为 skill**：遵循 progressive disclosure——description 常驻 system prompt，正文按需加载；与 pi-skills 的 brave-search/youtube-transcript 同构
- **控制**：播放/暂停/停止/语速调节；朗读状态由前端管理

**数据契约要点**：无独立 TTS 表（朗读是即时行为不持久化）；朗读本身不写入 StudyEvent，除非学生主动把某次朗读标记为"已复习"（此时走 S1 StudyEvent 的 `practice_reviewed` 类事件）。

### 3.10 备份恢复（按课程 zip 包 + 定期调度）

**业务认知**：每学期每门课的独立 SQLite 业务数据 + 资料文件，可打包为独立 zip 包备份到本地其他目录，也可从本地备份 zip 恢复对应课程。避免每次从零开始，应对 SQLite 崩溃/损坏——单机 SQLite 虽 WAL 模式但仍非"强壮"，定期 zip 备份是数据安全的兜底。

**核心产品规则**：
- **备份粒度**：每门课程（`course_instance`）一个独立 zip 包，包含该课程的 semester.db 相关表数据（按 `course_instance_id` 过滤导出）+ 该课程 `storage_key` 指向的资料文件
- **备份目标**：本地其他目录（学生自选，如外部硬盘/U 盘路径）；**不传云端**（与单机零云一致）
- **恢复**：从本地备份 zip 恢复对应课程到当前学期；恢复时 `content_hash` 校验完整性；同名课程冲突时学生确认覆盖/新建
- **定期调度**：默认每周一自动执行（参考 inno-agent cron-scheduler 机制），学生可配置为每月一；调度任务写 `backup_records`
- **手动触发**：学生可随时手动触发某门课程或全部课程的备份（如考前、归档前、重大变更后）
- **zip 作为备份容器**（与"资料导入拒绝压缩包"不冲突，见 §6 澄清）
- **SQLite 崩溃应对**：WAL 模式 + 定期 zip 备份双保险；崩溃/损坏后从最近备份恢复，最多丢失一个备份周期（一周/一月）的数据
- **归档前后备份**：学期归档前后强制触发一次完整备份（所有课程）

**数据契约要点**：全局库 `backup_records`（记录备份历史：课程 ID/备份时间/目标路径/content_hash/备份类型[manual/scheduled/pre_archive/post_archive]/状态）；备份 zip 内部结构约定见 07-Workflow。

### 3.11 通用 AI 对话（pi 原生，默认主入口）

**业务认知**：pi-studybuddy 以 pi coding agent 为 AI 底座，pi 天生自带对话能力。这是"专属 studybuddy"的根基——学生打开应用即看到"💬 对话"标签页（默认），可随时与 AI 自由问答，AI 可自主调用 S1-S7 全部 registerTool 工具。学生不必为了零碎提问而使用别的 AI。

**核心产品规则**：
- **对话是基础功能，不是可选**：应用启动即默认打开"💬 对话"标签页（详见 09-UI §4.2）
- **pi 原生能力全保留**：流式回复（`Streams["agent.events"]`）、工具调用视图、上下文压缩、@文件引用、多模型切换、registerTool 工具调用
- **AI 自主调用工具**：学生在对话里提问，AI 按需调用 `studybuddy_generate_note`/`studybuddy_generate_questions`/`studybuddy_tts_speak`/`studybuddy_backup_course` 等全部 S1-S7 + TTS + 备份恢复工具，工具调用过程可视化
- **学习场景业务化**：会话附加学科标签/学习目标/错题关联；L1 画像在 `before_agent_start` 注入；L3 会话检索在 `turn_end` 增量索引；任意 AI 回复可 TTS 朗读
- **双层并存**：对话 Tab 是"自由探索"区（AI 原生 + 零碎问答），S1-S7 标签页是"结构化工具"区（规则驱动 + 闭环）；两者数据贯通（对话中生成的笔记 → 笔记 Tab 可见；练习 Tab 的错题 → 对话中可 @引用讨论）
- **AI 受约束辅助**（铁律，与 §2.2 一致）：AI 只负责受约束生成/抽取/批改/润色，不接管决策、不替学生改写事实；考试日期/错因/掌握状态等必须学生确认；AI 建议带"不确定"标记
- **工具调用透明**：每次 AI 调用工具都可视化展示，学生知道 AI 做了什么
- **Simple Mode**：学生可在设置中切换简化模式（03-Architecture §2.5），降低上下文消耗

**数据契约要点**：无独立"对话表"——复用 pi 原生会话目录 `~/.pi/agent/`（03-Architecture §4.1 物理隔离）；会话列表 `sessions.*`（06-API §3.1）统一管理；L3 会话检索（FTS5）索引对话内容便于历史搜索。

---

## 4. kaobuddy 功能基本面吸收结论

> kaobuddy 无 LICENSE，是第三方只读参考。**禁止复制源码/视觉/文案/品牌资产**；采用任何设计必须先独立设计决策。本节记录吸收结论，作为 03-Architecture 的功能覆盖度参考。

### 4.1 吸收总表

| kaobuddy 模块 | 吸收结论 | 吸收方式（独立重设计要点） |
|---|---|---|
| **考试项目** | 吸收 | 上升为 `Exam` 一等对象，支持一个 Course 对多个 Exam（kaobuddy 是 1:1）；`daily_minutes` 改为按星期的可用时间表；`target_score` 改为带百分制/等级制结构化字段；`weak_points` 拆为"用户自述"+"系统推断"两条来源；不复制 prompts.py 文案 |
| **资料导入** | 部分吸收 | 格式覆盖面吸收（PDF/DOCX/PPTX/图片/TXT/MD），实现迁移到 pi 生态独立 adapter；**不吸收** IndexedDB 存全文（改本地文件+storage_key）；**不吸收** B站字幕 UA 伪装抓取（改白名单+用户粘贴字幕）；手写 OCR 走本地 RapidOCR 不走多模态 AI |
| **知识模块** | 吸收 | "证据化知识模块"（带 source/source_section/evidence）是 kaobuddy 最值得吸收的设计，**必须保留**；分块抽取+后合并策略吸收，但规则层负责切块和去重、AI 只负责抽取；AI 输出改严格 JSON Schema 而非自由文本+正则兜底；**不复制** PLAN_SYSTEM_PROMPT 文案 |
| **模拟考** | 吸收 | "试题+解析双段输出"契约吸收，但 AI 直接输出结构化 JSON（题型/题干/选项/标准答案/解析/分值/对应知识点）；新增"人工答题→AI批改→错题回流"模式；题级三态判定吸收为内部状态机；**不复制** MOCK_*_SYSTEM_PROMPT 文案；PDF 导出改独立方案不用 html2canvas |
| **临考速背** | 吸收 | 五段结构（核心概念/必背要点/记忆口诀/常见考法/易错提醒）作为信息架构吸收，段名顺序由 pi-studybuddy 独立定义；"按重要性排序+斩一个隐藏一个+撤销"交互吸收为"考前清单"模式；**不复制** MEMORIZE_SYSTEM_PROMPT 文案；卡片手势独立实现 |
| **备考工作台** | 吸收架构，不吸收实现 | 信息架构吸收（左项目栏+右工作区+总览四指标卡+今日任务+下一步提示）；7 类数据对象分层对齐 ai-studybuddy S1-S7；**不吸收** IndexedDB/React PWA/localStorage 存密钥/8 tab 平铺；**不复制** DESIGN.md 配色/PRODUCT.md 文案/BrandMark/StatusToast |

### 4.2 与 ai-studybuddy S1-S7 的关系

kaobuddy 6 模块与 ai-studybuddy S1-S7 是**互补为主、局部重叠**关系：

- kaobuddy 的"考试项目+资料导入+知识模块+每日计划"对应 ai-studybuddy S1+S2+S3（高度重叠，kaobuddy 提供"第一产品流程参考"）
- kaobuddy 的"模拟考+临考速背+错题本+薄弱点"对应 ai-studybuddy S5+S4 练习侧（kaobuddy 提供完整练习→批改→错题→薄弱点回流闭环）
- kaobuddy **完全没有** S6 家长脱敏报告和 S7 课堂录制 ASR（这两块由 ai-studybuddy 已有规划独立扩展）

### 4.3 冲突点（pi-studybuddy 按 ai-studybuddy 原则裁决）

- **AI 接管 vs 规则层主导**：kaobuddy 让 AI 直接决定模块清单和每日计划；pi-studybuddy 按 ai-studybuddy 已定调的"规则层负责日期/统计/去重/状态、AI 只负责受约束生成或润色"原则，**不复制 kaobuddy 的 AI 接管模式**
- **资料存储**：kaobuddy 用 IndexedDB 存全文；pi-studybuddy 用本地文件目录 + `storage_key`（DB 只存元数据）
- **AI 输出格式**：kaobuddy 用自由文本+正则解析兜底；pi-studybuddy 用严格 JSON Schema
- **密钥管理**：kaobuddy 用 localStorage 存 API Key；pi-studybuddy 用 DPAPI 加密（pi-desktop credential-vault 模式）

### 4.4 吸收纪律（铁律）

1. **禁止复制**：kaobuddy 的 `backend/app/prompts.py` 全部 prompt 文案、`src/utils.ts` 解析函数、`src/App.tsx` 组件结构、`src/storage.ts` IndexedDB schema、`src/fileReaders.ts` 解析实现、`backend/app/video.py` B站抓取逻辑
2. **禁止复制视觉/品牌**：DESIGN.md 的墨绿+暖橙红配色、PRODUCT.md 的品牌文案、"考搭子/KaoBuddy"名称、BrandMark Logo、StatusToast 样式、memorize-zhan 斩卡片动效
3. **独立设计决策**：先写 pi-studybuddy 自己的 PRD/架构/Prompt，再对照 kaobuddy 验证功能覆盖度，**绝不反向工程 kaobuddy 源码**
4. **数据结构可参考思路但需重命名重设计**：`StudyProject`/`StudyTask`/`MockAttempt` 字段名与类型可参考思路但需重命名重设计

---

## 5. 家长报告边界与隐私

### 5.1 家长报告产品边界

| 维度 | 边界 |
|---|---|
| 家长角色 | 报告接收者，**不是系统用户**；不登录、不编辑、不看本机页面 |
| 报告生成 | 规则优先 + AI 仅润色；AI 失败保留规则报告 |
| 报告内容 | 5 个 section 脱敏聚合：`study_rhythm`/`materials`/`practice`/`mistakes`/`exam_reminder` + `data_quality` |
| 报告类型 | `daily`/`weekly`/`monthly`/`exam_reminder`（考前 7/3/1 天，只对 `confirmed` 考试） |
| 投递渠道 | v0.1：本地导出（文件/打印）；SMTP 邮件 + 飞书 Webhook 作为可选渠道（参考 ai-studybuddy） |
| 投递语义 | 至少一次；`report_key+channel` 去重；渠道独立失败隔离；最多重试 3 次 |
| 冻结快照 | `content_json` + `content_hash`；外部成功但本机未写 `sent` 前崩溃，恢复可能重复投递同一快照 |

### 5.2 脱敏规则（隐私边界铁律）

**禁止读取/输出**（家长报告**绝不**包含）：
- 资料原文、笔记正文
- 完整题干、完整答案、学生作答
- 错因正文（错题的 `error_cause_note`）
- 聊天内容
- 真实渠道地址（邮箱/Webhook URL）
- 完整 UUID

**允许输出**（`privacyLevel: 'aggregate_only'`）：
- 计数/状态/趋势
- 短标题/日期窗口/提醒级别
- 模块名（不暴露原文）

**UUID 泄漏检测**（`assertNoSensitiveLeak`）：
- 序列化整个 ParentReportResult
- 用 UUID 正则 `/[0-9a-f]{8}-...-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i` 检测
- 发现任何完整 UUID → 抛 `PARENT_REPORT_PRIVACY_VIOLATION`(500)
- AI 摘要内容也经此检测，失败降级为规则报告

### 5.3 AI 日志 allowlist

- 允许字段：`event`/`level`/`taskType`/`provider`/`model`/`tokenUsed`/`latencyMs`/`fallbackUsed`/`attemptedProviderCount`/`attemptedProviders`/`cooldownStartedAt`/`cooldownEndsAt`/`cooldownEndedAt`/`errorCode`/`timestamp`
- 字符串值最大 128 字符；`errorCode` 必须匹配 `^[A-Z][A-Z0-9_]{1,63}$`
- **不记录**：API Key、输入全文、输出全文、学生隐私正文、完整 UUID、Provider URL

### 5.4 其他隐私边界

- **API 信封**：`{ success: true, data, meta? } | { success: false, error: { code, message } }`，统一 6 个安全错误码（`NOT_FOUND`/`INVALID_JSON`/`FILE_TOO_LARGE`/`BAD_REQUEST`/`INTERNAL_ERROR`），中文可操作消息，永不暴露内部错误栈
- **仅 127.0.0.1**：无公网入口；loopback Origin 策略
- **密钥存储**：DPAPI 加密（pi-desktop credential-vault 的 safeStorage 模式），键名 `modelProvider:xxx`/`parentContact:xxx`
- **日志根与受保护根互不包含**：拒绝符号链接；单文件 5MiB 轮转保留 3 份
- **S7 原始音频**：只暂存 tmp，finally 清理，不进日志/StudyEvent/S6 报告

---

## 6. 非目标（明确不做什么）

> 以下内容**不在 v0.1 范围内**，避免范围蔓延。如需变更须走显式变更评审。

**zip 澄清**：TRD §3 格式矩阵的"拒绝压缩包"指**资料导入拒绝把 zip/7z/rar 当学习内容解析**（压缩包不是学习内容格式）。这与 §3.10 备份恢复**用 zip 作为备份容器**是两个不同用途，不冲突——备份恢复用 zip 打包课程数据是数据管理，资料导入拒绝解析 zip 是内容边界。

### 6.1 用户与协作

- ❌ 多用户、多终端并发、远程协作
- ❌ 多个家长渠道（v0.1 单一渠道）
- ❌ 教师/同学作为系统用户
- ❌ 家长登录系统或编辑任务

### 6.2 AI 与自动化

- ❌ AI 接管决策（计划/错因/掌握状态必须学生确认）
- ❌ 自动选股/自动交易/盈利预测（与用户 profile 约束一致）
- ❌ AI 冒充事实（AI 生成内容必须标注）
- ❌ AI 直接决定模块清单和每日计划（规则层主导）

### 6.3 功能范围

- ❌ 资料导入解析压缩包（zip/7z/rar 当学习内容解析——压缩包不是学习内容格式；备份恢复用 zip 作容器不在此列，见 §3.10）
- ❌ 主观题/跨课程混合组卷（S3 不做；S5 模拟考只客观题）
- ❌ 实时录音/流式字幕/说话人分离（S7 不做）
- ❌ MP3/M4A/WebM/视频/FFmpeg 转码（S7 只受控 PCM WAV）
- ❌ 云端音频上传/云端 ASR（S7 只本机 whisper.cpp）
- ❌ B站字幕 UA 伪装抓取（资料导入不做）
- ❌ IndexedDB 存全文（改本地文件+storage_key）
- ❌ localStorage 存密钥（改 DPAPI）
- ❌ SheetJS（CVE-2023-30533/CVE-2023-22365，registry 停更）
- ❌ 宏文档解析（xlsm/docm/pptm）
- ❌ 云端备份（v0.1 只本地目录备份，不传云）

### 6.4 部署与分发

- ❌ 公网入口、云数据库、自动同步
- ❌ 多平台（v0.1 只 Windows）
- ❌ 移动端 App

---

## 7. 成功标准

### 7.1 闭环完整性

- [ ] S1-S7 七子系统全部可演示
- [ ] 学期初始化 → 资料笔记 → 知识模块 → 限时练习 → 错题改错 → 期末冲刺 → 家长报告 全链路打通
- [ ] S7 课堂采集 → S2 handoff 可走通
- [ ] S4 错题 → S5 薄弱点回流可走通
- [ ] TTS 跨子系统随时可击发：工作台打开时，S2 笔记/S4 错题复盘/S5 冲刺要点/任意 Markdown 内容均可朗读，SAPI 默认离线可用

### 7.2 隐私边界守护

- [ ] `assertNoSensitiveLeak` UUID 泄漏检测有测试断言
- [ ] AI 日志 allowlist 有测试断言（非 allowlist 字段抛错）
- [ ] 家长报告不含资料原文/题干/答案/作答/错因/完整 UUID
- [ ] API 信封统一 6 错误码，中文可操作消息
- [ ] 仅 127.0.0.1，无公网入口

### 7.3 证据驱动

- [ ] 知识模块带 `source_evidence` 回链
- [ ] 考试日期带来源/置信度/确认状态/变更历史
- [ ] 错题幂等归档（`source_practice_answer_id` 唯一）
- [ ] 错因学生确认（AI 建议带"不确定"标记）
- [ ] 薄弱点需 `evidence_count≥2`

### 7.4 规则优先

- [ ] 批改由规则负责（非 AI）
- [ ] 每日首页由规则聚合（非 AI）
- [ ] 速背卡/冲刺计划确定性只读（不依赖 AI）
- [ ] AI 不可用时保留确定性输出，不阻塞

### 7.5 单机零云

- [ ] 无公网入口
- [ ] 无云数据库
- [ ] 可用本地推理（Ollama 等）或学生自配供应商
- [ ] whisper.cpp 本机转写不回退云端

### 7.6 备份恢复

- [ ] 每门课程可独立 zip 备份（含 semester.db 相关表数据 + storage_key 资料文件）
- [ ] 备份可写入本地其他目录（学生自选）
- [ ] 可从本地备份 zip 恢复对应课程（content_hash 校验完整性）
- [ ] 定期调度默认每周一，可配置为每月一
- [ ] 手动触发备份（单课程/全课程）
- [ ] 学期归档前后强制完整备份
- [ ] SQLite 崩溃后可从最近备份恢复

---

## 8. 版本历史

| 版本 | 日期 | 变更 |
| v0.1.4 | 2026-08-09 | 交叉审查修订：补充未配置模型时 `agent.send` 返回固定 `MODEL_NOT_CONFIGURED`，生产路径不注入测试夹具；密钥与模型配置统一落在业务数据根 `config/`。 |
| v0.1.3 | 2026-08-07 | 按用户反馈增强：§1.2 补"pi 原生 AI 对话是基础能力，不是可选"；新增 §3.11 通用 AI 对话（pi 原生默认主入口 + AI 自主调用 S1-S7 工具 + 双层并存 + 工具调用透明）；响应用户反馈"不能把 ai 输入基础功能废弃"——pi 天生自带对话，作为"专属 studybuddy"不废弃，避免学生被迫用别的 AI |
| v0.1.2 | 2026-08-07 | 按用户反馈增强：§3.10 新增备份恢复（每课程 zip 包 + 定期调度 + SQLite 崩溃应对）；§6 澄清"拒绝压缩包"指资料导入不解析 zip，备份恢复用 zip 作容器不冲突；§6.3 增云端备份为非目标；§7.6 增备份恢复验收项 |
| v0.1.1 | 2026-08-07 | 按用户反馈增强：TTS 提升为 §3.9 跨子系统随时可击发能力（S2 笔记朗读/S4 错题复盘朗读/S5 考前冲刺朗读/任意 Markdown）；§1.4 增"听觉复习通道"价值主张；§7.1 增 TTS 验收项 |
| v0.1.0 | 2026-08-07 | 初始草案：项目定位、使用者与边界、S1-S7 业务闭环、kaobuddy 吸收结论、家长报告边界与隐私、非目标、成功标准。输入：ai-studybuddy S1-S7 调研 + kaobuddy 6 模块吸收结论 + docs/prep-参考点核对表.md |

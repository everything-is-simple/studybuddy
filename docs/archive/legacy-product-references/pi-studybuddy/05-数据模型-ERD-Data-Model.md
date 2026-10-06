# 05 数据模型 ERD

**版本**：v0.1.2
**日期**：2026-08-09
**状态**：✅ 已审查批准；T-M5-011 执行中。

> 数据模型的实际完成条件是：开发机真实用户动作产生的资料、笔记、练习、错题、报告和备份数据可写入、重启回读并形成闭环；仅 schema 建立或 isolated fixture 通过不代表产品完成。
**上游**：[02-PRD v0.1.4 §3](./02-PRD-产品需求-Product-Requirements.md)、[03-Architecture v0.1.3 §4](./03-架构设计-Architecture-Design.md)
**下游**：06-API、07-Workflow、08-Test
**业务来源**：ai-studybuddy S1-S7 已验证数据模型业务认知迁移（不复制实现）

---

## 1. 数据库总览

### 1.1 数据库分布

| 数据库 | 路径 | 角色 | 引擎 |
|---|---|---|---|
| **全局库 global.db** | `%LOCALAPPDATA%\PiStudyBuddy\global.db` | 学期注册表 + 家长报告目标 + 备份记录 | SQLite (WAL) |
| **学期库 semester.db** | `%LOCALAPPDATA%\PiStudyBuddy\semester\<semester-id>\sem.db` | 单学期全量业务数据（S1-S7） | SQLite (WAL) |
| **L3 会话库** | `%LOCALAPPDATA%\PiStudyBuddy\memory\l3\conversation.sqlite` | 会话检索（FTS5 bigram） | SQLite (node:sqlite, Node≥22.5) |
| **L1 画像** | `%LOCALAPPDATA%\PiStudyBuddy\memory\l1\learner-profile.json` | 学习者画像（JSON + events.jsonl） | 文件 |
| **L2 知识库索引** | `%LOCALAPPDATA%\PiStudyBuddy\memory\l2\wiki-index\` | BM25 + 知识图谱 | 文件 + 内存 |
| **credential-vault** | `%LOCALAPPDATA%\PiStudyBuddy\config\credentials.json` | DPAPI 加密 JSON（值为 safeStorage 密文的 base64 表示） | 文件（尽力设置 0o600） |
| **pi 会话目录** | `~/.pi/agent/` | pi 自管（auth.json/models.json/settings.json） | pi 内核 |

### 1.2 物理隔离原则（TRD §7 决策 3）

- `~/.pi` 由 pi 自管，pi-studybuddy **不侵入**
- `%LOCALAPPDATA%\PiStudyBuddy` 是业务数据根，pi-studybuddy **自管**
- 单用户单机单写进程（WAL 模式）

### 1.3 全局库与学期库关系

```
global.db
  └ semesters (学期索引)
       │ db_relative_path
       ▼
  semester/<semester-id>/sem.db (学期库，按子系统分表)
       │ storage_key
       ▼
  semester/<semester-id>/storage/ (资料文件)
```

### 1.4 主键与 ID 规范

- **主键**：所有表用 `id TEXT PRIMARY KEY`（UUID v4，应用层生成）
- **外键**：`*_id TEXT` 引用父表 id；SQLite `PRAGMA foreign_keys = ON`
- **时间戳**：`created_at`/`updated_at` TEXT（ISO 8601 UTC）
- **软删除**：`deleted_at TEXT`（NULL 表示未删除）
- **UUID 泄漏防护**：家长报告 DTO 不含完整 UUID（02-PRD §5.2）

---

## 2. 全局库 global.db schema

### 2.1 semesters（学期索引）

> 02-PRD §3.2：全局库 semesters（学期索引，含 db_relative_path/ready 标志）

```sql
CREATE TABLE semesters (
  id TEXT PRIMARY KEY,                          -- UUID v4
  student_name TEXT NOT NULL,                   -- 学生姓名（单用户，但保留字段）
  semester_label TEXT NOT NULL,                 -- 学期标签（如 "2026 秋"）
  start_date TEXT NOT NULL,                     -- ISO 日期（学期开始）
  end_date TEXT NOT NULL,                       -- ISO 日期（学期结束）
  timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  status TEXT NOT NULL DEFAULT 'active'         -- active / teaching_ended / follow_up / archived
    CHECK (status IN ('active', 'teaching_ended', 'follow_up', 'archived')),
  db_relative_path TEXT NOT NULL,               -- 相对路径（如 "semester/2026-autumn/sem.db"）
  ready INTEGER NOT NULL DEFAULT 0,             -- 0=未就绪 1=就绪（学期库已初始化）
  archived_at TEXT,                             -- 归档时间（status=archived 时必填）
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  CHECK (end_date > start_date)
);

CREATE INDEX idx_semesters_status ON semesters(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_semesters_label ON semesters(semester_label);
```

### 2.2 parent_report_targets（家长报告目标配置）

> 02-PRD §3.7：全局库 parent_report_targets

```sql
CREATE TABLE parent_report_targets (
  id TEXT PRIMARY KEY,                          -- UUID v4
  semester_id TEXT NOT NULL REFERENCES semesters(id),
  target_name TEXT NOT NULL,                    -- 家长称谓（如 "妈妈"）
  channel_type TEXT NOT NULL                    -- local_export / smtp / feishu_webhook / print
    CHECK (channel_type IN ('local_export', 'smtp', 'feishu_webhook', 'print')),
  channel_config_json TEXT NOT NULL,             -- 渠道配置（脱敏存储，真实地址在 credential-vault）
                                                  -- smtp: {to_alias: "mom_email"} 真实邮箱在 vault
                                                  -- feishu_webhook: {webhook_alias: "mom_webhook"} 真实 URL 在 vault
                                                  -- local_export: {dir: "H:/Reports"}
  credential_key TEXT,                          -- credential-vault 键名（如 "parentContact:mom_email"）
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX idx_report_targets_semester ON parent_report_targets(semester_id) WHERE deleted_at IS NULL;
```

### 2.3 backup_records（备份历史）

> 02-PRD §3.10：全局库 backup_records（记录备份历史：课程 ID/备份时间/目标路径/content_hash/备份类型/状态）

```sql
CREATE TABLE backup_records (
  id TEXT PRIMARY KEY,                          -- UUID v4
  semester_id TEXT NOT NULL REFERENCES semesters(id),
  course_instance_id TEXT NOT NULL,             -- 学期库中的 course_instance.id（跨库引用，不建 FK）
  backup_type TEXT NOT NULL                     -- manual / scheduled / pre_archive / post_archive
    CHECK (backup_type IN ('manual', 'scheduled', 'pre_archive', 'post_archive')),
  target_path TEXT NOT NULL,                    -- 备份目标目录（学生自选本地路径）
  zip_filename TEXT NOT NULL,                   -- zip 文件名（如 "2026-autumn-math-20260807.zip"）
  content_hash TEXT NOT NULL,                   -- SHA-256（完整性校验）
  file_size_bytes INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'completed'     -- in_progress / completed / failed
    CHECK (status IN ('in_progress', 'completed', 'failed')),
  error_code TEXT,                              -- 失败时错误码（匹配 ^[A-Z][A-Z0-9_]{1,63}$）
  schedule_cron TEXT,                           -- 调度配置（scheduled 类型时记录 cron 表达式）
  started_at TEXT NOT NULL,
  completed_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_backup_semester ON backup_records(semester_id);
CREATE INDEX idx_backup_course ON backup_records(course_instance_id);
CREATE INDEX idx_backup_type ON backup_records(backup_type);
CREATE INDEX idx_backup_created ON backup_records(created_at DESC);
```

### 2.4 backup_schedules（备份调度配置）

> 02-PRD §3.10：默认每周一自动执行，学生可配置为每月一

```sql
CREATE TABLE backup_schedules (
  id TEXT PRIMARY KEY,
  semester_id TEXT NOT NULL REFERENCES semesters(id),
  course_instance_id TEXT,                      -- NULL=全课程，非空=指定课程
  cron_expression TEXT NOT NULL,                -- "0 0 * * 1"（每周一）或 "0 0 1 * *"（每月一）
  timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  enabled INTEGER NOT NULL DEFAULT 1,
  last_run_at TEXT,
  next_run_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_backup_sched_enabled ON backup_schedules(enabled) WHERE enabled = 1;
```

---

## 3. 学期库 semester.db schema（S1-S7）

> 每个学期独立 semester.db，按子系统分表。所有表的外键引用同库内表。

### 3.1 S1 学习节奏

#### 3.1.1 course_instances（课程实例）

```sql
CREATE TABLE course_instances (
  id TEXT PRIMARY KEY,
  semester_id TEXT NOT NULL,                    -- 引用 global.db semesters.id（跨库，不建 FK）
  course_name TEXT NOT NULL,                    -- 课程名（如 "高等数学"）
  subject TEXT NOT NULL,                        -- 学科（如 "数学"）
  teacher TEXT,                                 -- 教师姓名（可选）
  daily_minutes_target INTEGER DEFAULT 60,      -- 每日目标学习时长（分钟）
  available_time_json TEXT,                     -- 按星期的可用时间表（如 {"mon": 90, "tue": 60, ...}）
  target_score_json TEXT,                       -- 目标分数（结构化：{type: "percentage"|"grade", value: 85}）
  retake_of TEXT,                               -- 重修关联（引用另一 course_instance.id）
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX idx_course_semester ON course_instances(semester_id);
CREATE INDEX idx_course_subject ON course_instances(subject);
```

#### 3.1.2 assessment_attempts（考试尝试）

```sql
CREATE TABLE assessment_attempts (
  id TEXT PRIMARY KEY,
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  exam_name TEXT NOT NULL,                      -- 考试名（如 "期中考试"）
  exam_type TEXT NOT NULL                       -- midterm / final / makeup / retake / quiz
    CHECK (exam_type IN ('midterm', 'final', 'makeup', 'retake', 'quiz')),
  scheduled_date TEXT,                          -- 计划考试日期（ISO）
  actual_date TEXT,                             -- 实际考试日期（ISO）
  confirmation_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (confirmation_status IN ('pending', 'confirmed', 'rejected', 'superseded')),
  confirmed_at TEXT,
  confirmed_by TEXT,                            -- 'student' / 'ai_suggestion'（来源标记）
  source TEXT,                                  -- 来源（student_input / ocr_schedule / ai_extracted）
  confidence REAL,                               -- 置信度（0.0-1.0，AI 提取时填）
  change_history_json TEXT,                     -- 变更历史（JSON 数组）
  retake_of TEXT,                               -- 补考关联（引用另一 assessment_attempt.id）
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX idx_assessment_course ON assessment_attempts(course_instance_id);
CREATE INDEX idx_assessment_status ON assessment_attempts(confirmation_status);
CREATE INDEX idx_assessment_date ON assessment_attempts(scheduled_date);
```

#### 3.1.3 schedule_entries（课表条目）

```sql
CREATE TABLE schedule_entries (
  id TEXT PRIMARY KEY,
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),  -- 0=周日...6=周六
  start_time TEXT NOT NULL,                    -- "HH:MM"
  end_time TEXT NOT NULL,                      -- "HH:MM"
  location TEXT,                               -- 教室
  week_pattern TEXT DEFAULT 'every',          -- every / odd / even
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  CHECK (end_time > start_time)
);

CREATE INDEX idx_schedule_course ON schedule_entries(course_instance_id);
CREATE INDEX idx_schedule_weekday ON schedule_entries(weekday);
```

#### 3.1.4 study_tasks（学习任务）

```sql
CREATE TABLE study_tasks (
  id TEXT PRIMARY KEY,
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  title TEXT NOT NULL,
  description TEXT,
  task_type TEXT NOT NULL                       -- review / practice / note / exam_prep / other
    CHECK (task_type IN ('review', 'practice', 'note', 'exam_prep', 'other')),
  due_date TEXT,                                -- 截止日期（ISO）
  priority INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
  status TEXT NOT NULL DEFAULT 'pending'       -- pending / in_progress / completed / skipped
    CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped')),
  source_system TEXT NOT NULL,                 -- S1-S7（任务来源）
  source_ref_id TEXT,                           -- 来源对象 id（如 material.id / mistake.id）
  completed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX idx_task_course ON study_tasks(course_instance_id);
CREATE INDEX idx_task_status ON study_tasks(status);
CREATE INDEX idx_task_due ON study_tasks(due_date) WHERE deleted_at IS NULL;
```

#### 3.1.5 study_events（学习事件时间线）

```sql
CREATE TABLE study_events (
  id TEXT PRIMARY KEY,
  semester_id TEXT NOT NULL,
  course_instance_id TEXT REFERENCES course_instances(id),  -- 可空（学期级事件）
  event_type TEXT NOT NULL,                     -- 事件类型（见下方枚举）
  source_system TEXT NOT NULL CHECK (source_system IN ('S1','S2','S3','S4','S5','S6','S7')),
  source_ref_id TEXT,                           -- 来源对象 id
  event_data_json TEXT,                         -- 事件数据（脱敏聚合，不含原文）
  occurred_at TEXT NOT NULL,                    -- 事件发生时间（ISO）
  created_at TEXT NOT NULL
);

-- event_type 枚举（非穷举）：
-- semester_initialized / exam_added / exam_confirmed / task_completed
-- material_uploaded / note_generated / knowledge_module_created
-- practice_submitted / practice_graded
-- mistake_archived / error_cause_confirmed / weak_point_formed
-- mock_exam_completed / cram_card_viewed
-- report_generated / report_delivered
-- class_transcribed / class_handoff_saved
-- practice_reviewed（TTS 朗读标记"已复习"时写此事件）

CREATE INDEX idx_event_semester ON study_events(semester_id);
CREATE INDEX idx_event_course ON study_events(course_instance_id);
CREATE INDEX idx_event_type ON study_events(event_type);
CREATE INDEX idx_event_time ON study_events(occurred_at DESC);
```

### 3.2 S2 资料笔记

#### 3.2.1 materials（资料）

```sql
CREATE TABLE materials (
  id TEXT PRIMARY KEY,
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  file_name TEXT NOT NULL,                      -- 原始文件名
  file_type TEXT NOT NULL,                      -- pdf / docx / pptx / xlsx / txt / md / image / text / doc / ppt / xls
  file_size_bytes INTEGER NOT NULL,
  mime_type TEXT NOT NULL,                      -- MIME 类型（服务端验证，不信浏览器）
  storage_key TEXT NOT NULL,                    -- 相对路径（如 "semester/2026-autumn/storage/material-uuid.pdf"）
  source_type TEXT NOT NULL DEFAULT 'upload'   -- upload / class_audio_transcription（S7 handoff）
    CHECK (source_type IN ('upload', 'class_audio_transcription')),
  status TEXT NOT NULL DEFAULT 'pending'       -- 状态机
    CHECK (status IN ('pending', 'converting', 'converted', 'note_generating', 'completed',
                      'conversion_failed', 'pending_quality_check')),
  permission_confirmed INTEGER NOT NULL DEFAULT 0,  -- S7 课堂采集许可确认（0/1）
  uploaded_at TEXT NOT NULL,
  converted_at TEXT,
  note_generated_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX idx_material_course ON materials(course_instance_id);
CREATE INDEX idx_material_status ON materials(status);
```

#### 3.2.2 normalized_texts（归一化文本）

```sql
CREATE TABLE normalized_texts (
  id TEXT PRIMARY KEY,
  material_id TEXT NOT NULL REFERENCES materials(id),
  content TEXT NOT NULL,                       -- 归一化纯文本
  content_hash TEXT NOT NULL,                  -- SHA-256（去重用）
  char_count INTEGER NOT NULL,
  source_type TEXT,                             -- class_audio_transcription（S7）或其他
  extraction_meta_json TEXT,                    -- 提取元信息（页数/OCR 置信度等）
  created_at TEXT NOT NULL,
  UNIQUE(material_id)
);

CREATE INDEX idx_normtext_material ON normalized_texts(material_id);
CREATE INDEX idx_normtext_hash ON normalized_texts(content_hash);
```

#### 3.2.3 structured_notes（结构化笔记）

```sql
CREATE TABLE structured_notes (
  id TEXT PRIMARY KEY,
  material_id TEXT NOT NULL REFERENCES materials(id),
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  note_markdown TEXT NOT NULL,                 -- Markdown 笔记正文
  highlights_json TEXT,                         -- 高亮（JSON 数组）
  prompt_version TEXT NOT NULL,                 -- AI prompt 版本
  model TEXT NOT NULL,                          -- AI 模型标识
  token_count INTEGER,                          -- token 用量
  ai_generated INTEGER NOT NULL DEFAULT 1,      -- 0=规则生成 1=AI 生成（必须标注）
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(material_id)
);

CREATE INDEX idx_note_material ON structured_notes(material_id);
CREATE INDEX idx_note_course ON structured_notes(course_instance_id);
```

#### 3.2.4 mind_maps（思维导图）

```sql
CREATE TABLE mind_maps (
  id TEXT PRIMARY KEY,
  material_id TEXT NOT NULL REFERENCES materials(id),
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  markmap_json TEXT NOT NULL,                  -- Markmap 格式 JSON
  created_at TEXT NOT NULL,
  UNIQUE(material_id)
);

CREATE INDEX idx_mindmap_material ON mind_maps(material_id);
```

#### 3.2.5 knowledge_modules（知识模块）

> 02-PRD §3.3：知识模块必须带 source_evidence 回链（降低幻觉的关键约束）

```sql
CREATE TABLE knowledge_modules (
  id TEXT PRIMARY KEY,
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  material_id TEXT NOT NULL REFERENCES materials(id),
  module_name TEXT NOT NULL,                   -- 模块名
  summary TEXT,                                -- 模块摘要
  importance INTEGER CHECK (importance BETWEEN 1 AND 5),  -- 重要性
  difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 5),  -- 难度
  learn_status TEXT NOT NULL DEFAULT 'not_started'
    CHECK (learn_status IN ('not_started', 'learning', 'mastered', 'needs_review')),
  source_evidence_json TEXT NOT NULL,          -- 回链（JSON：{material_id, section, page, chunk_id, evidence_text}）
  ai_generated INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX idx_kmodule_course ON knowledge_modules(course_instance_id);
CREATE INDEX idx_kmodule_material ON knowledge_modules(material_id);
CREATE INDEX idx_kmodule_status ON knowledge_modules(learn_status);
```

#### 3.2.6 material_chunks（资料分块）

```sql
CREATE TABLE material_chunks (
  id TEXT PRIMARY KEY,
  material_id TEXT NOT NULL REFERENCES materials(id),
  chunk_index INTEGER NOT NULL,                -- 分块序号
  content TEXT NOT NULL,                        -- 分块文本
  section_path TEXT,                            -- 章节路径（如 "第3章/3.2 节"）
  page_number INTEGER,                          -- 页码（PDF）
  char_count INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(material_id, chunk_index)
);

CREATE INDEX idx_chunk_material ON material_chunks(material_id);
CREATE INDEX idx_chunk_section ON material_chunks(section_path);
```

#### 3.2.7 jobs（转换/生成作业）

```sql
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  material_id TEXT NOT NULL REFERENCES materials(id),
  job_type TEXT NOT NULL                       -- convert_pdf / convert_docx / convert_pptx / ocr_image / wps_convert / generate_note
    CHECK (job_type IN ('convert_pdf', 'convert_docx', 'convert_pptx', 'convert_xlsx',
                        'ocr_image', 'wps_convert', 'generate_note')),
  status TEXT NOT NULL DEFAULT 'pending'       -- pending / running / completed / failed
    CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 3,
  error_code TEXT,
  error_message TEXT,                          -- 中文可操作消息
  started_at TEXT,
  completed_at TEXT,
  timeout_ms INTEGER,                           -- 超时（毫秒）
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_job_material ON jobs(material_id);
CREATE INDEX idx_job_status ON jobs(status);
```

### 3.3 S3 限时练习

#### 3.3.1 questions（题目）

> 02-PRD §3.4：作答前 DTO 不含 correct_answer/acceptable_answers/explanation（防泄露）

```sql
CREATE TABLE questions (
  id TEXT PRIMARY KEY,
  practice_session_id TEXT,                    -- 归属 session（可空，模拟卷题目归属 mock_exam_paper）
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  knowledge_module_id TEXT REFERENCES knowledge_modules(id),
  question_type TEXT NOT NULL                   -- single_choice / multiple_choice / fill_blank
    CHECK (question_type IN ('single_choice', 'multiple_choice', 'fill_blank')),
  question_stem TEXT NOT NULL,                  -- 题干
  options_json TEXT,                            -- 选项（JSON 数组，选择题必填）
  correct_answer TEXT,                          -- 标准答案（作答后返回，DTO 隔离）
  acceptable_answers_json TEXT,                 -- 可接受答案（填空题多等价答案 OR）
  explanation TEXT,                             -- 解析（作答后返回）
  score INTEGER NOT NULL DEFAULT 1,             -- 分值
  difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 5),
  source_evidence_json TEXT,                    -- 来源回链
  ai_model TEXT,                                -- 生成模型
  prompt_version TEXT,
  source_hash TEXT,                             -- 防重复生成
  created_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE INDEX idx_question_session ON questions(practice_session_id);
CREATE INDEX idx_question_course ON questions(course_instance_id);
CREATE INDEX idx_question_module ON questions(knowledge_module_id);
```

#### 3.3.2 practice_sessions（练习会话）

```sql
CREATE TABLE practice_sessions (
  id TEXT PRIMARY KEY,
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  question_count INTEGER NOT NULL CHECK (question_count BETWEEN 5 AND 20),
  time_limit_minutes INTEGER,                   -- 限时（可空=不限时）
  difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 5),
  question_types_json TEXT NOT NULL,            -- 题型分布 {"single":60,"multiple":20,"fill":20}
  module_ids_json TEXT NOT NULL,                -- 选择的模块 id 列表
  status TEXT NOT NULL DEFAULT 'in_progress'   -- in_progress / submitted / graded
    CHECK (status IN ('in_progress', 'submitted', 'graded')),
  started_at TEXT NOT NULL,
  submitted_at TEXT,
  graded_at TEXT,
  total_score INTEGER,                          -- 总分
  max_score INTEGER,                            -- 满分
  correct_count INTEGER,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_psession_course ON practice_sessions(course_instance_id);
CREATE INDEX idx_psession_status ON practice_sessions(status);
```

#### 3.3.3 practice_answers（答题记录）

```sql
CREATE TABLE practice_answers (
  id TEXT PRIMARY KEY,
  practice_session_id TEXT NOT NULL REFERENCES practice_sessions(id),
  question_id TEXT NOT NULL REFERENCES questions(id),
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  student_answer TEXT,                          -- 学生作答
  is_correct INTEGER,                           -- 0/1/NULL（未批改）
  graded_at TEXT,
  time_spent_ms INTEGER,                         -- 单题耗时
  created_at TEXT NOT NULL,
  UNIQUE(practice_session_id, question_id)
);

CREATE INDEX idx_panswer_session ON practice_answers(practice_session_id);
CREATE INDEX idx_panswer_question ON practice_answers(question_id);
CREATE INDEX idx_panswer_correct ON practice_answers(is_correct) WHERE is_correct = 0;
```

### 3.4 S4 错题改错

#### 3.4.1 mistakes（错题）

> 02-PRD §3.5：幂等归档 UNIQUE(question_id)

```sql
CREATE TABLE mistakes (
  id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL REFERENCES questions(id),
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  knowledge_module_id TEXT REFERENCES knowledge_modules(id),
  error_cause TEXT,                              -- 错因正文（学生确认，不进 S6 报告）
  error_cause_category TEXT                      -- 六分类
    CHECK (error_cause_category IN ('concept_unclear', 'misread', 'formula_error',
                                     'step_missing', 'time_pressure', 'other')),
  error_cause_confirmed_by TEXT,                -- 'student' / NULL（未确认）
  error_cause_ai_suggestion TEXT,               -- AI 建议（带"不确定"标记）
  status TEXT NOT NULL DEFAULT 'needs_review'  -- needs_review / mastered
    CHECK (status IN ('needs_review', 'mastered')),
  redo_count INTEGER NOT NULL DEFAULT 0,
  last_redo_correct INTEGER,                    -- 最近一次重做是否正确（0/1/NULL）
  mastered_at TEXT,                              -- 掌握时间（可回退到 needs_review）
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(question_id)                           -- 幂等归档：同一 question 唯一
);

CREATE INDEX idx_mistake_course ON mistakes(course_instance_id);
CREATE INDEX idx_mistake_module ON mistakes(knowledge_module_id);
CREATE INDEX idx_mistake_status ON mistakes(status);
```

#### 3.4.2 mistake_evidence（错题证据）

> 02-PRD §3.5：幂等归档 UNIQUE(source_practice_answer_id)

```sql
CREATE TABLE mistake_evidence (
  id TEXT PRIMARY KEY,
  mistake_id TEXT NOT NULL REFERENCES mistakes(id),
  source_practice_answer_id TEXT NOT NULL REFERENCES practice_answers(id),
  evidence_type TEXT NOT NULL DEFAULT 'initial_wrong'
    CHECK (evidence_type IN ('initial_wrong', 'redo_wrong')),
  recorded_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(source_practice_answer_id)            -- 幂等：同一答题唯一
);

CREATE INDEX idx_mevidence_mistake ON mistake_evidence(mistake_id);
```

#### 3.4.3 weak_points（薄弱点）

> 02-PRD §3.5：需 evidence_count≥2 才形成；UNIQUE(course_instance_id, knowledge_module_id)

```sql
CREATE TABLE weak_points (
  id TEXT PRIMARY KEY,
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  knowledge_module_id TEXT NOT NULL REFERENCES knowledge_modules(id),
  evidence_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active'         -- active / resolved / regressed
    CHECK (status IN ('active', 'resolved', 'regressed')),
  first_evidenced_at TEXT NOT NULL,
  last_evidenced_at TEXT NOT NULL,
  resolved_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(course_instance_id, knowledge_module_id),
  CHECK (evidence_count >= 2)                   -- 形成薄弱点的必要条件
);

CREATE INDEX idx_weak_course ON weak_points(course_instance_id);
CREATE INDEX idx_weak_module ON weak_points(knowledge_module_id);
CREATE INDEX idx_weak_status ON weak_points(status);
```

### 3.5 S5 期末冲刺

#### 3.5.1 mock_exam_papers（模拟卷）

> 02-PRD §3.6：触发器校验 assessment_attempt 必须 confirmed

```sql
CREATE TABLE mock_exam_papers (
  id TEXT PRIMARY KEY,
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  assessment_attempt_id TEXT NOT NULL REFERENCES assessment_attempts(id),
  paper_title TEXT NOT NULL,
  question_count INTEGER NOT NULL,
  time_limit_minutes INTEGER,
  total_score INTEGER NOT NULL,
  source_hash TEXT NOT NULL,                    -- 防重复生成
  ai_model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_mockpaper_course ON mock_exam_papers(course_instance_id);
CREATE INDEX idx_mockpaper_attempt ON mock_exam_papers(assessment_attempt_id);
CREATE INDEX idx_mockpaper_hash ON mock_exam_papers(source_hash);
```

#### 3.5.2 mock_exam_questions（模拟卷题目）

> 02-PRD §3.6：CHECK 约束选择题 vs 填空题字段互斥

```sql
CREATE TABLE mock_exam_questions (
  id TEXT PRIMARY KEY,
  mock_paper_id TEXT NOT NULL REFERENCES mock_exam_papers(id),
  question_index INTEGER NOT NULL,
  question_type TEXT NOT NULL
    CHECK (question_type IN ('single_choice', 'multiple_choice', 'fill_blank')),
  question_stem TEXT NOT NULL,
  options_json TEXT,                            -- 选择题选项（填空题为 NULL）
  correct_answer TEXT,
  acceptable_answers_json TEXT,
  explanation TEXT,
  score INTEGER NOT NULL,
  knowledge_module_id TEXT REFERENCES knowledge_modules(id),
  created_at TEXT NOT NULL,
  -- CHECK 约束：选择题必有 options，填空题无 options
  CHECK (
    (question_type IN ('single_choice', 'multiple_choice') AND options_json IS NOT NULL)
    OR
    (question_type = 'fill_blank' AND options_json IS NULL)
  ),
  UNIQUE(mock_paper_id, question_index)
);

CREATE INDEX idx_mquestion_paper ON mock_exam_questions(mock_paper_id);
```

#### 3.5.3 mock_exam_attempts（模拟考作答）

```sql
CREATE TABLE mock_exam_attempts (
  id TEXT PRIMARY KEY,
  mock_paper_id TEXT NOT NULL REFERENCES mock_exam_papers(id),
  course_instance_id TEXT NOT NULL REFERENCES course_instances(id),
  status TEXT NOT NULL DEFAULT 'in_progress'   -- in_progress / submitted / graded
    CHECK (status IN ('in_progress', 'submitted', 'graded')),
  started_at TEXT NOT NULL,
  submitted_at TEXT,
  graded_at TEXT,
  total_score INTEGER,
  max_score INTEGER,
  correct_count INTEGER,
  duration_ms INTEGER,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_mattempt_paper ON mock_exam_attempts(mock_paper_id);
CREATE INDEX idx_mattempt_status ON mock_exam_attempts(status);
```

#### 3.5.4 mock_exam_answers（模拟考答题）

```sql
CREATE TABLE mock_exam_answers (
  id TEXT PRIMARY KEY,
  mock_attempt_id TEXT NOT NULL REFERENCES mock_exam_attempts(id),
  mock_question_id TEXT NOT NULL REFERENCES mock_exam_questions(id),
  student_answer TEXT,
  is_correct INTEGER,
  time_spent_ms INTEGER,
  created_at TEXT NOT NULL,
  UNIQUE(mock_attempt_id, mock_question_id)
);

CREATE INDEX idx_manswer_attempt ON mock_exam_answers(mock_attempt_id);
CREATE INDEX idx_manswer_question ON mock_exam_answers(mock_question_id);
```

#### 3.5.5 mock_exam_module_analyses（模拟考模块分析）

```sql
CREATE TABLE mock_exam_module_analyses (
  id TEXT PRIMARY KEY,
  mock_attempt_id TEXT NOT NULL REFERENCES mock_exam_attempts(id),
  knowledge_module_id TEXT NOT NULL REFERENCES knowledge_modules(id),
  total_questions INTEGER NOT NULL,
  correct_count INTEGER NOT NULL,
  accuracy_rate REAL NOT NULL,                  -- 正确率
  weakness_level TEXT NOT NULL                  -- 强弱项分析
    CHECK (weakness_level IN ('strong', 'medium', 'weak')),
  created_at TEXT NOT NULL,
  UNIQUE(mock_attempt_id, knowledge_module_id)
);

CREATE INDEX idx_manalysis_attempt ON mock_exam_module_analyses(mock_attempt_id);
```

### 3.6 S6 家长报告

#### 3.6.1 parent_reports（家长报告）

> 02-PRD §3.7：PK report_key；冻结快照 content_json + content_hash

```sql
CREATE TABLE parent_reports (
  report_key TEXT PRIMARY KEY,                  -- 报告唯一键（如 "2026-autumn-weekly-2026-W32"）
  semester_id TEXT NOT NULL,
  report_type TEXT NOT NULL                     -- daily / weekly / monthly / exam_reminder
    CHECK (report_type IN ('daily', 'weekly', 'monthly', 'exam_reminder')),
  period_start TEXT NOT NULL,                   -- 报告周期开始（ISO）
  period_end TEXT NOT NULL,                     -- 报告周期结束（ISO）
  content_json TEXT NOT NULL,                  -- 冻结脱敏快照（5 section + data_quality）
  content_hash TEXT NOT NULL,                   -- SHA-256（保证投递一致）
  rule_generated INTEGER NOT NULL DEFAULT 1,    -- 0=AI 润色 1=规则生成
  ai_polished INTEGER NOT NULL DEFAULT 0,
  ai_model TEXT,
  prompt_version TEXT,
  privacy_check_passed INTEGER NOT NULL DEFAULT 1,  -- assertNoSensitiveLeak 结果
  generated_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_report_semester ON parent_reports(semester_id);
CREATE INDEX idx_report_type ON parent_reports(report_type);
CREATE INDEX idx_report_period ON parent_reports(period_start, period_end);
```

#### 3.6.2 report_deliveries（报告投递）

> 02-PRD §3.7：PK report_key+channel；至少一次投递语义

```sql
CREATE TABLE report_deliveries (
  report_key TEXT NOT NULL REFERENCES parent_reports(report_key),
  channel TEXT NOT NULL                         -- local_export / smtp / feishu_webhook / print
    CHECK (channel IN ('local_export', 'smtp', 'feishu_webhook', 'print')),
  status TEXT NOT NULL DEFAULT 'pending'        -- pending / sent / failed / retained_locally
    CHECK (status IN ('pending', 'sent', 'failed', 'retained_locally')),
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 3,
  error_code TEXT,
  sent_at TEXT,
  last_attempt_at TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (report_key, channel)
);

CREATE INDEX idx_delivery_status ON report_deliveries(status);
```

---

## 4. 三层记忆 schema

### 4.1 L1 学习者画像（JSON）

> 03-Architecture §4.2：profile.json + events.jsonl

**文件**：`%LOCALAPPDATA%\PiStudyBuddy\memory\l1\learner-profile.json`

```json
{
  "version": "1.0",
  "student_id": "local-student",
  "basic_info": {
    "name": "学生姓名",
    "grade_level": "K12|大学|自考",
    "available_time_per_weekday": {"mon": 90, "tue": 60, "wed": 90, "thu": 60, "fri": 120, "sat": 180, "sun": 180}
  },
  "learning_preferences": {
    "preferred_subjects": ["数学", "物理"],
    "difficulty_tolerance": 3,
    "review_style": "spaced_repetition"
  },
  "weak_points_summary": [
    {"subject": "数学", "module": "极限", "evidence_count": 3, "last_evidenced": "2026-08-01"}
  ],
  "goals": [
    {"course": "高等数学", "target_score": {"type": "percentage", "value": 85}}
  ],
  "study_patterns": {
    "avg_daily_minutes": 75,
    "most_productive_time": "evening",
    "consistency_score": 0.8
  },
  "updated_at": "2026-08-07T12:00:00Z"
}
```

**事件流**：`%LOCALAPPDATA%\PiStudyBuddy\memory\l1\events.jsonl`（每行一个 StudyEvent 摘要）

### 4.2 L2 知识库（BM25 + 知识图谱）

> 03-Architecture §4.2：简化为 BM25 + DIRECT_LINK

**索引目录**：`%LOCALAPPDATA%\PiStudyBuddy\memory\l2\wiki-index\`

**BM25 索引结构**（内存 + 文件持久化）：
- `inverted_index.json`：词 → 文档 id 列表 + TF
- `doc_lengths.json`：文档长度（用于 BM25 计算）
- `avg_doc_length`：平均文档长度

**知识图谱**（DIRECT_LINK 简化版）：
- `graph_nodes.json`：节点（knowledge_module / material / question）
- `graph_edges.json`：边（DIRECT_LINK 权重 0.5）

```json
// graph_edges.json 示例
[
  {"source": "km-uuid-1", "target": "material-uuid-1", "type": "DIRECT_LINK", "weight": 0.5},
  {"source": "km-uuid-1", "target": "question-uuid-1", "type": "DIRECT_LINK", "weight": 0.5}
]
```

### 4.3 L3 会话检索（SQLite FTS5）

> 03-Architecture §4.2：借鉴 inno-agent sqlite-store.ts，基于 node:sqlite

**对话 Tab 承载**（02-PRD §3.11 + 03-Architecture §6.7 + 09-UI §4.2）："💬 对话"标签页（默认主入口）的会话即 pi 会话，`session_id` 字段引用 pi 会话 id；对话内容经 `turn_end` 钩子增量索引（基于 `last_offset` + `last_mtime_ms`）到此表，供学生在对话 Tab 内检索历史问答。

**文件**：`%LOCALAPPDATA%\PiStudyBuddy\memory\l3\conversation.sqlite`

```sql
-- chunks 表
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,                    -- pi 会话 id
  content TEXT NOT NULL,                       -- 原始内容
  role TEXT NOT NULL,                          -- user / assistant / tool
  source_type TEXT,                            -- message / tool_result
  created_at TEXT NOT NULL,
  last_offset INTEGER NOT NULL,               -- 增量索引用
  last_mtime_ms INTEGER NOT NULL
);

CREATE INDEX idx_chunk_session ON chunks(session_id);
CREATE INDEX idx_chunk_offset ON chunks(last_offset);

-- FTS5 全文索引（bigram 分词）
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  content,
  content='chunks',
  content_rowid='rowid',
  tokenize='unicode61'
);

-- bigram 分词由应用层实现（CJK 切 bigram），写入 chunks_fts
-- 查询：OR-combined MATCH
```

**bigram 分词示例**（应用层）：
```
"学习计划" → "学习" "习计" "计划"
"高等数学" → "高等" "等数" "数学"
ASCII 整词小写："practice" → "practice"
```

---

## 5. ER 关系图

### 5.1 全局库 ER 图

```
semesters (PK: id)
  ├ 1:N → parent_report_targets (FK: semester_id)
  ├ 1:N → backup_records (FK: semester_id)
  ├ 1:N → backup_schedules (FK: semester_id)
  └ 1:N → semester.db (跨库引用 db_relative_path)
```

### 5.2 学期库 ER 图（核心关系）

```
course_instances (PK: id)
  ├ 1:N → assessment_attempts (FK: course_instance_id)
  ├ 1:N → schedule_entries (FK: course_instance_id)
  ├ 1:N → study_tasks (FK: course_instance_id)
  ├ 1:N → materials (FK: course_instance_id)
  ├ 1:N → knowledge_modules (FK: course_instance_id)
  ├ 1:N → practice_sessions (FK: course_instance_id)
  ├ 1:N → mistakes (FK: course_instance_id)
  ├ 1:N → weak_points (FK: course_instance_id)
  ├ 1:N → mock_exam_papers (FK: course_instance_id)
  └ 1:N → study_events (FK: course_instance_id)

materials (PK: id)
  ├ 1:1 → normalized_texts (FK: material_id, UNIQUE)
  ├ 1:1 → structured_notes (FK: material_id, UNIQUE)
  ├ 1:1 → mind_maps (FK: material_id, UNIQUE)
  ├ 1:N → knowledge_modules (FK: material_id)
  ├ 1:N → material_chunks (FK: material_id)
  └ 1:N → jobs (FK: material_id)

knowledge_modules (PK: id)
  ├ N:1 → materials (FK: material_id)
  ├ N:1 → course_instances (FK: course_instance_id)
  ├ 1:N → questions (FK: knowledge_module_id)
  ├ 1:N → weak_points (FK: knowledge_module_id)
  └ 1:N → mock_exam_module_analyses (FK: knowledge_module_id)

practice_sessions (PK: id)
  ├ N:1 → course_instances (FK: course_instance_id)
  ├ 1:N → questions (FK: practice_session_id)
  └ 1:N → practice_answers (FK: practice_session_id)

questions (PK: id)
  ├ N:1 → practice_sessions (FK: practice_session_id)
  ├ N:1 → knowledge_modules (FK: knowledge_module_id)
  └ 1:1 → mistakes (FK: question_id, UNIQUE)

practice_answers (PK: id)
  ├ N:1 → practice_sessions (FK: practice_session_id)
  ├ N:1 → questions (FK: question_id)
  └ 1:1 → mistake_evidence (FK: source_practice_answer_id, UNIQUE)

mistakes (PK: id)
  ├ 1:1 → questions (FK: question_id, UNIQUE)
  └ 1:N → mistake_evidence (FK: mistake_id)

assessment_attempts (PK: id)
  ├ N:1 → course_instances (FK: course_instance_id)
  └ 1:N → mock_exam_papers (FK: assessment_attempt_id)

mock_exam_papers (PK: id)
  ├ N:1 → assessment_attempts (FK: assessment_attempt_id)
  ├ 1:N → mock_exam_questions (FK: mock_paper_id)
  └ 1:N → mock_exam_attempts (FK: mock_paper_id)

mock_exam_attempts (PK: id)
  ├ N:1 → mock_exam_papers (FK: mock_paper_id)
  ├ 1:N → mock_exam_answers (FK: mock_attempt_id)
  └ 1:N → mock_exam_module_analyses (FK: mock_attempt_id)
```

### 5.3 跨子系统数据流

```
S1 course_instances
  ↓
S2 materials → normalized_texts → structured_notes → knowledge_modules
  ↓                                              ↓
S3 questions ← practice_sessions              material_chunks
  ↓
S4 mistakes ← practice_answers (is_correct=0)
  ↓ mistake_evidence (evidence_count≥2)
S4 weak_points
  ↓
S5 mock_exam_papers ← assessment_attempts (confirmed)
  ↓ mock_exam_questions ← knowledge_modules
S5 mock_exam_attempts → mock_exam_module_analyses
  ↓
S6 parent_reports (脱敏聚合) → report_deliveries
```

---

## 6. 触发器

### 6.1 S4 关系一致性触发器（6 个）

> 02-PRD §3.5：6 个关系一致性触发器校验 question/course/module/answer 关系

```sql
-- T1: question.course_instance_id 必须匹配 practice_session.course_instance_id
CREATE TRIGGER trg_question_course_consistency
BEFORE INSERT ON questions
FOR EACH ROW
WHEN NEW.practice_session_id IS NOT NULL
BEGIN
  SELECT CASE
    WHEN (SELECT course_instance_id FROM practice_sessions WHERE id = NEW.practice_session_id)
         != NEW.course_instance_id
    THEN RAISE(ABORT, 'question course mismatch with practice session')
  END;
END;

-- T2: mistake.question_id 必须存在且 course 一致
CREATE TRIGGER trg_mistake_question_consistency
BEFORE INSERT ON mistakes
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN (SELECT course_instance_id FROM questions WHERE id = NEW.question_id)
         != NEW.course_instance_id
    THEN RAISE(ABORT, 'mistake course mismatch with question')
  END;
END;

-- T3: mistake_evidence.source_practice_answer_id 必须关联同一 mistake 的 question
CREATE TRIGGER trg_evidence_answer_consistency
BEFORE INSERT ON mistake_evidence
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN (SELECT question_id FROM mistakes WHERE id = NEW.mistake_id)
         != (SELECT question_id FROM practice_answers WHERE id = NEW.source_practice_answer_id)
    THEN RAISE(ABORT, 'evidence answer does not belong to mistake question')
  END;
END;

-- T4: weak_points.course + module 必须一致（knowledge_module 属于 course）
CREATE TRIGGER trg_weakpoint_consistency
BEFORE INSERT ON weak_points
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN (SELECT course_instance_id FROM knowledge_modules WHERE id = NEW.knowledge_module_id)
         != NEW.course_instance_id
    THEN RAISE(ABORT, 'weak point module does not belong to course')
  END;
END;

-- T5: practice_answers.question_id 必须属于 practice_session
CREATE TRIGGER trg_answer_session_consistency
BEFORE INSERT ON practice_answers
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN (SELECT practice_session_id FROM questions WHERE id = NEW.question_id)
         != NEW.practice_session_id
    THEN RAISE(ABORT, 'answer question does not belong to practice session')
  END;
END;

-- T6: mistake.knowledge_module_id 必须匹配 question 的 module
CREATE TRIGGER trg_mistake_module_consistency
BEFORE INSERT ON mistakes
FOR EACH ROW
WHEN NEW.knowledge_module_id IS NOT NULL
BEGIN
  SELECT CASE
    WHEN (SELECT knowledge_module_id FROM questions WHERE id = NEW.question_id)
         != NEW.knowledge_module_id
    THEN RAISE(ABORT, 'mistake module mismatch with question module')
  END;
END;
```

### 6.2 storage_key 路径逃逸防护触发器

> 02-PRD §3.3：storage_key 相对路径，触发器拒绝 `..`/`:\`/`:/`

```sql
CREATE TRIGGER trg_material_storage_key_safety
BEFORE INSERT ON materials
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN NEW.storage_key LIKE '%..%' OR NEW.storage_key LIKE '%:%' OR NEW.storage_key LIKE '%:/%'
    THEN RAISE(ABORT, 'storage_key path escape attempt detected')
  END;
END;
```

### 6.3 mock_exam_papers 校验 assessment_attempt confirmed

> 02-PRD §3.6：触发器校验 assessment_attempt 必须 confirmed

```sql
CREATE TRIGGER trg_mockpaper_attempt_confirmed
BEFORE INSERT ON mock_exam_papers
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN (SELECT confirmation_status FROM assessment_attempts WHERE id = NEW.assessment_attempt_id)
         != 'confirmed'
    THEN RAISE(ABORT, 'mock exam requires confirmed assessment attempt')
  END;
END;
```

### 6.4 mistake_evidence 幂等归档触发器

> 02-PRD §3.5：幂等归档（同一 question 唯一，重复扫描不重复建）

```sql
-- 归档前检查：同一 question 已有 mistake 则不重复建，仅追加 evidence
CREATE TRIGGER trg_mistake_idempotent_archive
BEFORE INSERT ON mistakes
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN EXISTS (SELECT 1 FROM mistakes WHERE question_id = NEW.question_id)
    THEN RAISE(ABORT, 'mistake already exists for this question, append evidence instead')
  END;
END;
```

---

## 7. 索引汇总

### 7.1 全局库索引

| 表 | 索引 | 用途 |
|---|---|---|
| semesters | idx_semesters_status | 按状态查询活跃学期 |
| semesters | idx_semesters_label | 按标签搜索 |
| parent_report_targets | idx_report_targets_semester | 按学期查报告目标 |
| backup_records | idx_backup_semester | 按学期查备份 |
| backup_records | idx_backup_course | 按课程查备份 |
| backup_records | idx_backup_type | 按类型查备份 |
| backup_records | idx_backup_created | 按时间倒序 |
| backup_schedules | idx_backup_sched_enabled | 查启用的调度 |

### 7.2 学期库索引（关键）

| 表 | 索引 | 用途 |
|---|---|---|
| course_instances | idx_course_semester | 按学期查课程 |
| assessment_attempts | idx_assessment_status | 按确认状态查考试 |
| assessment_attempts | idx_assessment_date | 按日期查考试 |
| materials | idx_material_status | 按状态查资料（转换队列） |
| knowledge_modules | idx_kmodule_status | 按学习状态查模块 |
| questions | idx_question_session | 按练习会话查题目 |
| practice_answers | idx_panswer_correct | 查错题（is_correct=0） |
| mistakes | idx_mistake_status | 按状态查错题 |
| weak_points | idx_weak_status | 按状态查薄弱点 |
| study_events | idx_event_time | 按时间查事件 |
| study_events | idx_event_type | 按类型查事件 |

---

## 8. 数据迁移与备份

### 8.1 备份 zip 内部结构

> 02-PRD §3.10：备份 zip 内部结构约定见 07-Workflow（此处定义结构）

```
<course-name>-<backup-date>.zip
  ├ manifest.json                          ← 备份清单
  │  {
  │    "course_instance_id": "uuid",
  │    "course_name": "高等数学",
  │    "semester_id": "uuid",
  │    "semester_label": "2026 秋",
  │    "backup_type": "manual",
  │    "backup_date": "2026-08-07",
  │    "content_hash": "sha256...",
  │    "schema_version": "1.0",
  │    "tables": ["course_instances", "materials", ...],
  │    "file_count": 15,
  │    "total_size_bytes": 12345678
  │  }
  ├ data/
  │  ├ course_instances.jsonl              ← 按 course_instance_id 过滤导出
  │  ├ materials.jsonl
  │  ├ normalized_texts.jsonl
  │  ├ structured_notes.jsonl
  │  ├ knowledge_modules.jsonl
  │  ├ ... (该课程所有相关表)
  │  └ ...
  └ storage/                               ← 该课程 storage_key 指向的资料文件
     ├ material-uuid-1.pdf
     ├ material-uuid-2.docx
     └ ...
```

### 8.2 恢复流程

1. 解压 zip 到临时目录
2. 读取 `manifest.json`，校验 `content_hash`
3. 校验 `schema_version` 兼容性
4. 检查目标学期是否存在同名课程（冲突时学生确认覆盖/新建）
5. 导入 `data/*.jsonl` 到 semester.db（按 course_instance_id）
6. 复制 `storage/` 文件到目标学期 storage 目录
7. 写 `backup_records`（备份类型 `manual` 恢复记录）

### 8.3 SQLite 崩溃恢复

- **WAL 模式**：默认开启（`PRAGMA journal_mode = WAL`）
- **定期 zip 备份**：每周一/每月一（02-PRD §3.10）
- **崩溃后恢复**：从最近 backup_records 找到成功备份，最多丢失一个备份周期数据
- **完整性检查**：恢复后 `PRAGMA integrity_check`

---

## 9. PRAGMA 配置

```sql
-- 每个 SQLite 数据库初始化时执行
PRAGMA journal_mode = WAL;              -- 写前日志，支持并发读
PRAGMA synchronous = NORMAL;           -- WAL 模式下 NORMAL 足够安全
PRAGMA foreign_keys = ON;              -- 启用外键约束
PRAGMA busy_timeout = 5000;            -- 忙等待 5 秒
PRAGMA cache_size = -64000;            -- 64MB 缓存
PRAGMA temp_store = MEMORY;            -- 临时表存内存
PRAGMA mmap_size = 268435456;          -- 256MB 内存映射
```

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
| v0.1.2 | 2026-08-09 | 交叉审查修订：credential-vault 路径与实现统一为业务数据根 `config/credentials.json`，不再描述不存在的 `credential-vault/*.enc` 文件树。 |
| v0.1.1 | 2026-08-07 | §4.3 L3 会话检索补"对话 Tab 承载"注——"💬 对话"标签页会话即 pi 会话，session_id 引用 pi 会话 id，对话内容经 turn_end 钩子增量索引到此表（02-PRD §3.11 + 03-Architecture §6.7 + 09-UI §4.2 贯通） |
| v0.1.0 | 2026-08-07 | 初始草案：全局库 schema（semesters/parent_report_targets/backup_records/backup_schedules）；学期库 schema（S1-S7 全量表 30+）；三层记忆 schema（L1 JSON/L2 BM25+图谱/L3 FTS5 bigram）；ER 关系图（全局库 + 学期库核心关系 + 跨子系统数据流）；触发器（6 个 S4 关系一致性 + storage_key 路径逃逸防护 + mock_exam confirmed 校验 + 幂等归档）；索引汇总；备份 zip 内部结构 + 恢复流程；PRAGMA 配置。输入：02-PRD §3 数据契约 + 03-Architecture §4 数据层 + ai-studybuddy S1-S7 业务认知迁移 |

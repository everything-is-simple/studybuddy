# 历史版本核心场景设计回顾

> 更新：2026-08-25
>
> 本文从祖宗版本（`H:\kaobuddy-remote-audit`）和两个前辈版本（`H:\ai-studybuddy`、`H:\pi-studybuddy`）的核心设计文档中提取场景设计，用于为 StudyBuddy 正式系统 AI Phase 4 及后续阶段提供产品范围和契约参考。
>
> 这些版本只用于提取契约和设计教训；不得直接复制源码。

## 一、祖宗版本：考搭子 KaoBuddy（PWA / 浏览器本地）

来源：`H:\kaobuddy-remote-audit/README.md`、`DESIGN.md`、`PRODUCT.md`

### 核心定位

> 一个给临时抱佛脚的人用的备考工作台。离考试还有两周？够用了。

用户把课件、教材、往年题、笔记、PDF、手写照片、视频字幕扔进来，AI 拆知识点、讲重点、出题、批改、生成模拟考、临考速背卡片。自带 API Key，数据全在浏览器。

### 核心场景

1. **连接 AI**：BYOK + 邀请码；DeepSeek / Kimi / OpenAI / 自定义 OpenAI-compatible。
2. **创建考试项目**：科目、考试日期、每天可学时长、目标分数、已知薄弱点。
3. **资料库**：PDF / DOCX / RTF / TXT / Markdown / 旧 .doc / 手写笔记 / B 站视频字幕。
4. **知识模块计划**：AI 从资料拆出可考知识点，每个带名称、难度、重要程度、考察内容、来源证据。
5. **每日计划**：按剩余天数、可学时间、模块重要程度和难度分配；逾期自动滚到今天。
6. **模块学习**：看讲解、出模拟题、学习卡片。
7. **模拟考**：自定义时长和题型；考题模式（AI 批改）或 AI 答题模式；导出 PDF。
8. **临考速背**：核心概念 → 必背要点 → 记忆口诀 → 常见考法 → 易错提醒。
9. **学习卡片**：concept / mistake / exam / quick_memory 四种，流式生成，左右滑动筛选。
10. **错题本**：模考错题自动入库，手动添加，薄弱点管理。
11. **数据管理**：IndexedDB 本地存储，JSON 导入导出。

### 对正式系统的启发

- **知识模块**是跨场景核心对象：S2 生成，S3/S4/S5 消费。
- **来源证据**：每个知识点必须能回链资料原文。
- **卡片/练习/模拟考**都围绕知识模块，不是泛泛的"本章复习"。
- **速背卡片**是 cards/exercises 的最小可用形态。

---

## 二、前辈版本一：AI StudyBuddy（Node/TS monorepo，七子系统）

来源：`H:\ai-studybuddy/docs/01-总PRD`、`02-七子系统地图`、`08-共同底座架构`

### 核心定位

> 把课程/考试目标、学习节奏、资料笔记、练习、错题复盘和考前冲刺连成可持续闭环；家长接收脱敏异步摘要。

**架构**：1 个共同底座 + 7 个场景子系统。

### 七个子系统

| 编号 | 子系统 | 场景 | 学生动作 | 系统输出 |
|---|---|---|---|---|
| S1 | 学习节奏 StudyRhythm | 每日/每周学习安排 | 建课程、考试目标、任务、截止时间 | 时间线、工作量、逾期提醒 |
| S2 | 资料笔记 NoteBuilder | 课后整理资料 | 上传 PDF/文本/图片 | 笔记、重点、导图、知识模块 |
| S3 | 限时练习 PracticeRunner | 学完后练习 | 围绕知识模块做限时题 | 批改结果、解析、练习记录 |
| S4 | 错题改错 ErrorFixer | 复盘错题 | 查看错因、重做 | 错题本、薄弱点、复习排程、变题 |
| S5 | 期末冲刺 ExamCrammer | 考前冲刺 | 上传真题、限时模拟 | 真题解析、模拟卷、冲刺计划 |
| S6 | 家长观察 ParentReport | 家长接收报告 | 阅读邮件/飞书 | 日报、周报、月报、考前提醒 |
| S7 | 课堂采集 ClassCapture | 课后整理 | 课堂录音 | 转写文本、S2 资料来源 |

### 共同对象流

```text
Semester -> CourseInstance -> AssessmentAttempt / Material -> KnowledgeModule -> StudyTask -> StudyEvent
KnowledgeModule -> Question -> PracticeSession / PracticeAnswer -> Mistake -> WeakPoint -> 下一轮 StudyTask
AssessmentAttempt + StudyTask + StudyEvent -> ParentReport（脱敏聚合）
```

### AI 质量门（重要的安全边界设计）

- `required_fix`：客观可核验的关键错误，修正前不能完成。
- `suggestion`：改善建议，不阻塞完成。
- `uncertain`：OCR 模糊、开放题等，要求孩子核对，AI 不作最终裁决。
- `overridden`：孩子覆盖，保留原结论和证据。
- Provider 全部不可用时进入 `pending_quality_check`，不阻塞孩子继续学习。

### 对正式系统的启发

- **七子系统拆分**是防止"先堆功能后补边界"的核心治理手段。
- **KnowledgeModule** 必须回链资料和证据，是 S2→S3→S4→S5 的共同对象。
- **AI 质量门**和 `pending_quality_check` 是 provider 不可用时的安全降级模式。
- **报告脱敏**：S6 只读聚合，不碰原文/答案/聊天。
- **Job 状态机**：pending→running→completed/failed，超时恢复，单进程串行。

---

## 三、前辈版本二：pi-studybuddy（pi 底座 + Electron 桌面壳）

来源：`H:\pi-studybuddy/AGENTS.md`、`dist/agent/tools/`

### 核心定位

> pi-studybuddy = pi（AI 底座）+ pi-skills（组件供给）+ StudyBuddy 业务能力（内核）+ pi-desktop 式桌面壳。

业务认知从 ai-studybuddy 迁移，但以 pi 为底座重新组装，不复制实现。

### S1–S7 工具划分（从 `dist/agent/tools/` 可见）

| 工具目录 | 对应子系统 | 推断职责 |
|---|---|---|
| `s1/` | 学习节奏 | 课程表、考试目标、时间线 |
| `s2/` | 资料笔记 | 资料上传、知识模块、笔记 |
| `s3/` | 限时练习 | 练习生成、批改 |
| `s4/` | 错题改错 | 错题本、薄弱点 |
| `s5/` | 期末冲刺 | 模拟考、速背 |
| `s6/` | 家长观察 | 报告发送 |
| `s7/`（含 `ocr-tools`） | 课堂采集 | OCR、ASR |
| `backup/` | 运维 | 备份恢复 |
| `tts/` | 辅助 | 语音合成 |

### 治理要点

- **五阶段组件治理**：下载储存 → 单件测试 → 集成测试 → 系统组装 → 冒烟 + E2E。
- **权威链裁决**：用户 > AGENTS.md 安全约束 > 已定案决策 > 设计文档 > 任务清单 > 计划 > 代码 > 参考 > 聊天。
- **task-id 全局唯一**：T-<里程碑>-<序号>。
- **每任务用户端到端测试铁律**。

### 对正式系统的启发

- **工具→子系统映射**：每个 S 阶段对应一组 agent tools，可作为未来扩展性参考。
- **治理纪律**：权威链、五阶段组件治理、task-id 唯一性，StudyBuddy 已有类似（AGENTS.md + Composer/Integration 流程）。
- pi-studybuddy 仍处于"运行级使用禁用"阶段，不代表产品完成。

---

## 四、三个版本的核心场景对比

| 场景 | 祖宗 KaoBuddy | 前辈一 ai-studybuddy | 前辈二 pi-studybuddy | StudyBuddy 正式系统当前 |
|---|---|---|---|---|
| 资料导入 | ✅ 浏览器端解析 | ✅ 后端 Adapter | ✅ agent tools | ✅ Phase 0 已完成 |
| 知识模块 | ✅ AI 拆分 | ✅ KnowledgeModule 对象 | ✅ s2 工具 | ❌ Phase 4 待实现 |
| 学习计划 | ✅ 每日计划 | ✅ S1 StudyTask/StudyEvent | ✅ s1 工具 | ❌ Phase 9 待实现 |
| 笔记生成 | ✅ AI 讲解 | ✅ S2 笔记/重点/导图 | ✅ s2 工具 | ❌ Phase 4 Q&A 前置 |
| 限时练习 | ✅ 模拟题 | ✅ S3 PracticeRunner | ✅ s3 工具 | ❌ Phase 8 待实现 |
| 错题改错 | ✅ 错题本 | ✅ S4 ErrorFixer | ✅ s4 工具 | ❌ Phase 8 待实现 |
| 模拟考 | ✅ 模拟考 | ✅ S5 ExamCrammer | ✅ s5 工具 | ❌ Phase 8 待实现 |
| 速背卡片 | ✅ 临考速背 | ✅ S5 速背 | ✅ s5 工具 | ❌ Phase 8 待实现 |
| 家长报告 | ❌ | ✅ S6 ParentReport | ✅ s6 工具 | ❌ 暂不做 |
| 课堂采集 | ✅ 视频字幕 | ✅ S7 ClassCapture | ✅ s7/ocr/tts | ❌ 暂不做 |
| AI Provider | ✅ BYOK | ✅ AiProviderRouter | ✅ pi 底座 | ❌ Phase 5 待实现 |
| 本地存储 | ✅ IndexedDB | ✅ SQLite | ✅ SQLite | ✅ Phase 0 已完成 |
| 部署形态 | PWA | Express localhost | Electron | FastAPI localhost |

---

## 五、对 StudyBuddy 正式系统 AI Phase 4 的输入

基于三个历史版本，正式系统 AI Phase 4（可信 Q&A 最小闭环）应继承的核心设计：

### 必须继承

1. **KnowledgeModule 回链证据**：每个知识点必须能回到 material/revision/chunk/span（祖宗"来源证据" + 前辈"KnowledgeModule 必须回链资料"）。
2. **AI 质量门**：provider 不可用时安全降级，不阻塞应用启动（前辈一 `pending_quality_check`）。
3. **citation 不可信模型**：模型不能自造引用，citation 只能来自 retrieval/context 可验证 key（祖宗"不编造资料里没有的内容" + 前辈"AI 不能把推断写成事实"）。
4. **draft 原则**：AI 生成内容必须先为 draft，用户确认后才 ready（前辈一/二）。
5. **provider secret 安全**：key 不进日志/数据库/前端（三个版本共同）。

### 暂不继承（明确延后）

- S6 家长报告（需 SMTP/飞书，暂不做）
- S7 课堂采集（需 ASR/OCR，暂不做）
- 模拟考 PDF 导出
- 邀请码/多用户
- Electron 桌面壳

### Phase 4 最小闭环对应历史场景

| Phase 4 组件 | 历史场景来源 |
|---|---|
| `material_revisions` | 前辈一 KnowledgeModule 的来源追溯 |
| `chunks` / `chunk_spans` | 祖宗"资料拆知识点" + 前辈一 S2 |
| `chunk-fts5-retrieval` | 祖宗"按知识点出题"的检索基础 |
| `citation-context-assembler` | 祖宗"来源证据" + 前辈一"证据回链" |
| `fake-provider` | 祖宗 BYOK + 前辈一 AiProviderRouter 的最小契约 |
| `qa-operation` | 祖宗"模块学习看讲解" + 前辈一 AI 质量门 |

---

## 六、关联文档

- 正式系统路线图：[`PHASE_ROADMAP.md`](PHASE_ROADMAP.md)
- AI 架构设计：[`ai-learning-architecture.md`](ai-learning-architecture.md)
- 本地环境目录：[`LOCAL_ENVIRONMENT_MAP.md`](LOCAL_ENVIRONMENT_MAP.md)
- 设计决策：[`DECISIONS.md`](DECISIONS.md)

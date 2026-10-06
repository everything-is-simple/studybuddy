# 原始 PRD、设计与任务提取映射

## 1. 最重要的原始 PRD

### ai-studybuddy 总 PRD

[01-总PRD-产品需求-Product-Requirements.md](./ai-studybuddy/01-总PRD-产品需求-Product-Requirements.md)

核心产品定义：

- 一个共同底座加七个场景子系统：S1 学习节奏、S2 资料笔记、S3 限时练习、S4 错题改错、S5 期末冲刺、S6 家长观察、S7 课堂采集。
- 学生是唯一业务操作者和数据拥有者；家长只接收脱敏异步报告。
- 系统以 Windows 本机、`127.0.0.1`、本地资料和阶段性验收为边界。
- 学习闭环是：课程/考试目标 → 计划 → 资料 → 知识模块 → 练习 → 错题 → 复习 → 家长摘要。
- 非目标包括公网家长监控、云数据库、学校教务系统替代和完整 LMS。

对应的上游子系统 PRD 位于 [ai-studybuddy/subsystems](./ai-studybuddy/subsystems/)。

### pi-studybuddy 产品 PRD

[02-PRD-产品需求-Product-Requirements.md](./pi-studybuddy/02-PRD-产品需求-Product-Requirements.md)

它把上述业务内核放进 pi 桌面产品，增加了：

- pi 原生 AI 对话作为自由探索入口。
- Electron/React 桌面壳、`registerTool` 业务工具和 S1-S7 Adapter。
- 课程、考试、资料、笔记、练习、错题、冲刺和家长摘要的一体化工作台。
- 单机、离线优先、凭据隔离、备份恢复和阶段门禁。

## 2. 原始设计文档

### ai-studybuddy

- [08-共同底座架构-Architecture.md](./ai-studybuddy/08-共同底座架构-Architecture.md)
- [02-七子系统地图-Scenario-Systems.md](./ai-studybuddy/02-七子系统地图-Scenario-Systems.md)
- [15-前端信息架构与界面范围研究-Frontend-Information-Architecture.md](./ai-studybuddy/15-前端信息架构与界面范围研究-Frontend-Information-Architecture.md)
- [07-文档策略-Design-Docs-Strategy.md](./ai-studybuddy/07-文档策略-Design-Docs-Strategy.md)
- [09-测试验收计划-Test-Plan.md](./ai-studybuddy/09-测试验收计划-Test-Plan.md)

### pi-studybuddy

- [01-TRD-技术需求-Technical-Requirements.md](./pi-studybuddy/01-TRD-技术需求-Technical-Requirements.md)
- [03-架构设计-Architecture-Design.md](./pi-studybuddy/03-架构设计-Architecture-Design.md)
- [05-数据模型-ERD-Data-Model.md](./pi-studybuddy/05-数据模型-ERD-Data-Model.md)
- [06-API契约-API-Contracts.md](./pi-studybuddy/06-API契约-API-Contracts.md)
- [07-工作流-Workflow.md](./pi-studybuddy/07-工作流-Workflow.md)
- [09-使用者介面-UI-Design.md](./pi-studybuddy/09-使用者介面-UI-Design.md)
- [08-测试验收-Test-Plan.md](./pi-studybuddy/08-测试验收-Test-Plan.md)

## 3. 原始任务文档

- [ai-studybuddy 开发任务清单](./ai-studybuddy/04-开发任务清单-Todo-List.md)：按共同底座和 S1-S7 场景登记任务。
- [pi-studybuddy 任务清单](./pi-studybuddy/04-任务清单-Todo-List.md)：按 M0-M5 里程碑、壳层、扩展层、业务 Adapter、数据层和测试门禁登记任务。
- pi-studybuddy 的系统集成和追踪资料位于 [系统集成](./pi-studybuddy/系统集成/) 与 [traceability](./pi-studybuddy/traceability/)。

## 4. 映射到当前 StudyBuddy

| 原始设计主题 | 当前 StudyBuddy 对应位置 | 当前状态解释 |
|---|---|---|
| 本机单用户、本地资料 | `backend/app/`、`H:\studybuddy-data` | 当前正式边界已采用 |
| 资料导入、解析、来源追踪 | `backend/app/adapters/file_parsers/`、repositories、citations | 已有正式实现和局部证据 |
| 学习计划、今日安排、进度 | 当前 Buddy/Student/Parent 页面及 learning API | 以当前 STATUS 和浏览器证据为准 |
| 练习、错题、期末冲刺 | `backend/app/api/`、learning/task 域 | 只按当前正式代码和证据判断，不按上游“完成”标签判断 |
| 课堂采集、OCR、ASR | `backend/app/providers/`、capture API | 本地 OCR/ASR 已配置；真实质量仍按当前验证范围解释 |
| 家长报告 | reports、delivery 配置 | 本地报告可用；外发默认关闭 |
| pi/Electron/React 桌面壳 | 当前不是正式运行时 | 作为产品和架构参考，不复制到 FastAPI 正式系统 |
| `registerTool`、pi hooks、桌面 IPC | 当前没有对应正式边界 | 不能当作已实现能力 |

## 5. 使用规则

1. 先读本目录的原始 PRD，再以当前正式 `STATUS`、`ARCHITECTURE`、`TODO` 和测试证据确认是否已经迁移。
2. 从原始文档提取业务目标、场景、对象和验收意图；不直接复制上游代码、Prompt、品牌、Electron 壳或数据库实现。
3. 新需求必须落到当前 StudyBuddy 的正式 API/UI/SQLite 边界，并补充自己的测试和证据。
4. 原始 PRD 与当前正式文档发生冲突时，原始文档保留为历史输入，当前正式文档负责描述现在的系统。

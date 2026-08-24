# 本地环境目录地图与治理

> 更新：2026-08-30（Phase 9A-7 restore gate 后）
>
> 本文记录 StudyBuddy 全部本地目录的职责、远端、Git 状态和相互关系，作为系统治理的单一事实来源之一。目录本身不含密钥；`H:\pi-references` 等含密钥目录只标注用途，不记录任何凭据内容。

## 一、核心四级目录（正式交付流水线）

按 `AGENTS.md` 的三阶段流程，组件从实验工厂走向正式系统：

```text
Composer 独立测试 -> Integration 组合测试 -> StudyBuddy 主系统重新实现/装配
                                                          |
                                                   studybuddy-test 验收
```

| 目录 | 职责 | 远端 | Git 状态 |
|---|---|---|---|
| `H:\studybuddy` | **正式系统**：源码 `backend/app/`、测试 `backend/tests/`、核心设计 `docs/`、系统治理 `AGENTS.md` | `everything-is-simple/studybuddy` | clean（仅未跟踪会话产物） |
| `H:\studybuddy-composer` | **实验工厂**：系统组件、测试配件、功能保证的独立 smoke 验证 | `everything-is-simple/studybuddy-composer` | clean |
| `H:\studybuddy-integration` | **集成工厂**：把 Composer 验证通过的组件组合装配并测试 | `everything-is-simple/studybuddy-integration` | clean |
| `H:\studybuddy-test` | **测试目录**：所有系统的测试 fixture、运行记录和验收 artifact | `everything-is-simple/studybuddy-test` | clean |

### 四级目录硬边界

- 不得从 Composer / Integration / 参考项目直接复制源码作为正式实现。
- 组件必须先在 Composer 通过独立 smoke，再在 Integration 通过组合测试，最后由主系统重新实现。
- 测试 artifact 写入 `studybuddy-test`，不污染主系统源码目录。
- 不提交数据库、上传原件、生成产物、密钥或测试运行输出。

## 二、参考与历史版本目录

这些目录只用于提取产品范围、接口契约和设计教训，**不得直接复制代码**到正式系统。

| 目录 | 性质 | 远端 | 说明 |
|---|---|---|---|
| `H:\kaobuddy-remote-audit` | **祖宗版本**（Kaobuddy 远程审计版） | `everything-is-simple/kaobuddy-remote-audit` + upstream `jin-zi-xuan/kaobuddy-pwa` | 最早的 PWA 版本，含 AI client、prompts、卡片学习、邀请等 |
| `H:\pi-studybuddy` | **前两版本之一**（pi 版 StudyBuddy） | `everything-is-simple/pi-studybuddy` | 基于 pi 的 agent 扩展应用，含 S1–S7 tools、OCR/TTS、Electron 结构 |
| `H:\AIStudyBuddy` | **前两版本之二**（Node/TS 版 AIStudyBuddy） | 无 Git | 完整业务实现：exam-crammer、practice-runner、note-builder、study-rhythm、ai-router 等 |
| `H:\ai-studybuddy` | **前两版本**（v2 monorepo，pnpm workspace） | `everything-is-simple/ai-studybuddy` | 含 backend/frontend/shared、七子系统 PRD、完整 docs 与 e2e |
| `H:\ai-studybuddy-composer` | **前两版本的组件试炼场** | 无 Git | 候选组件 smoke（ai-provider、asr、ocr、pdf、queue、storage、db 等） |
| `H:\pi-references` | **前两版本选择的组件 / Provider 参考资料** | 无 Git | API Provider 研究、配置示例、书签；**含密钥，不得提交** |

### 参考目录使用规则

- 只读不写：从中提取契约和设计，不在参考目录里做正式开发。
- 密钥安全：`H:\pi-references` 含 API key/token/account 文件，绝不进入任何远端仓库、日志、数据库或前端。
- 契约回填：从参考目录抽象出的接口，需在 `studybuddy-composer` 重新独立验证，再进入正式系统。

## 三、工具环境路径

项目实际使用的本地工具环境：

| 路径 | 说明 |
|---|---|
| `C:\miniconda\py310` | Python 3.10.19，StudyBuddy 测试/运行环境；依赖以 `backend/requirements.txt` 固定并已恢复验证 |
| `C:\Program Files\nodejs` | Node.js 24.14.0；Playwright 由仓库 `node_modules` 提供 |
| `C:\Git\bin` | Git 可执行文件 |
| `C:\Program Files\PowerShell\7` | PowerShell 7 |
| `C:\cygwin64\bin` | Cygwin 可执行文件（当前 agent shell 基础） |

## 四、当前正式系统状态

- 基础设施 v1 已基本完工：I1 migration/schema、I2 backup/restore、I3 可观察性完成；I4 真实环境/容量基线时间盒验收完成。
- 文件材料管理 v1 核心路径局部 `real-pass`；Phase 4–6 的可信 Q&A、Provider 和产品化证据按精确范围记录。
- Phase 7 已按 Mistral 精确配置范围收口；Phase 8 已按 deterministic fake-provider、Chromium 与 backup/restore 精确范围收口，证据见 `PHASE8_ACCEPTANCE_EVIDENCE.md`。
- Phase 9A-0 至 9A-7 已在明确的单进程 SQLite/backend/API/local Chromium scoped gates 内形成实现与证据；9A-7 backup/restore `restore-gates-pass` 已通过；9A-8 closeout 和完整计划产品能力仍未完成。
- 比较结论：正式系统在工程治理、可靠性、资料生命周期、引用可追溯性和验收纪律上已经进化；在卡片、练习、学习计划、OCR/ASR 和 S1–S7 产品宽度上尚未全面超过历史/前代版本。
- Phase 9 不作为单一业务大阶段，后续学习能力按 9A–9D 独立立项和验收；Phase 10 继续承载后台任务、生产化和扩展。

## 五、下一步准备

Phase 7 与 Phase 8 fake-provider closeout 已完成，9A-6 source lifecycle scoped gate 已通过，9A-7 backup/restore `restore-gates-pass` 已通过；下一步是 9A-8 closeout。9B–9D 仍不得提前推进，不能跳过各自独立契约和 migration gate。Composer/Integration 组件仍需保持可复核 smoke/integration evidence：

1. `chunker` - deterministic 文本分块（中文/Unicode offset、page/slide span 映射）
2. `chunk-fts5-retrieval` - chunk 词法检索与 top-k 排序
3. `citation-context-assembler` - token budget、可验证 citation key
4. `fake-provider` - deterministic fake LLM provider
5. `qa-operation` - AI operation / Q&A 生命周期

组件通过后放入 `studybuddy-integration` 组合测试，最终在 `studybuddy` 主系统重新实现，测试 artifact 写入 `studybuddy-test`。

## 六、关联文档

- 项目入口：[`README.md`](../README.md)
- Agent 指令：[`AGENTS.md`](../AGENTS.md)
- 基础设施状态：[`INFRASTRUCTURE_CLOSEOUT.md`](INFRASTRUCTURE_CLOSEOUT.md)
- 阶段路线图：[`PHASE_ROADMAP.md`](PHASE_ROADMAP.md)
- 当前状态：[`STATUS.md`](STATUS.md)
- 执行清单：[`TODO.md`](TODO.md)
- 设计决策：[`DECISIONS.md`](DECISIONS.md)

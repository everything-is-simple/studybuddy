# StudyBuddy 组件采用审计 — 2026-08-27

> 依据：`H:\studybuddy`（正式系统）、`H:\studybuddy-composer\components`（组件实验工厂）、`H:\ai-studybuddy-composer`（第一代组件）、`H:\pi-references`（参考资料）。
> 结论性质：**静态对照审计**。只核对“组件是否已进入正式系统”，不代表行为级 `real-pass` 复测。

---

## 一、studybuddy-composer 组件采用状态（8 个）

| 组件 | 正式系统对应实现 | 状态 | 匹配 |
|---|---|---|---|
| `backend-file-parsers` | `backend/app/adapters/file_parsers/`（`adapter.py`、`models.py`） | ✅ 已进入 | 匹配。`parse_file(Path, media_type, ParseOptions)`、`ParseResult`/`TextSpan`、`PARSER_VERSION=1.0.0`，契约一致；TXT/MD/PDF/DOCX/PPTX，RTF/DOC/PPT 拒绝。测试：`test_file_parsers.py` |
| `deterministic-chunker` | `backend/app/chunking.py` | ⚠️ 已实现但**算法不同** | **不匹配**。Composer 契约是 `codepoint-window-v1`（500 codepoints / 50 overlap / 2000 hard-max、NFKC 归一化、绝不跨 span、east_asian_width 估 token）；正式系统是 `boundary_window`（800 字符、按空白/换行边界切分、正则估 token）。两者 chunk 结果不一致 |
| `kaobuddy-file-foundation` | （无 JS 代码）→ 由 `backend-file-parsers` 取代 | ✅ 有意替代 | 匹配（按设计）。Composer 卡自身结论即“PDF/DOCX/PPTX 应在 FastAPI 侧重写为服务端适配器”；正式系统正是这样做的，未复制浏览器端 JS |
| `openai-compatible-provider` | `backend/app/providers.py`：`OpenAICompatibleLLMProvider` + `OpenAICompatibleEmbeddingProvider` + `ProviderRegistry`/`EmbeddingProviderRegistry` | ✅ 已进入 | 匹配。`/chat/completions`、`/embeddings`、Bearer、超时、`ProviderError` 稳定错误映射、SSE/脱敏限制均有。测试：`test_ai_provider.py`、`test_provider_acceptance_runner.py`、`test_real_provider_smoke.py` |
| `sqlite-local` | `backend/app/migrations/runner.py`（schema v13、连续迁移、`schema_migrations`、`PRAGMA user_version`）+ `repository.py`（WAL、锁、事务、backup/restore） | ✅ 已进入 | 匹配（正式化）。Composer 只验证可行性；正式 schema 在 studybuddy 实现 |
| `WhisperCli` | **无**。`POST /api/study/capture-sessions/{id}/transcribe` 硬编码 `provider_registry("fake","fake-capture-v1").capture_provider()` → `DeterministicFakeCaptureProvider` | ❌ 未进入 | **缺口（最重要）**。S7 数据库链路（capture_sessions / transcript_drafts / transcript_segments，schema v13）已就绪，但真实 ASR 未接；G:\WhisperCli 未被调用 |
| `CapsWriterCli_Full` | 无 | ❌ 未进入 | 缺口（候选：本地 ASR 备选，含热词/服务端） |
| `component-template` | — | — | 模板，无内容可核对 |

---

## 二、ai-studybuddy-composer（第一代）可借鉴组件

重点标准：成熟、稳定、高效、免费。按“能否进入 studybuddy 系统构建”排序：

| 组件 | 技术 | 许可/成本 | 相关度 | 结论 |
|---|---|---|---|---|
| `local-asr-whispercpp` | whisper.cpp v1.9.1 CLI（MSVC x64 已构建） | MIT，离线 | 高（S7 真实 ASR 的成熟参考） | ✅ 可进入。已验证中文转写、全零静音 `NO_SPEECH` 前置判定、进程超时清理；与 WhisperCli 同源思路 |
| `ocr/RapidOCR` | ONNX Runtime，无需 GPU | Apache-2.0，免费 | 高（S7 图片/板书 OCR） | ✅ 可进入。轻量、成熟、有 smoke；`windows-native/04-rapidocr-child` 提供子进程 harness 模式 |
| `ocr/PaddleOCR` | PaddlePaddle | Apache-2.0，免费 | 高 | ✅ 可进入（较重，需权衡） |
| `asr/SenseVoice` / `asr/FunASR` | 阿里语音模型 | 免费 | 中高 | ◐ 候选。效果强但 Python 依赖重、单机内存占用大 |
| `windows-native/06-qq-smtp`、`07-feishu-webhook` | SMTP/飞书 Webhook | 免费 | 中 | ◐ 参考。studybuddy `delivery.py` 已存在但 live 外发默认 off、需三重授权，属未立项范围 |
| `windows-native/08-windows-scheduler` | 计划任务 | 免费 | 低 | ✖ 超出单进程边界（scheduler 不在支持范围） |
| `queue/bullmq-test`、`storage/minio-test`、`db/pgvector-test` | Redis/MinIO/Postgres | — | 低 | ✖ 与“单进程 / SQLite / 本地盘”边界冲突，不建议引入 |
| `markdown`、`mindmap`、`pdf`、`converter` | 前端渲染/转换 | — | 低 | ◐ 前端候选，与后端组件审计无关 |

---

## 三、pi-references 可借鉴性

| 目录 | 结论 |
|---|---|
| `kaobuddy/` | 祖宗系统；其能力已通过 `kaobuddy-file-foundation` 审计并被服务端重写取代 |
| `pi-skills/transcribe` | macOS 专用（parakeet-cpp），Windows 不可用，仅思路参考 |
| `pi/`、`pi-desktop/`、`inno-agent/` | Agent 基础设施源码，不是 studybuddy 后端组件 |

---

## 四、结论

1. **已进入且匹配（3 个）**：`backend-file-parsers`、`openai-compatible-provider`、`sqlite-local`（另 `kaobuddy-file-foundation` 被有意替代）。
2. **不完全匹配（1 个）**：`deterministic-chunker` —— 正式系统用的是 `boundary_window`，Composer 契约是 `codepoint-window-v1`。需要决策：对齐 Composer 契约，还是保留现有策略并正式记录差异。
3. **未进入的缺口（2 个）**：`WhisperCli`（S7 真实 ASR，最重要）、`CapsWriterCli_Full`（本地 ASR 备选）。
4. **可引入的高价值免费组件（来自第一代）**：`local-asr-whispercpp`（ASR 成熟参考）、`RapidOCR` / `PaddleOCR`（OCR）、`SenseVoice`/`FunASR`（ASR 增强备选）。
5. **不建议引入**：Redis/MinIO/Postgres 类组件（与单进程边界冲突）。

> 本审计只做静态对照；任何组件要“进入”正式系统仍须按治理规则在 `H:\studybuddy` 重新实现、过 migration、补正式测试并留证据，不能直接复制 Composer/Integration 代码。

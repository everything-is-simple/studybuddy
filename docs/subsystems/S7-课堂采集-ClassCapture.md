# S7 课堂采集（ClassCapture）

> 状态以 [capabilities.json](../capabilities.json) 中 `id=s7-classroom-capture` 与 `id=x-asr-whisper` 为准。

原始意图参考 [S7 ClassCapture PRD](../archive/legacy-product-references/ai-studybuddy/subsystems/07-S7-课堂录音子系统PRD-ClassCapture.md)。

## 1. 目标

课堂讲解里常有教材之外的重点和考试提示，学生边听边记很难完整。S7 把学生已获允许的课堂录音或板书照片在本机转成可编辑文字，学生修改并确认后成为 S2 材料的新修订，再走资料 → 知识模块 → 练习的主闭环。S7 服务学生本人，不是课堂监听或云端采集。

## 2. 用户流程

1. 在 `capture.html` 查看转写能力状态（未配置 / 已配置 / 演示模式）。
2. 新建采集会话：选择类型（音频或图片）、文件名和媒体类型。
3. 上传文件，绑定一个本地原件。
4. 点击转写：图片走 OCR，音频走 ASR；得到转写草稿和逐段置信度，不确定片段被标出。
5. 逐段核对，修改转写文本。
6. 确认：文本写入该材料的新修订并建立索引，可在 `material-detail.html` 继续抽取知识模块；或拒绝，或归档会话。
7. `classroom.html` 汇总采集会话和学习报告。

## 3. 数据对象

| 表 | 关键字段 | 状态 |
|---|---|---|
| `capture_sessions` | asset_kind `audio / image`, material_id, original_name, media_type, source_status | `draft → uploaded → transcribing → review_required → confirmed / rejected`；`failed`、`archived` |
| `transcript_drafts` | capture_session_id, operation_id, text, language, quality_status `clear / uncertain`, edited_by_user | `draft → confirmed / rejected`，`superseded` |
| `transcript_segments` | draft_id, ordinal, text, confidence, quality `clear / uncertain` | 随草稿 |
| 确认产物 | 新的 `extractions`（成功）+ `text_spans` + `material_revisions` 当前修订 | 进入 S2 |

支持的媒体：`image/png`、`image/jpeg`、`image/webp`、`audio/wav`、`audio/mpeg`、`audio/mp4`；上传受大小上限约束，原件不暴露存储路径。

## 4. 页面与 API

页面：`capture.html`、`classroom.html`；确认后的材料在 `material-detail.html`。

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/study/capture-sessions` | 新建会话（draft） |
| GET | `/api/study/capture-sessions` | 会话列表 |
| GET | `/api/study/capture-sessions/{capture_id}` | 会话详情 |
| POST | `/api/study/capture-sessions/{capture_id}/upload` | 上传原件 |
| POST | `/api/study/capture-sessions/{capture_id}/transcribe` | OCR / ASR 转写 |
| GET | `/api/study/capture-sessions/{capture_id}/transcript` | 读取转写草稿 |
| POST | `/api/study/capture-sessions/{capture_id}/transcript/edit` | 学生修改草稿 |
| POST | `/api/study/capture-sessions/{capture_id}/confirm` | 确认为材料新修订 |
| POST | `/api/study/capture-sessions/{capture_id}/reject` | 拒绝草稿 |
| POST | `/api/study/capture-sessions/{capture_id}/archive` | 归档会话 |
| GET | `/api/ai/capabilities` | 转写能力状态 |

## 5. 规则与 AI 边界

- OCR / ASR 属于非 LLM 的格式转换；只在显式配置后运行：图片需 `ocr_enabled` 且 Provider 为 `paddleocr`；音频需配置 `asr_provider_id`，否则仅演示模式使用 fake 转写；均未配置时返回 `transcription_provider_not_configured`。
- 转写结果一律是草稿；Provider 输出不能修改学生编辑过的文本。
- 只有 `review_required` 的会话和 `draft` 的草稿可编辑、确认或拒绝；来源不可用时不能确认。
- 确认是唯一写入学习材料的路径；确认后不会自动生成笔记或知识模块，后续由学生在 S2 操作。
- 是否录音、是否已获允许、是否保存，都由学生决定；原件只在本机。
- 家长报告只读"不确定转写片段数"等计数，不看原件或转写文本。
- Whisper 适配器使用显式配置的本地 CLI 与模型；官方 whisper.cpp 的输出名是 `input.wav.txt` / `input.wav.srt`，旧 Windows port 则是 `input.txt` / `input.srt`，两者均可读取。UTF-8 BOM 不属于转写正文，只有 BOM 的输出必须拒绝，不生成空草稿。
- `whisper-cpp` Provider 名称不证明所配置的二进制支持某个模型；安装及配置必须选择已验证的运行时/模型组合。运行时路径和学生原文不进入公开错误。

## 6. 验收标准

- 未配置转写能力时，页面显示未配置，转写返回明确错误，不产生草稿。
- 转写后能看到逐段文本，不确定片段有标记。
- 修改并确认后，对应材料出现新的解析正文，可在 `material-detail.html` 抽取知识模块；Today 随后可能出现"知识草稿待确认"。
- 拒绝后会话显示已拒绝，材料正文不变。
- 不支持的文件类型或超大文件被拒绝并提示原因。
- 真实 ASR 验收需同时核对已知输入的有意义文本、草稿确认边界与材料修订；退出码为零、模型加载成功或出现输出文件均不能单独判定通过。

## 7. 状态来源

本页不维护当前缺口或验证结论；以 [`capabilities.json`](../capabilities.json) 的 `id=s7-classroom-capture` 与 `id=x-asr-whisper` 为准。第一版产品目标和边界见文首链接的 S7 PRD。

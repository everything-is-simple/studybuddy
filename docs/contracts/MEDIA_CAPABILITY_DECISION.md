# 媒体能力选型与门禁决策

> 更新：2026-08-30。此文记录已选候选、Composer 本机预检与 Formal 边界；不构成真实 OCR/ASR/TTS 的 StudyBuddy 完成声明。

## 已选方案

| 领域 | 选定路径 | 当前证据 | Formal 状态 |
|---|---|---|---|
| ASR | `H:/WhisperCli` 的 whisper.cpp `ggml-large-v3-turbo` | 本地中文 MP3 → TXT/SRT，exit code 0；CLI 支持语言、TXT/SRT 与 duration 参数 | B1 C0 已选定；C1–C6 未完成 |
| OCR 主路径 | PaddleOCR 3.7.0 / PaddlePaddle 3.3.1 | Windows Python 3.10 运行时与依赖可导入；未初始化/下载模型、未处理图片 | B2 C0 已选定；C1–C6 未完成 |
| OCR 回退 | RapidOCR ONNX Runtime 1.4.4 | Windows Python 3.10 运行时可导入；未初始化/下载模型、未处理图片 | B2 C0 回退候选；C1–C6 未完成 |
| OCR 兼容后备 | Tesseract | 未安装；不作为中文/文档主引擎 | 未开始 |
| TTS | edge-tts 7.2.8 | CLI 与 voice-list 成功；未合成用户文本 | 免费在线候选，非离线；不属于当前 Phase 9D 批准业务范围 |
| PPTX 原生文字 | `formal-pptx` parser | 正式 parser、PPTX 浏览器导入和 slide span 回归已通过 | 已实现，仅提取 OOXML 原生文字 |
| PPTX 辅助转换 | MarkItDown 0.1.7 + python-pptx | 合成 PPTX → Markdown smoke 通过 | Pi/开发辅助，不替代 Formal parser |
| 图片/扫描 PPT 页面 | render → PaddleOCR | 尚无模型/图片 smoke | 随 B2 处理 |

## 不变量

1. `H:/WhisperCli` 是唯一 canonical ASR runtime；Composer 目录中的 WhisperCli 副本仅供证据/审计，不能形成第二个运行路径。
2. 真实 OCR/ASR 输出一律 draft-first。只有用户显式确认后才可进入 material/revision/chunk/retrieval/citation；不得静默覆盖用户编辑或已确认 revision。
3. PaddleOCR 是中文、版面、表格和图片型 PPT 页的主候选；RapidOCR 只是资源受限时的轻量 ONNX 回退。两者安装/导入不等于准确率、离线模型或 C1 smoke 已通过。
4. edge-tts 不购买 API Key，但依赖 Microsoft Edge 在线语音服务；只允许用户显式触发，不能默认调用、不能声称离线，也不把生成音频作为 citation/source 或学习事实。
5. PPTX 原生文字提取不是 OCR。无文字层的扫描/图表页面必须经 B2 OCR 路径，且保留 slide/source identity。
6. 当前正式 S7 默认仍是 deterministic fake/loopback OCR/ASR；真实外部组件继续 `not_verified`，不得仅因本机预检或单次 smoke 改变该状态。

## 进入下一门禁前的工作

- **B1 C1**：使用合成、非敏感 WAV，验证 WhisperCli 成功、空/损坏/不支持输入、超时/终止、TXT/SRT 输出限制、重复调用、临时目录和子进程清理；证据不得包含音频、全文、绝对路径、模型路径或 stderr。
- **B2 C1**：预置本地 PaddleOCR/RapidOCR 模型后，在合成中文/英文、空白、损坏、超大图片上验证成功/失败、无隐式网络、超时、输出限制、清理和脱敏证据；禁止把模型首次下载混入 smoke。
- **TTS 重新立项**：在有明确学习产品路径时，先冻结 `TextToSpeechProvider`、本地音频保留/删除、用户确认、网络 opt-in、失败/限流和隐私契约；这不是 B4 delivery，也不启用自动朗读。
- **PPT 图片页**：先冻结安全 PPTX→渲染图的转换器、大小/页数/清理合同，再把图像送入已通过 C1/C2 的 OCR adapter。

Composer 的可执行 preflight、版本与模型 hash 记录位于 `H:/studybuddy-composer`；详细选型见其 `DECISIONS/STUDYBUDDY_MEDIA_CAPABILITIES.md`。
# P1-6-3 真实 OCR 主路径与 RapidOCR 兜底契约

> 状态：`contract-frozen / P1-6-3-2 / 2026-08-31`
>
> 本契约建立在 RapidOCR Composer C1 与 Integration C2 精确范围证据之上。它批准 Formal 独立实现与真实 acceptance，不把任何 fake OCR 输出写成真实能力证据。

## 1. 精确 provider scope

主路径：

- `provider_id=paddleocr`
- `model_id=PP-OCRv5_server_det+PP-OCRv5_server_rec`
- PaddleOCR 3.7.0 / PaddlePaddle 3.3.1
- PP-OCRv5 server detection/recognition models
- Windows、Python 3.10、CPU、本地预置模型，默认不下载

兜底路径：

- `provider_id=rapidocr`
- `model_id=ch_PP-OCRv4_det_infer+ch_PP-OCRv4_rec_infer`
- `rapidocr_onnxruntime=1.4.4`
- ONNX Runtime 1.20.1
- bundled local ONNX model set：detection、recognition、classification
- Windows、Python 3.10、CPU、本地模型，默认不联网

精确版本、模型文件名、运行环境和 C2 结果见：

- `H:/studybuddy-composer/components/ocr-rapidocr/COMPONENT-CARD.md`
- `H:/studybuddy-composer/results/ocr-rapidocr/c1-smoke.json`
- `H:/studybuddy-integration/results/ocr-rapidocr-c2/integration.json`

这些 evidence 只证明精确环境和输入 scope，不代表所有 RapidOCR/PaddleOCR 版本、模型、语言、GPU 或操作系统可用。

## 2. 输入边界

允许的图片 MIME：`image/png`、`image/jpeg`、`image/webp`。服务端必须校验实际 bytes 可解码、hash 与 stored original 一致、像素和字节上限；空、损坏、MIME 不支持、hash mismatch 和超限输入在 provider 选择前拒绝。

这些输入安全错误不得 fallback，因为 fallback 不能绕过输入完整性或大小边界：

- `capture_asset_type_not_supported`
- `capture_asset_too_large`
- `transcription_failed`（source hash mismatch）
- `capture_source_unavailable`
- `capture_not_found`

## 3. Fallback policy

PaddleOCR 是默认主路径。只允许一次、同一请求内、无并行的 RapidOCR fallback。

允许触发 fallback 的主路径错误：

| 主路径错误/状态 | fallback | 安全原因记录 |
|---|---|---|
| `transcription_provider_not_configured` / 初始化失败 | 允许 | `primary_unavailable` |
| `provider_unavailable` / 模型缺失 | 允许 | `primary_unavailable` |
| `provider_timeout` | 允许 | `primary_timeout` |
| `transcript_empty_or_invalid` | 允许 | `primary_empty_result` |
| `transcription_failed`（provider 内部执行失败） | 允许 | `primary_failed` |

不得 fallback 的错误：

- 输入格式、空输入、hash、source、权限或大小边界错误；
- `payload_too_large`，不得用 fallback 绕过输出安全上限；
- RapidOCR 自身失败、超时或空结果，不再尝试第三个 provider；
- 用户已编辑/确认的 draft，不因 retry 或 fallback 静默覆盖。

两者都失败时：

- 保留 primary 与最终失败的安全 operation/error 事实；
- 返回最终稳定错误 `transcription_failed`，除非最终错误是明确的 `payload_too_large` 或 `provider_timeout`；
- 不伪造文本、不生成 draft、不宣称 fallback 成功；
- 不暴露 raw provider error、路径、stderr、图片或模型信息之外的敏感数据。

## 4. Identity 与 metadata

最终成功结果的 operation 必须记录实际成功的 `provider_id` 与 `model_id`：

- PaddleOCR 成功：operation 为 `paddleocr`；
- PaddleOCR 失败、RapidOCR 成功：operation 为 `rapidocr`；
- 两者失败：operation 保留已创建的主 provider identity，最终 error code 为安全稳定错误。

当前 v14 schema/API 不新增 fallback 字段。`fallback_reason`、primary error 和 provider attempt 仅作为运行时内部决策和脱敏 evidence，不进入 raw response 或新表。若正式产品必须向用户暴露持久化 fallback history，必须另行冻结 migration/API contract。

允许的公开 metadata 只有 provider/model identity、状态、耗时、固定 error code、input fingerprint 和 draft/source 状态。禁止原图、完整 OCR 正文、raw response、stderr、模型绝对路径、secret 或本机路径。

## 5. Draft-first 与生命周期

统一流程：

```text
PaddleOCR primary
  → RapidOCR fallback if policy allows
  → real OCR result
  → transcript draft / review_required
  → explicit user edit
  → explicit confirm
  → same-material extraction/revision
  → chunk/index/retrieval/citation
```

没有 provider 结果时不得创建 draft。fallback 成功也必须从 draft 开始，不能直接创建 ready revision。retry 创建新的 operation/draft，旧 operation/draft 历史保留。用户编辑过的 draft 和 confirmed revision 不得被 provider retry、fallback 或 source refresh 静默覆盖。

soft delete、purge、stale 和 restore 只改变 source status；历史事实保留，普通 read、startup、verify、backup/restore 不重新调用任一 OCR provider，不自动修复 source 状态。

## 6. 运行与安全门禁

- 真实 OCR 仅在显式 capability/runtime gate 下执行；默认不运行；
- 模型必须本地预置，禁止隐式下载；
- 使用独立临时 data root 和非敏感图片；
- B1/B2 的原始输入、完整 OCR 文本、真实路径和模型文件不进入仓库/evidence；只记录 hash、计数、状态、耗时和安全 identity；
- 不接入 Phase 10 task runner、scheduler、自动 OCR 或自动确认；
- B4 `delivery=off` 保持不变；OCR 不触发 delivery；
- timeout/初始化失败的 fallback 必须有 bounded timeout、临时资源清理和单次尝试上限；
- fallback 不得隐式访问网络或未知第三方 provider。

## 7. 当前 schema/API 决策

P1-6-3 当前不新增 schema、migration 或 API endpoint。现有 `ai_operations.provider_id/model_id/status/error_code` 足以记录最终成功 provider 和稳定失败；现有 transcript draft lifecycle 足以保存 fallback 产生的 draft。fallback reason 不做持久化字段扩展，防止未完成 migration/backup/API 评审就改变正式契约。

若实现证明该结论不成立，必须停止 Formal 实现，新增独立 migration/API 评估，不得在本任务中隐式升级 schema。

## 8. Acceptance gate

必须分别记录：

1. RapidOCR C2 Integration：真实 RapidOCR 处理 PNG/JPEG/WebP、空白/损坏边界、confidence、draft-first、source lifecycle、backup/restore non-repair 和无 Formal touch；
2. Formal real PaddleOCR：真实模型、明确输入集、confidence/clear/uncertain、draft-first 和 provider identity；
3. Formal real RapidOCR fallback：受控主路径失败、真实 RapidOCR 成功、fallback 原因、最终 identity；
4. 两者都失败：稳定错误、无 draft、无第三 provider；
5. source lifecycle、backup/restore、startup/read/verify 不重新运行 OCR；
6. browser evidence 仅在 Formal backend real acceptance 后执行，真实 browser smoke 必须显式 opt-in。

Fake OCR 只允许用于 policy/error-injection 单元测试，不能计入真实 PaddleOCR 或真实 RapidOCR acceptance。

**冻结声明：** P1-6-3-2 批准真实 PaddleOCR 主路径与真实 RapidOCR 兜底的后续 Formal 实现，但不表示 Formal fallback 已实现或真实 acceptance 已通过。

# P1-6-3-0 真实 OCR 组件与 Formal 边界审计证据

> 状态：`planned/audit-draft / 2026-08-31`
>
> 本文只记录真实组件、既有证据和 Formal 表达能力审计。它不批准 RapidOCR 进入 Formal，不把 fake OCR、图片解码或旧 Integration 自报状态写成真实 OCR acceptance。

## 1. 审计范围与工作区保护

审计读取了 P1-6、B2 OCR contract/evidence、Formal provider/config/API/repository/backup 边界，以及 `H:/studybuddy-composer` 和 `H:/studybuddy-integration` 的 RapidOCR 记录。

Formal 工作区在审计开始前已有未提交修改：

- `backend/app/providers/_ocr.py`
- `backend/app/providers/_registry.py`
- `docs/contracts/P1_6_3_OCR_FALLBACK_CONTRACT.md`（未跟踪）

这些内容被视为用户已有工作；本切片未修改、回退、暂存或将其视为已通过门禁。工作区原有 3 个中文未跟踪项目也未修改、暂存或提交。

## 2. 当前真实运行组件

本机审计环境：

- OS：Windows 10 build 26200（当前主机报告值）
- Python：3.10.19
- CPU execution；未验证 GPU
- PaddleOCR：3.7.0
- PaddlePaddle：3.3.1
- RapidOCR package：`rapidocr-onnxruntime` 1.4.4
- ONNX Runtime：1.20.1
- Pillow：12.3.0

PaddleOCR 本地模型 inventory：

- `PP-OCRv5_server_det`：`inference.json`、`inference.pdiparams`、`inference.yml`
- `PP-OCRv5_server_rec`：`inference.json`、`inference.pdiparams`、`inference.yml`

RapidOCR package-bundled 本地模型 inventory：

- `ch_PP-OCRv4_det_infer.onnx`
- `ch_PP-OCRv4_rec_infer.onnx`
- `ch_ppocr_mobile_v2.0_cls_infer.onnx`

模型实际存在且 Python 包可导入。模型绝对路径不写入普通产品 metadata/API；本 evidence 仅记录公开 model identity。RapidOCR 三个 ONNX 文件的 SHA-256 已在本机核对，但不在本文复制本机路径。

## 3. 当前真实 PaddleOCR 覆盖

既有 Formal C5/C6 证据只证明：

- PaddleOCR 3.7.0 / PaddlePaddle 3.3.1；
- PP-OCRv5 server det/rec；
- Windows / Python 3.10 / CPU / 本地预置模型 / 显式 opt-in；
- 一个非敏感 synthetic PNG 的真实模型推理；
- 返回一个非空 segment，confidence 在 `[0,1]`；
- draft-first、显式确认、现有 source/material/revision 边界；
- 不接入 task runner，不自动执行，不改变 `delivery=off`。

P1-6-2 的 PNG/JPEG/WebP 证据使用真实图片解码但 fake PaddleOCR 输出，只能证明 adapter 输入/错误/清理 contract，不能扩大真实模型识别范围。

因此当前真实 PaddleOCR 未覆盖：真实模型 JPEG/WebP、中文/英文/混合质量矩阵、低质量/空白/超大/损坏的完整真实 provider 行为、可靠 timeout/cancel、并发/容量、其它 OS/GPU、表格/版面质量或通用 real-pass。

## 4. RapidOCR C1/C2 审计

Composer C1 记录为 `smoke_passed`，真实 RapidOCR 对 synthetic 中英文图片产生文本和 confidence，并覆盖 blank/corrupt/unsupported/oversize/重复调用等 harness checks。

Integration 目录存在 `ocr-rapidocr/run_integration.py` 和一份 `status=integration_passed` JSON。本次在本机重新执行该脚本，命令成功返回 `integration_passed`，真实 RapidOCR 再次处理了 synthetic PNG/JPEG/WebP。

但按本任务新增的严格 C2 contract，该脚本仍有门禁缺口：

1. fallback decision 是固定字典，不是实际执行“主 PaddleOCR 失败 → RapidOCR 被调用”；
2. `TIMEOUT_SECONDS` 未形成真正 bounded provider execution；
3. RapidOCR 模型路径不是显式 gate 参数，运行依赖 package-bundled default；
4. evidence 未记录模型 hash/provenance 完整闭环；
5. storage/draft/operation/source lifecycle 使用脚本内临时简化表，不是既有 Integration 治理中的正式组合 contract；
6. backup/restore 只检查 draft 行数，未通过调用计数证明 restore/startup/verify 不会重新调用 OCR；
7. 未覆盖主失败不被静默掩盖、两个 provider attempt identity、final error 和 bounded output 的完整矩阵；
8. Composer component card/catalog 仍标记 RapidOCR 为 `not_started`/`smoke_passed`，与 Integration JSON 存在治理漂移；
9. `H:/studybuddy-integration/ocr-rapidocr/` 和结果当前未提交，不能作为已进入共享基线的 durable C2 gate。

结论：旧 JSON 的真实 RapidOCR 格式 smoke 有价值，但 **P1-6-3 要求的 RapidOCR C2 尚未通过**。

## 5. Formal fallback 与 schema/API 审计

现有 B2 Formal contract 明确只批准 PaddleOCR，并明确 RapidOCR 必须经独立 C3/adapter contract 后才能使用；所以需要新增 fallback contract，但只能在严格 C2 通过后冻结。

当前 v14 已有 `ai_operations.provider_id`、`model_id`、`status`、`error_code`，可保存一个 operation 的最终或初始 provider identity；capture transcript lifecycle 已能表达 draft-first、user edit、confirm、revision/chunk/citation 和 source degradation。

但是当前 `transcribe_capture_session()` 在调用 provider 前就读取 wrapper 的 `provider_id/model_id` 并创建 operation。若 fallback wrapper identity 为模糊的 `ocr-fallback/paddleocr+rapidocr`：

- 成功 operation 无法准确表示最终实际成功 provider；
- `fallback_reason` 和 `primary_error_code` 无持久字段；
- idempotency 当前把 provider/model 纳入匹配，fallback identity 更新方式必须先冻结；
- browser/API 无法可靠区分主路径成功与 RapidOCR fallback 成功。

因此当前不能直接断言“不需要 schema/API”。后续 C2 通过后必须先做独立 contract 决策：

- 若只要求安全运行期 fallback audit，并允许 operation 在完成时原子更新为最终 provider identity，可能无需 migration/API；
- 若要求持久化并公开 `fallback_used`、`fallback_reason`、`primary_error_code`、provider attempt history，则现有 v14 不足，必须停止并单独冻结 migration/API contract。

本切片未修改 schema、migration、API 或 Formal runtime。

## 6. 安全与未验证边界

- 未保存原图、OCR 正文、raw response、stderr、secret 或模型绝对路径；
- 未默认下载模型，未批准任何隐式网络访问；
- 未运行真实用户图片；
- 未接入 task runner/scheduler；
- 未自动确认或覆盖用户 draft；
- B4 `delivery=off` 保持不变；
- 未执行 browser real OCR；
- 未创建 real acceptance evidence。

## 7. 第一阶段回答

- **RapidOCR C2 是否通过？** 否。真实 PNG/JPEG/WebP smoke 重跑成功，但严格 fallback/integration/governance 门禁不完整。
- **真实 PaddleOCR 当前实际覆盖到什么范围？** 精确 Windows/Python 3.10/CPU、本地 PP-OCRv5 server det/rec、一个 synthetic PNG 的真实非空识别与 draft-first scoped closeout；其它真实输入矩阵仍未验证。
- **Formal fallback 是否需要新增 schema/API？** 尚不能冻结。最终 provider identity 可望复用 v14，但持久化 fallback reason/primary error/attempt history 需要 migration/API；必须在 C2 后做独立决策。
- **下一步应执行哪个独立子切片？** 仅执行 P1-6-3-1 RapidOCR C2 修复：显式模型路径/hash、真实主失败→RapidOCR 调用、bounded timeout/output、正式组合 lifecycle/backup non-call proof、治理状态同步。通过前不得进入 Formal contract。

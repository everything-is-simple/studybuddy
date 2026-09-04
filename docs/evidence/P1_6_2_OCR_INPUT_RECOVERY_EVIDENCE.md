# P1-6-2 B2 OCR 输入集与失败恢复验证证据

> 状态：`implemented / focused-pass / 2026-08-31`
>
> 本证据覆盖 B2 Formal PaddleOCR adapter 的输入格式解码、边界拒绝和受控 timeout 清理。OCR 识别结果由 fake PaddleOCR 返回，仅验证 adapter/storage contract，不代表通用 OCR 准确率或 global `real-pass`。

## 1. 精确范围

- Formal adapter：`backend/app/providers/_ocr.py:PaddleImageOcrProvider`
- Provider identity：`paddleocr` / `PP-OCRv5_server_det+PP-OCRv5_server_rec`
- Accepted MIME scope：`image/png`、`image/jpeg`、`image/webp`
- Test environment：local single-process、SQLite-compatible in-memory request、Python 3.10 test environment；不执行模型下载或网络请求
- OCR engine in focused tests：fake `paddleocr.PaddleOCR`，真实图片 bytes 由 Pillow 生成并经 adapter 解码校验

## 2. 本次验证

| 场景 | 结果 | 结论 |
|---|---|---|
| PNG 输入 | passed | 通过真实 PNG image decode 后进入 OCR adapter |
| JPEG 输入 | passed | 通过真实 JPEG image decode 后进入 OCR adapter |
| WebP 输入 | passed | 通过真实 WebP image decode 后进入 OCR adapter |
| 空输入/损坏图片 | passed | 在 OCR 处理前返回稳定拒绝，不产生 draft |
| MIME 不支持/hash 不匹配 | existing pass | 保持 `capture_asset_type_not_supported` / `transcription_failed` 边界 |
| 像素上限 | passed | 超过 `MAX_OCR_PIXELS` 返回 `capture_asset_too_large`，不调用 OCR |
| 输入字节上限 | passed | 超过 50 MiB 返回 `capture_asset_too_large` |
| OCR timeout | passed | `TimeoutError` 映射为 `provider_timeout`，partial temporary root 被清理 |
| 输出上限/confidence | existing pass | 保持 `payload_too_large`、confidence clamp 和 clear/uncertain 语义 |
| draft/source lifecycle | existing pass | 复用 Phase 9D capture 的 draft-first、失败不产生 draft、source degradation 与显式 retry 语义 |

三种格式的测试确认的是容器解码和输入边界，不是 PaddleOCR 模型质量；没有使用真实用户图片或真实 OCR 网络服务。

## 3. 测试结果

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_phase_b2_ocr_c4.py backend/tests/test_b2_ocr_c6_closeout.py backend/tests/test_phase9d_capture.py -q
18 passed
```

新增 P1-6-2 focused assertions 位于 `backend/tests/test_phase_b2_ocr_c4.py`，覆盖三种已批准图片 MIME、空/损坏输入、像素/字节限制和 timeout 后临时目录清理。Phase 9D capture 回归继续覆盖失败 operation、显式重试、draft 不落库和 source lifecycle。

## 4. 失败恢复与隐私边界

- 失败只保留安全 operation/error fact；本切片不新增 schema 或 operation 状态。
- timeout 后不保留 partial OCR temporary file；不生成 transcript draft。
- raw image bytes、模型路径、provider response、secret 和绝对路径不进入 evidence 或公共响应。
- retry 仍必须由现有 capture workflow 显式触发；不新增自动重试、scheduler 或 task runner 接入。

## 5. 未验证与限制

- 未执行真实 PaddleOCR 模型推理；本切片 fake OCR 只验证 adapter 输入/输出和清理契约；
- 未验证任意用户图片质量、多语言、表格/版面、图片尺寸组合、GPU、其它 OS、并发、容量或长时稳定性；
- 未证明 graceful cancellation、子进程树终止、跨进程恢复或硬终止恢复；
- 未新增 API、schema、migration、后台任务或前端行为；
- B1 ASR、B3 reports、B4 delivery 不在本切片范围，B4 继续 `delivery=off`；
- 不将本次结果扩大为通用 OCR real-pass 或 global production `real-pass`。

## 6. 变更与检查

本切片只增加 B2 focused tests、本 evidence 和状态索引；没有修改 `backend/app/`。可复现检查：

```text
C:\miniconda\py310\python.exe backend/scripts/check-source-size.py
# source-size check passed

git diff --check
# passed
```

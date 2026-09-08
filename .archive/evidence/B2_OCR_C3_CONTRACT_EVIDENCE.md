# B2 OCR C3 Formal Contract Evidence

> 状态：`contract-frozen`。本文件是脱敏的 C3 证据索引，不是 OCR 实现证据。

## 前置证据

| Gate | Evidence | 结论 |
|---|---|---|
| Composer C1 | `H:\studybuddy-composer\results\ocr-paddleocr\c1-smoke.json` | PaddleOCR 精确本地模型 scope `12/12` smoke passed |
| Model inventory | `H:\studybuddy-composer\results\ocr-paddleocr\model-inventory.json` | 模型归档/文件 hash inventory；模型未进入 Git |
| Integration C2 | `H:\studybuddy-integration\results\ocr-paddleocr-c2\integration.json` | 隔离 data root 组合验证 passed |
| Formal C3 | `H:\studybuddy\docs\contracts\B2_IMAGE_OCR_PROVIDER_CONTRACT.md` | 正式 provider、draft、source、privacy、验收边界已冻结 |

## 精确已验证范围

- PaddleOCR 3.7.0 / PaddlePaddle 3.3.1。
- `PP-OCRv5_server_det` + `PP-OCRv5_server_rec`。
- Windows/Python 3.10/CPU/本地预置模型。
- synthetic printed Chinese/English image；C1/C2 均无网络访问。
- C2 证明了原件 hash/storage、draft-first、confidence/uncertain、用户确认、同 material revision、source deletion、rollback 和 backup/restore non-repair 的组合语义。

## C3 冻结的安全声明

- Formal 真实 OCR 默认关闭，必须 capability/feature gate + 用户显式操作。
- 模型不得隐式下载；网络默认关闭。
- 未确认 OCR draft 不进入 ready revision/chunk/FTS/retrieval/citation。
- 不静默覆盖用户编辑、已确认 revision 或既有材料正文。
- API、日志、页面、诊断和 evidence 不得包含原图、完整 OCR 正文、stored/model path、raw stderr、raw provider response、secret 或 traceback。
- backup/restore/startup/read/verify 不执行 OCR、不自动确认、不修复 source status。

## 未验证与禁止外推

C1/C2 不证明通用 OCR real-pass、复杂扫描件质量、表格结构识别、全部图片格式、多语言质量、GPU/其它操作系统、其它 Python/包版本、并发/容量、真实断电、磁盘满、网络盘、系统级辅助技术或正式 UI 用户路径。RapidOCR 仍是独立回退候选，未因本 C3 自动纳入 Formal。

## C4/C5/C6 门槛

- C4：Formal 独立实现 `ImageOcrProvider`、配置 gate、draft lifecycle 和必要 domain/API 边界；不得复制 Composer/Integration 代码。
- C5：focused backend、显式 opt-in synthetic local-model smoke、Chromium capture workflow、source lifecycle、migration/backup/restore、startup/readiness/diagnostics 和完整 backend regression 全部通过。
- C6：提供脱敏 acceptance evidence，精确记录 provider/model/environment/input scope、测试结果和限制，并同步 STATUS/TODO/ROADMAP。

## C3 结论

`B2 OCR C3 = contract-frozen`。本次没有修改生产代码、schema、migration、API、UI、数据库或正式运行数据；`ImageOcrProvider` 仍为 `not_implemented`，C4 是唯一下一步。

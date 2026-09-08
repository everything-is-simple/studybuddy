# P1-6-0 扩大 B1-B4 验证范围审计证据

> 状态：`contract-frozen / audit-complete / 2026-08-31`
>
> 本证据记录 P1-6-0 的文档和治理审计结果，不代表扩大验证已经执行，也不代表 B1-B4 达到通用或 global `real-pass`。

## 1. 审计对象

审计对照了 B1 ASR、B2 OCR、B3 reports、B4 delivery 的既有 contract/evidence、Formal 源码边界、Composer/Integration 隔离、运行时默认值、source lifecycle、backup/restore 和当前项目状态。

| 能力 | contract | acceptance/closeout evidence | manifest/governance | 当前结论 |
|---|---|---|---|---|
| B1 ASR | `FORMAL_ASR_ACCEPTANCE_EVIDENCE.md` 中的 Formal Contract；B0 catalog 记录 canonical runtime | `docs/evidence/FORMAL_ASR_ACCEPTANCE_EVIDENCE.md` | B0 component governance / ASR catalog | `C0-C6 scoped closeout`；输入、取消、并发、跨环境仍有限 |
| B2 OCR | `docs/contracts/B2_IMAGE_OCR_PROVIDER_CONTRACT.md` | `docs/evidence/B2_OCR_C6_SCOPED_CLOSEOUT_EVIDENCE.md` | B0 catalog；B2 C1/C2/C5/C6 evidence | `closeout-scoped-pass`；当前只接受精确 PaddleOCR scope |
| B3 reports | `docs/contracts/B3_REPORT_COMPONENT_CONTRACT.md` | `docs/evidence/B3_REPORT_C6_SCOPED_CLOSEOUT_EVIDENCE.md` | B3 C0-C3 governance/evidence | `scoped-closeout-pass`；JSON/Markdown deterministic read-only scope |
| B4 delivery | `docs/contracts/B4_DELIVERY_COMPONENT_CONTRACT.md` | `docs/evidence/B4_DELIVERY_C6_SCOPED_CLOSEOUT_EVIDENCE.md` | B4 C3-C6 evidence；delivery policy | `scoped closeout passed`；产品 live API 继续关闭 |

## 2. Gap ledger

| 验证维度 | B1 ASR | B2 OCR | B3 reports | B4 delivery |
|---|---|---|---|---|
| 输入集 | 当前为公开 `jfk.wav`；TXT/SRT 输出边界已覆盖 | 当前为单个 synthetic PNG；任意图片/多语言/版面未覆盖 | 四类报告与 JSON/Markdown 已覆盖；PDF/HTML 未立项 | 固定 synthetic message；生产内容、批量、附件未覆盖 |
| 取消/中断 | reliable cancellation、子进程树清理未验证 | reliable cancellation 未验证 | 同步只读 projection，无独立长任务 cancel 契约 | 自动取消/队列取消未立项；adapter timeout 已有边界 |
| 并发/容量 | 未验证 | 未验证 | 未验证长时/大规模 projection | 未验证并发发送、限流和容量；自动化明确排除 |
| 失败恢复 | timeout/empty/oversize 有映射；restart/硬终止仍有限 | invalid/timeout/rollback/source lifecycle 有边界；跨环境未验证 | restart/restore non-repair 有证据；更大窗口/异常输入待矩阵 | failure/retry/idempotency 与 restore no-send 有证据；产品 live recovery 不立项 |
| 跨环境 | 当前 Windows canonical runtime only | Windows/Python 3.10/CPU only | local single-process/SQLite only | 固定 SMTP/Feishu 精确配置，非通用渠道 |
| 真实用户路径 | opt-in static capture path 已有；真实输入类别窄 | browser 主要为 mocked capability/failure；real provider browser 未宣称 | reports page 是 read-only local path | operator fixed-synthetic smoke；产品 live API closed |

## 3. P1-6 后续建议拆分

1. **P1-6-1 B1 输入集与可取消性**：从 canonical `whisper-cpp` 开始，使用非敏感 fixture，先验证输入分类、timeout/cancel、临时目录与子进程清理；不扩大模型/语言/OS 承诺。
2. **P1-6-2 B2 输入集与失败恢复**：补 PNG/JPEG/WebP、空/损坏/超大图片、timeout/retry 和 draft/source lifecycle；继续使用显式本地 PaddleOCR gate。
3. **P1-6-3 B3 跨环境与恢复矩阵**：补 IANA timezone/window、空/退化 source、export boundary、restart/restore replay；保持 deterministic read-only。
4. **P1-6-4 B4 adapter isolation 与 no-send recovery**：只测 default-off、dry-run、失败/retry/idempotency、restart/restore no-send；不打开产品 live。
5. **P1-6-5 B1-B4 受控并发/资源测量**：专项完成后再做 bounded measurements，结果只记录 evidence，不产生容量承诺。
6. **P1-6-6 真实用户/跨环境复核**：需要使用者明确授权、固定目标和独立环境，按组件分别记录，不合并为 global 结论。

## 4. P1-6-0 验收结果

- Contract：已创建 `docs/contracts/P1_6_VERIFICATION_SCOPE_CONTRACT.md`，状态为 `contract-frozen`。
- Scope：已将 B1-B4 当前事实与 `not_verified` 边界分开记录。
- Safety：本切片不执行真实 runtime/network/delivery，不读取或保存 secret，不新增 API/schema/migration。
- Runtime：保持 local single-process、single-instance、SQLite、local-disk；B4 `delivery=off` 与产品 API live closed 不变。
- Next slice：推荐 P1-6-1，先处理 B1 输入集与可取消性。

## 5. 未验证与不立项

本轮没有验证任意语言/音频/图片质量、跨 OS/GPU、并发/容量、真实生产 Provider generation、通用 SMTP/webhook、批量或附件发送、自动调度、后台 worker、真实断电、ACL、disk-full、network filesystem、恶意扩展/进程或 global production `real-pass`。这些边界必须继续显示为 `not_verified` 或明确排除。

## 6. 可复现检查

本切片的机器检查为：

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_p1_6_0_governance.py -q
# 11 passed
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
# 580 passed, 3 skipped
C:\miniconda\py310\python.exe backend/scripts/check-source-size.py
# source-size check passed
git diff --check
# passed
```

本切片没有新增浏览器行为或生产代码，因此不新增 Chromium 测试；既有 browser 基线未被改写。3 个 skip 是显式 opt-in 的真实 ASR/Provider smoke。

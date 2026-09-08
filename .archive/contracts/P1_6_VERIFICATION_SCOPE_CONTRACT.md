# P1-6 扩大 B1-B4 验证范围契约

> 状态：`contract-frozen / P1-6-0 / 2026-08-31`
>
> 本契约只冻结扩大验证的范围、门禁和后续切片顺序，不代表 B1-B4 已达到通用 real-pass 或 global production `real-pass`。

## 1. 目标与边界

P1-6 的目标是在既有 B1 ASR、B2 OCR、B3 reports、B4 delivery 的 C0-C6 scoped closeout 之上，逐项验证尚未覆盖的输入类别、取消/中断、并发、失败恢复、跨环境和真实用户路径。每个后续切片必须独立立项、测试、记录 evidence，并只扩大实际通过的精确范围。

本切片 P1-6-0 只做审计与契约冻结：

- 不修改 `backend/app/` 生产代码；
- 不新增或修改 schema、migration、API endpoint、错误码或业务数据语义；
- 不调用真实 ASR/OCR/Provider/delivery runtime；
- 不保存、复制或提交真实 secret、音频、图片、报告正文、收件人或 webhook；
- 不改变 B4 的 `delivery=off` 默认值，也不批准产品 API live delivery；
- 不启动 scheduler、worker、自动发送、自动转写或自动 OCR。

支持边界仍为 local single-process、single-instance、SQLite、local-disk v1。多进程、多用户、云同步、网络盘、真实断电恢复和生产规模容量继续不在本契约内。

## 2. 当前基线与证据来源

| 能力 | 当前 scoped closeout 基线 | 当前证据来源 | 本契约不外推的范围 |
|---|---|---|---|
| B1 ASR | `C0-C6 scoped closeout`，Const-me/Whisper 1.12.0 local CLI，`whisper-cpp` / `ggml-large-v3-turbo`，Windows，公开 `jfk.wav`，draft-first capture transcription | `docs/evidence/FORMAL_ASR_ACCEPTANCE_EVIDENCE.md`；B0 catalog/component governance | 任意音频、语言、格式、模型/运行时安装、官方 asset hash、并发、可靠取消、其它 OS/GPU、容量、通用 real-pass |
| B2 OCR | `closeout-scoped-pass`，PaddleOCR 3.7.0 + PaddlePaddle 3.3.1，PP-OCRv5 server models，Windows/Python 3.10/CPU，单个 synthetic PNG，draft-first | `docs/contracts/B2_IMAGE_OCR_PROVIDER_CONTRACT.md`；`docs/evidence/B2_OCR_C6_SCOPED_CLOSEOUT_EVIDENCE.md` | 通用准确率、任意用户图片、多语言、表格/版面质量、全部格式组合、并发、可靠取消、其它 OS/GPU、容量 |
| B3 reports | `scoped-closeout-pass`，local deterministic project-scoped daily/weekly/monthly/exam_alert projection，JSON/Markdown，1 MiB bound，read-only | `docs/contracts/B3_REPORT_COMPONENT_CONTRACT.md`；`docs/evidence/B3_REPORT_C6_SCOPED_CLOSEOUT_EVIDENCE.md` | PDF、HTML/email、Feishu card、AI narrative、通用报告格式、网络、scheduler、生产规模和高风险决策适用性 |
| B4 delivery | `scoped closeout passed`，一条 163→QQ SMTP 和一个 Feishu custom-bot webhook 的 fixed synthetic smoke；Formal product API live closed | `docs/contracts/B4_DELIVERY_COMPONENT_CONTRACT.md`；`docs/evidence/B4_DELIVERY_C6_SCOPED_CLOSEOUT_EVIDENCE.md` | 任意 SMTP/webhook、生产收件人、批量/附件/HTML/cards、自动 retry/scheduler/queue、通用 live delivery、多用户授权、global real-pass |

B1 当前没有独立命名的 Formal contract 文件；其 Formal contract、精确配置和限制以 `FORMAL_ASR_ACCEPTANCE_EVIDENCE.md` 及 B0 治理记录为来源。后续若需扩大 B1 契约，必须新增明确版本的 Formal contract，不得用本表替代。

## 3. 验证维度定义

| 维度 | 通过含义 | 默认验证方式 | 默认状态 |
|---|---|---|---|
| 输入集 | 明确列出格式、大小、语言/布局、空/损坏/边界样本及结果 | 非敏感 fixture；必要时显式 opt-in 真实样本 | 立项后逐组件验证 |
| 取消/中断 | 任务在规定窗口内停止，临时文件/子进程/状态无泄漏，失败可安全重试 | loopback、受控 fake 或本地 runtime；硬终止不等于 graceful cancel | `not_verified` |
| 并发 | 明确并发上限、资源隔离、重复/冲突语义和数据一致性 | 隔离 temporary data root 与 bounded worker/thread probe | `not_verified` |
| 失败恢复 | timeout、坏输入、provider/tool failure、重启、retry、source degradation 的结果可解释且不 repair | fake/loopback、restart、backup/restore | 部分已有；扩大前逐项确认 |
| 跨环境 | 工具、模型、OS/Python/CPU/GPU、路径和网络假设可重复 | 固定环境 matrix；不把单主机结果外推 | `not_verified` |
| 真实用户路径 | 从 `/app` 或正式 CLI/API 进入，包含成功、失败、retry、刷新/重启与隐私检查 | 非敏感授权材料；真实网络必须显式 gate | `not_verified` |

“验证通过”必须绑定组件、版本、环境、输入类别、命令、时间和结果；未覆盖的维度保持 `not_verified`。

## 4. 立项结论与切片顺序

P1-6-0 只批准以下后续切片作为候选执行顺序，不在本次执行：

| 切片 | 范围 | 结果类型 |
|---|---|---|
| P1-6-1 | B1 ASR 输入集与可取消性审计/受控验证：TXT/SRT、可读性、超时、取消、临时文件/子进程清理；不扩大语言或部署承诺 | loopback + 当前 canonical runtime 的显式 opt-in evidence |
| P1-6-2 | B2 OCR 输入集与失败恢复：PNG/JPEG/WebP、空/损坏/超大图片、timeout/retry、draft/source lifecycle | synthetic/local provider evidence |
| P1-6-3 | B3 reports 跨环境与恢复：timezone/window matrix、空/退化 source、export boundary、restart/restore replay | deterministic backend/operator evidence |
| P1-6-4 | B4 delivery 继续保持 default-off：仅验证 adapter isolation、失败/retry/idempotency、重启/restore no-send；不开放产品 live | loopback/dry-run/operator evidence |
| P1-6-5 | B1-B4 受控并发与资源边界汇总：只有组件专项完成后才可执行 | bounded measurement；不承诺容量 |
| P1-6-6 | 真实用户路径与跨环境复核：由使用者提供明确授权和环境矩阵后单独 gate | explicit opt-in real smoke；逐条记录限制 |

推荐下一步为 P1-6-1。理由是 B1 的当前 evidence 输入最窄、取消/清理仍是直接风险，且它可以在不打开 delivery、不改变 schema/API 的情况下产出清晰增量证据。P1-6-1 通过前不得把 B1 扩大为通用 ASR。

## 5. 真实运行与安全门禁

任何真实网络、真实 ASR/OCR runtime 或真实外发测试必须：

1. 显式设置唯一的 provider/model/runtime/gateway/target；不得继承或猜测上一次配置；
2. 使用独立临时 `data_root`，输入必须为公开 fixture 或明确授权的非敏感数据；
3. 命令与 artifact 默认脱敏，禁止保存 secret、原件、正文、地址、webhook、绝对路径或 raw response；
4. 明确 timeout、输出大小、临时文件清理、失败和 retry 行为；
5. B4 仍要求 `delivery=off`，除非另有独立、明确、一次性的 operator authorization；即使 smoke 成功，也不打开产品 live API；
6. 将 provider/model/gateway/target、环境、输入类别、时间和通过范围写入 evidence，并列出未验证项。

## 6. 证据、测试与文档门禁

每个 P1-6 后续切片必须提交：实现或验证产物、focused tests、必要 browser/API/operator evidence、安全检查和文档同步。C5/closeout 至少要求相关 backend、Chromium（有 UI 时）、source lifecycle、backup/restore、runtime 和 source-size/diff 检查，并运行完整 backend regression。

本 P1-6-0 的通过标准为：

- 本契约与 `docs/evidence/P1_6_0_AUDIT_EVIDENCE.md` 已创建；
- `backend/tests/test_p1_6_0_governance.py` 通过；
- schema 保持 v14，未新增 migration/API/runtime capability；
- `STATUS.md`、`TODO.md` 明确 P1-6-0 已完成而 P1-6-1 尚未完成；
- 当前 B1-B4 scoped closeout 与 `not_verified` 边界没有被改写为通用 real-pass。

## 7. 当前明确保留的 not_verified

官方 ASR asset hash、任意语言/音频/图片质量、复杂版面/表格、取消的可靠性和子进程树、并发/容量、跨 OS/GPU、真实生产 Provider generation、通用 SMTP/webhook、批量/附件/HTML/card delivery、自动调度、外部日志采集、OS clipboard/history、恶意扩展/进程、真实断电/ACL/disk-full/network filesystem 和全局 production `real-pass` 均继续为 `not_verified` 或明确不在本次立项范围。

**冻结声明：** P1-6-0 是审计与契约冻结，不打开任何新生产能力，不改变现有运行时默认值。

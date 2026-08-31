# B2 ImageOcrProvider 正式契约

> 状态：`contract-frozen`（B2 C3）  
> 范围：PaddleOCR 精确本地模型配置；Formal C4/C5/C6 尚未开始。  
> 本文冻结正式边界，不是实现、schema migration、API 或 UI 证据。

## 1. 审计基线与门禁结论

B2 已完成前置组件证据：

- Composer C1：PaddleOCR `3.7.0` / PaddlePaddle `3.3.1`，`PP-OCRv5_server_det` + `PP-OCRv5_server_rec`，Windows/Python 3.10/CPU，`12/12` 通过。
- Integration C2：隔离 data root 中验证了图片原件 hash/storage、OCR draft、confidence/uncertain、显式确认、同 material revision、source deletion、rollback 与 backup/restore non-repair。
- RapidOCR 是独立的 `smoke_passed` 回退候选；本契约不把它自动纳入 Formal adapter。

证据仅代表精确组件、模型、环境和 synthetic fixture 范围，不代表通用 OCR 准确率、全部图片类型、其它环境、并发容量或全局 `real-pass`。

Formal 顺序冻结为：

```text
C3 contract-frozen → C4 independent implementation → C5 formal gates → C6 scoped closeout
```

C4 不得复制 Composer/Integration 实现；必须针对本契约独立实现并复用正式系统已有 source/material/revision/citation 语义。

## 2. 精确支持范围与明确不做

### 2.1 本次冻结的 provider scope

正式实现首个精确 scope 仅为：

- PaddleOCR `3.7.0`；
- PaddlePaddle `3.3.1`；
- PP-OCRv5 server detection model：`PP-OCRv5_server_det`；
- PP-OCRv5 server recognition model：`PP-OCRv5_server_rec`；
- Windows、Python 3.10、CPU、本地已预置模型目录；
- 默认离线运行，不允许首次运行下载模型。

模型来源、归档 hash 与文件 inventory 以 Composer evidence 为审计输入；Formal 不提交模型、归档或本机路径。

PaddleOCR C1/C2 通过不等于支持所有 PaddleOCR pipeline、语言、版面模型、表格结构模型或 GPU 环境。RapidOCR/Tesseract 只有未来独立 C3 或明确 adapter contract 后才可使用。

### 2.2 输入范围

首个 Formal scope 只接受服务端识别为 allowlist 的常见图片：`image/png`、`image/jpeg`、`image/webp`。服务端以实际 bytes/MIME/扩展一致性判定，不信任客户端声明。PDF、视频、压缩包、可执行文件和任意 `application/octet-stream` 不属于本 scope；需要扩展时必须另立契约或更新本契约。

输入边界复用正式 `AppConfig.max_upload_bytes`，默认 50 MiB，并增加明确的像素/解码/输出上限。超限、无法解码或类型不支持必须返回稳定安全错误，不把原图或 provider stderr 返回给客户端。

客户端不得提供或覆盖：`project_id`、`stored_path`、source status、confidence、quality、provider/model metadata、OCR text、operation status 或 citation status。

## 3. 正式输出契约

Provider 只产生待核对的 OCR draft，不直接产生 ready material content。逻辑输出至少包括：

- server-generated draft identity、capture/material/operation identity；
- `language`（可为空或服务端结果，不视为准确率承诺）；
- 有序 segments；
- 每个 segment 的 `ordinal`、`text`、`confidence`、`quality`；
- 安全 operation metadata：provider/model identifier、input fingerprint、状态、耗时、错误码、时间。

`confidence` 必须是服务端归一化的 `[0,1]` 数值，不能由客户端提交。`quality` 只能为 `clear` 或 `uncertain`。本契约固定 `uncertain` 阈值为 `0.85`；低于阈值、空文本、明显非法/乱码结果或 provider 明确不可靠时使用 `uncertain`。任何 uncertain segment 都要求用户核对；分数不表示通用识别准确率。

空白或非法 draft 不得确认，返回 `transcript_empty_or_invalid`。结构化输出非法、超限、超时、provider unavailable 等进入安全失败状态；不得保存半截 raw response。

允许持久化的内容仅限：已脱敏的 draft/segment 领域字段、source identity、operation metadata、状态时间和固定错误码。禁止持久化 raw provider request/response、原始图片 bytes 的副本、完整 stderr、密钥、模型绝对路径和未受限诊断内容。

## 4. 生命周期与状态机

### 4.1 Draft-first 状态

```text
capture draft
  → uploaded
  → transcribing
  → review_required
  → confirmed | rejected | failed
  → archived
```

允许的动作：

1. 创建 project-scoped capture session；一个 session 只绑定一个 capture material。
2. 上传一次图片原件；原件复用既有 hash-derived original storage 和 material lifecycle。
3. 显式触发 OCR operation；真实 OCR 必须由独立 capability/feature gate 和明确用户动作启用，不能因模型目录或 provider 配置存在而自动执行。
4. 成功后创建 draft/segments，进入 `review_required`。
5. 用户可编辑 draft；编辑设置 `edited_by_user=1`，仍保持 review_required。
6. 用户显式 confirm/reject/archive。confirm 前不进入 ready source 管线。
7. 失败时保留最小安全 operation fact；显式 retry 创建新 operation 和新 draft，不覆盖旧历史。

用户已编辑的 draft 不得被 retry、source refresh 或 provider 重跑静默覆盖。已确认 revision 不得被后续 OCR 静默替换；替换必须是未来明确的 revision workflow 或新 session。

### 4.2 Source status

workflow status 与 source status 分离。source status 由服务端根据 material/revision/source identity 派生：`valid`、`stale`、`source_deleted`、`source_unavailable`。客户端不可写。

软删除、restore、purge、重新索引都不得删除历史 draft/operation/revision 或伪造来源：

- material deleted：历史结果保留，source status 降为 `source_deleted`；
- original purge/missing：降为 `source_unavailable`；
- source identity 不再匹配 current revision：降为 `stale`；
- restore 只有在既有 source identity 可重新验证时才可恢复 valid；普通 read/restore 不执行 OCR、重建或自动确认。

## 5. Material、revision、chunk 与 citation

OCR 原图是普通 capture material，不创建第二套 transcript/material 正文库。confirm 必须在一个 domain transaction 内：

1. 重新验证 session、material、project scope、source identity 和 draft；
2. 重新验证 text、segment、confidence、quality 与空文本规则；
3. 在同一 `material_id` 下创建新的 OCR extraction/revision，区分 `parser_id=ocr` 和固定 parser version；
4. 复用既有 deterministic chunking/index 管线；
5. 只有所有步骤成功才将 session 置为 confirmed；任一步骤失败整体 rollback，session 保持 review_required。

confirm 前 draft text 不得写入 ready `material_revisions`、chunks、FTS、retrieval 或 citation。confirm 后 citation 仍必须由服务端通过既有 revision/chunk/span identity 和 citation validator 重新验证，不能信任 provider 或客户端自造 `valid`。

## 6. Operation、幂等、失败、超时与重试

Operation 复用正式 `ai_operations` 生命周期：`queued`、`running`、`succeeded`、`failed`、`cancelled`、`stale`。operation 保存 capture/session/material/source fingerprint、公开 provider/model id、状态、耗时、retry relation 和稳定 error code，不保存 raw input/output。

- 相同输入 fingerprint + 相同合法 `Idempotency-Key` 可安全 replay 已成功结果，不复制 operation/draft；
- 同 key 的不同请求 fingerprint 返回 `idempotency_mismatch`；
- 已 running 的同 key 返回稳定 conflict，不并发重复 OCR；
- failed/timeout 可由显式 retry 产生新 operation/draft，旧 operation 保留；
- 超时必须终止/隔离 provider 调用并删除临时文件；若当前 runtime 无可靠取消能力，必须标记明确 `not_verified`，不得声称已取消；
- provider 不可用、模型缺失、格式不支持、非法输出、输出超限均安全失败；不暴露内部 traceback、路径或 provider 原文。

正式第一版不接入 task runner 自动调度。若未来接入长任务，必须另行冻结 operation/task 适配、lease、cancel、restart recovery 和 browser contract；startup、backup、restore、普通 read 不得触发 OCR。

## 7. 安全、隐私与配置

真实 OCR 默认关闭。正式能力必须由服务端 capability/feature gate 显式控制，并要求用户显式发起 transcribe/confirm；前端只读取 capability 状态，不硬编码模型路径或本机工具。

- 网络默认关闭；模型必须预置；OCR 运行不能隐式下载；
- API/UI/log/diagnostics/artifact 不得泄露原图、完整 OCR 正文、stored path、模型绝对路径、raw stderr、raw provider response、secret、SQL 或 traceback；
- 普通列表、报告和 delivery audit 只能返回安全状态、计数和受限定位，不返回 draft 全文或原件路径；
- backup 只包含允许持久化的 SQLite 事实，不包含 secret、raw response、临时上传字节或未受控 provider cache；
- 原件展示名只允许 basename、长度 1–255，用于受限本地 UI；不得进入日志、报告或外发；
- 所有新增事实使用服务端 project scope，客户端 project id 被拒绝或忽略；
- 所有时间使用 timezone-aware UTC；ID 由服务端生成；
- 低置信内容必须显式显示为需要核对，不能显示为系统已裁决。

## 8. Schema 与正式模块边界

C3 不新增或修改 schema。C4 先审计正式已有 capture/transcript/operation/material/revision 表能否表达本契约；若需要 schema，必须先提交独立连续 migration 设计，并覆盖 new DB、upgrade、rollback、history、`PRAGMA user_version`、constraint、backup/restore，不能在 runtime ad-hoc `CREATE TABLE`。

后续实现顺序冻结为：

```text
provider contract/adapter → domain transaction → API/error mapping → static UI → C5 gates
```

Formal 不导入 Composer/Integration 代码；只复用已验证语义，独立实现 `ImageOcrProvider` adapter、配置 gate、draft lifecycle、source validation 和必要 API/UI。OCR 不自动接入 Phase 10 task runner。

## 9. C4/C5 验收计划

C4 focused tests 至少覆盖：

- local model configuration、provider capability gate、no implicit download/network-off；
- PNG/JPEG/WebP success、blank、corrupt、unsupported、oversized/pixel boundary；
- structured output、confidence `[0,1]`、`clear/uncertain` 与固定阈值；
- empty/invalid/garbled output、provider missing、timeout、output limit；
- idempotency success replay、mismatch、running conflict、failed retry；
- draft creation、user edit protection、explicit confirm/reject/archive；
- same-material extraction/revision、chunk/index/citation validation 与 atomic rollback；
- delete/restore/purge/stale/source-unavailable；
- backup→verify→restore to a new empty target，且 restore/startup/read/verify 不运行 OCR、不修复状态、不发送 delivery；
- API project scope、稳定错误、隐私 response、无路径/secret/raw response。

C5 必须运行：

- 变更域 focused backend tests；
- 真实本地模型仅在显式 opt-in、非敏感 synthetic image 下运行；
- 静态 capture 页面 desktop、窄屏、键盘、reload、failure/retry、duplicate click、uncertain/review/confirm 和 source lifecycle Chromium tests；
- backup/restore、migration/history/user_version、startup/readiness、diagnostics 与完整 backend regression；
- 记录精确 provider/model/environment/input scope 和 `not_verified` 限制。

C6 必须提供脱敏 acceptance evidence，并同步 STATUS/TODO/ROADMAP。`implemented`、`smoke_passed`、`real-pass` 必须分开；一次 synthetic 图片通过不能外推为通用 OCR 能力。

## 10. C3 交付与禁止事项

本 C3 交付只包括正式契约、审计/证据索引和文档状态同步。禁止在 C3：实现 adapter、修改 `backend/app/`、修改 schema/migration、增加 API/UI、接入 task runner、下载模型、运行真实用户图片或提交生成 artifact。

C3 通过后唯一推荐下一步是 B2 C4：在 Formal 中独立实现上述精确 scope 的 `ImageOcrProvider`，仍不与 C5 浏览器/完整回归混在同一任务中。

# Phase 9D Acceptance Evidence

> 状态：`scoped-gates-pass` / `restore-gates-pass` / `closeout-scoped-pass`。
>
> 本文收口的是 9D-0 部分立项所批准的范围：deterministic fake/loopback S7 课堂采集与转写、确认后接入 S2、S6 脱敏报告快照/预览/导出、本地 delivery `off`/`dry_run` 审计、Chromium workspace、source lifecycle 和 backup/verify/restore non-repair。
>
> 准确声明：Phase 9D 的上述部分立项范围已完成 Gate A-L 的对应验收；这不等于未经立项的真实 OCR/ASR、真实 SMTP/飞书外发或全局 production `real-pass` 已完成。由于 9D-0 明确为部分立项，本文不把整个未立项的 Phase 9D 扩大声明为全量完成。
>
> 本文不包含数据库、backup 文件、上传原件、Provider key、私有路径、raw provider response、测试运行 artifact 或真实外发数据。

## 1. Scope And Decision

9D-0 的五项评审结论为：

- 真实需求：S7 课堂采集到 S2 资料管线的需求成立；S6 脱敏聚合有场景价值，但家长账号/多用户体系不在当前系统边界。
- 隐私：S7 敏感音频/图片复用现有 material/original lifecycle；S6 只允许白名单聚合；对外交付是高风险路径。
- 保留：采集原件、转写、报告和交付审计服从现有生命周期与显式清理语义，不引入自动 retention worker。
- 真实组件证据：真实 OCR/ASR、SMTP、飞书生产端点均缺少当前正式系统所需的通用 evidence。
- 运维成本：fake/loopback、本地 SQLite 和 dry-run 成本可控；真实组件成本、送达、退信和合规未评估。

因此 9D-0 结论是 `conditional go / partial scope`：

- 允许：deterministic fake/loopback、单进程 SQLite、本地 Chromium、backup/restore、本地 dry-run。
- 暂缓：真实 OCR/ASR provider 通用接入、真实 SMTP/飞书生产外发、scheduler/worker、自动定时推送、多用户/家长账号、云同步。

权威范围和契约：

- [`prompts/phase9d/PHASE9D_AUDIT_AND_SCOPE.md`](prompts/phase9d/PHASE9D_AUDIT_AND_SCOPE.md)
- [`prompts/phase9d/PHASE9D_DOMAIN_CONTRACT.md`](prompts/phase9d/PHASE9D_DOMAIN_CONTRACT.md)
- [`prompts/phase9d/EXECUTION_ORDER_AND_GATES.md`](prompts/phase9d/EXECUTION_ORDER_AND_GATES.md)

## 2. Gate Matrix

| Gate | Result | Evidence |
|---|---|---|
| A 立项与范围 | pass for approved partial scope | 9D-0 audit-draft；partial-go、privacy、retention、real-component and ops conclusions in Section 1 |
| B 领域契约 | pass | 9D-1 contract-frozen；capture/transcript/report/delivery state machines, idempotency, source and privacy rules |
| C 数据库 | pass | v12 migration and rollback/history/user_version/backup checks covered by migration and full backend suite |
| D 共享领域层 | pass | `test_phase9d_domain.py`、`test_phase9d_delivery.py`、report projection, scope, transaction, append-only and redaction checks |
| E S7 采集/转写 | pass | `test_phase9d_capture.py`；`test_phase9d_api.py`；fake/loopback, type/size, confidence, uncertain, timeout, malformed output and retry |
| F S7 接入 S2 | pass | `test_phase9d_capture_ingest.py`；same material revision, chunks/FTS retrieval, citations, edit protection, confirm rollback |
| G S6 报告 | pass | `test_phase9d_report.py`、`test_phase9d_domain.py`；four report kinds, timezone half-open period, whitelist, source degradation and safe export |
| H S6 交付 | pass for off/dry-run boundary | `test_phase9d_delivery.py`、`test_phase9d_api.py`、Chromium 9D S6 paths；default off, allowlist, idempotency, audit and live rejection |
| I API/UI | pass | `test_phase9d_api.py` 4 tests；`browser_phase9d.spec.js` 4 tests；desktop/narrow/keyboard/reload/failure/privacy paths |
| J 生命周期/恢复 | pass | `test_phase9d_backup_restore.py` 4 tests；soft-delete/purge degradation, history preservation, verify→new-empty-target restore and non-repair |
| K 真实组件边界 | pass as explicit boundary | real-provider smoke remains default skipped; real OCR/ASR and live delivery are `not_verified`/not approved, not silently enabled |
| L 收口 | pass for scoped closeout | this evidence plus synchronized STATUS/TODO/ROADMAP/PROJECT_PROGRESS/INDEX/README and regression results in Section 5 |

## 3. Implemented User Paths

### S7 ClassCapture

- Create one project-scoped capture session for one audio/image asset.
- Upload through hash-derived originals and bind one capture material.
- Run deterministic fake or local loopback transcription.
- Render safe status, confidence and uncertain markers without exposing stored paths or raw provider data.
- Edit draft explicitly, then confirm or reject.
- Confirm creates the same capture material's transcript extraction/revision and existing chunk/FTS/citation chain.
- Retry and idempotency retain safe operation history; user edits are not silently overwritten.
- Delete/purge of the source degrades `source_deleted`/`source_unavailable` while retaining historical transcript and operation facts.

### S6 ParentReport

- Generate `daily`, `weekly`, `monthly`, and `exam_alert` snapshots with explicit IANA timezone and half-open date windows.
- Aggregate existing learning facts read-only.
- Expose only the safe whitelist: counts, minutes, coarse buckets, source-quality counts and boolean quality flags.
- Preview and export JSON/Markdown deterministically.
- Delivery defaults to `off`; local `dry_run` is allowlisted and does not connect to a third party.
- Live delivery remains blocked by `delivery_live_not_approved`; delivery attempts are append-only and idempotent.
- Reload and restore do not implicitly generate reports or create delivery attempts.

## 4. Privacy And Failure Evidence

The verified response/DOM boundaries exclude, where applicable:

- `stored_path`, private filesystem paths and source storage layout;
- Provider keys, secrets and raw provider requests/responses;
- report source text, material path/name, answer keys, submitted answers, Q&A text and per-question details;
- real delivery payloads or third-party response bodies.

Failure and boundary coverage includes:

- unsupported media, signature mismatch, size limit, duplicate upload and upload rollback;
- provider unavailable, timeout, malformed/empty output, invalid output and explicit retry;
- uncertain segments, user edit protection, invalid citation and source deletion/purge;
- report invalid period, report redaction boundary, export failure and delivery idempotency mismatch;
- default-off delivery, allowlist rejection and live-delivery rejection;
- malformed/network UI responses, duplicate click, reload recovery, keyboard focus and 390x844 overflow.

## 5. Commands And Results

All commands were run from `H:\studybuddy` using the project Python environment.

Full backend regression:

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q -p no:cacheprovider
```

Result:

```text
360 passed, 2 skipped
```

The two skips are opt-in real-provider smoke tests. No real OCR/ASR or live delivery test was promoted to a default pass.

Focused Phase 9D backend matrix:

```text
C:\miniconda\py310\python.exe -m pytest \
  backend/tests/test_phase9d_api.py \
  backend/tests/test_phase9d_capture.py \
  backend/tests/test_phase9d_capture_ingest.py \
  backend/tests/test_phase9d_delivery.py \
  backend/tests/test_phase9d_domain.py \
  backend/tests/test_phase9d_report.py \
  backend/tests/test_phase9d_backup_restore.py -v --tb=short
```

Result: `35 passed`.

Related Phase 8/9 Chromium and frontend failure regression:

```text
npx playwright test \
  backend/tests/browser_phase8.spec.js \
  backend/tests/browser_phase9a.spec.js \
  backend/tests/browser_phase9b.spec.js \
  backend/tests/browser_phase9c.spec.js \
  backend/tests/browser_phase9d.spec.js \
  backend/tests/browser_frontend_failure_contract.spec.js --workers=1
```

Result: `22 passed`.

The Phase 9D browser subset is `4 passed`; the full related set includes Phase 8, Phase 9A/9B/9C and the frontend failure contract.

Static verification:

```text
C:\miniconda\py310\python.exe -m py_compile backend\app\main.py
```

Result: passed. `git diff --check`: passed before closeout edits.

## 6. Version And Persistence Boundary

- Formal schema is v12.
- 9D migration is registered through `backend/app/migrations/runner.py`; no runtime business-table creation was added for closeout.
- 9D facts are included in SQLite backup and restored to a new empty target.
- Restore rebases internal original paths to the selected target; this is expected path relocation, not source repair.
- Restore, startup, read and verify do not call OCR/ASR, regenerate reports, send delivery, or upgrade degraded source status.
- Historical transcript, operation, report snapshot and delivery audit facts remain append-only/readable within their safe contracts.

## 7. Remaining Limits

The following remain outside this partial closeout and are not verified:

- general real OCR/ASR provider compatibility, accuracy, capacity, cost or production credentials;
- SMTP/Feishu production delivery, recipient identity, deliverability, bounce handling and compliance;
- scheduler, worker, queue, background retry, automatic push or reminder;
- authentication, parent accounts, multi-user or cloud synchronization;
- multiple workers/instances sharing a data root;
- system-level screen-reader validation, extreme content and long-duration stability;
- real power-loss recovery, network filesystem, disk-full and hardware corruption behavior;
- global production `real-pass`.

The accurate completion wording is:

> Phase 9D 的 9D-0 部分立项范围已在 deterministic fake/loopback 组件、单进程 SQLite、本地 Chromium、backup/restore 与本地 dry-run 交付的明确范围内完成并完成收口；不代表真实 OCR/ASR provider 通用验证、真实对外交付（SMTP/飞书生产端点）、自动 scheduler/worker/定时推送、多用户/云同步、系统级 screen reader、极端内容、长时稳定性或全局 production `real-pass`。

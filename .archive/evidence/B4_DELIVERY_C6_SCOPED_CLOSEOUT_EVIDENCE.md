# B4 Delivery C6 Scoped Closeout Evidence

> Gate: B4 C6
> Status: `scoped closeout passed`
> Scope: local single-process Formal delivery boundary for the exact independently tested SMTP and Feishu synthetic smoke paths.
>
> This closeout does not open Formal product API live delivery.

## Gate review

| Gate | Review result | Evidence |
|---|---|---|
| C0-C1 Composer | reviewed feasibility input | component cards and loopback smoke record |
| C2 Integration | reviewed isolated combination input | `studybuddy-integration` C2 result and channel-specific smoke record |
| C3 Formal contract | passed | `docs/contracts/B4_DELIVERY_COMPONENT_CONTRACT.md`, `docs/evidence/B4_DELIVERY_C3_CONTRACT_EVIDENCE.md` |
| C4 Formal implementation | passed | `docs/evidence/B4_DELIVERY_C4_IMPLEMENTATION_EVIDENCE.md` |
| C5 Formal acceptance | passed in declared scope | `docs/evidence/B4_DELIVERY_C5_ACCEPTANCE_EVIDENCE.md` |
| C6 isolation, privacy, regression, evidence review | passed in declared scope | this record |

Formal implementation was independently written in `H:\studybuddy`. It imports no implementation or configuration from `H:\studybuddy-composer` or `H:\studybuddy-integration`. The smoke runner reads only its own current-process environment and has no database writes or product API integration.

## Reviewed delivery behavior

- SMTP and Feishu are separate adapters, separately configured and separately smoke-tested.
- SMTP is host-restricted to `smtp.163.com` and `smtp.qq.com`; Feishu is HTTPS host/path restricted to the approved custom-bot webhook scope.
- SMTP recipient mapping, SMTP credentials, and Feishu webhook values are runtime-only and excluded from `AppConfig` representation. Audit data uses opaque target labels only.
- The product default remains `delivery=off`; default off and dry-run do not call network adapters.
- Browser live runtime state remains fail-closed at `delivery_authorization_required`; backend coverage verifies the deeper `delivery_live_not_approved` product gate after explicit request authorization.
- `run_b4_delivery_c5_smoke.py` is an operator-only, one-channel runner. It requires explicit process authorization and uses a fixed synthetic message with no study material.
- No automatic retries, scheduler, queue, background worker, report regeneration, source-state repair, schema migration, or parallel delivery state was introduced.

## Exact accepted smoke scope

| Channel | Accepted evidence | Scope limit |
|---|---|---|
| SMTP | runner returned `sent`; operator confirmed QQ receipt | one operator-configured 163 SMTP sender to one operator-configured QQ mailbox, fixed synthetic content |
| Feishu | runner returned `sent`; operator confirmed group receipt | one operator-configured Feishu custom-bot webhook, fixed synthetic content |

The common fixed synthetic content summary was `73` characters with SHA-256 `aeb8d952e6fa5e73c2f11f11faf76ff2265d7cd06fcdfe343f3583f3be170e97`.

## Privacy and restore review

- C5 evidence contains no address, authorization code, webhook, group name, raw provider response, report body, study material, source text, answer, attachment, or local path.
- C6 added an explicit regression assertion that SMTP target addresses do not appear in the `AppConfig` representation.
- Source lifecycle is aggregate-only for reports and does not cause send/retry/repair work.
- Backup/verify/restore tests monkeypatch both Formal adapters and fail if either is invoked; delivery attempts/history round-trip without delivery side effects.
- The credentials and webhook used during smoke were exposed outside the Formal secret boundary and must be rotated before any future live smoke. They are not present in repository files or evidence.

## Verification

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_b4_delivery_c4_config.py backend/tests/test_b4_delivery_c4_adapters.py backend/tests/test_b4_delivery_c5_smoke.py backend/tests/test_phase9d_delivery.py backend/tests/test_phase9d_backup_restore.py backend/tests/test_phase9d_api.py -q
35 passed in 9.03s

npx playwright test backend/tests/browser_phase9d.spec.js --workers=1 --reporter=line
5 passed

C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
468 passed, 3 skipped in 228.47s

python backend/scripts/check-source-size.py
git diff --check
```

The three skipped backend tests are explicit opt-in real ASR/provider smoke tests. Source-size and diff checks passed.

## Remaining limits

B4 does not establish arbitrary SMTP/webhook compatibility, production recipient policy, bulk delivery, attachments, HTML email, Feishu cards, signing, scheduling, retry automation, capacity, crash recovery, multi-user authorization, cloud deployment, or global production `real-pass`.

The Formal product API live gate remains intentionally closed. Any future product-facing live delivery requires a new separately approved contract and acceptance slice; this scoped closeout must not be used to bypass `delivery_live_not_approved`.

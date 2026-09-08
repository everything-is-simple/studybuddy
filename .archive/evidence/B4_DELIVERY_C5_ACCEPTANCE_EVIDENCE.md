# B4 Delivery C5 Acceptance Evidence

> Gate: B4 C5
> Status: `scoped acceptance passed`
> Scope: Formal SMTP and Feishu synthetic channel smoke, default-off/live-blocked browser state, source lifecycle aggregation, and backup/restore no-send behavior.
>
> Formal product API live delivery remains closed.

## Channel-specific synthetic smoke

The operator ran `backend/scripts/run_b4_delivery_c5_smoke.py` from a local PowerShell process with the script's required per-run environment authorization. The runner accepts exactly one channel per invocation and uses only this fixed synthetic text:

```text
StudyBuddy B4 C5 synthetic delivery smoke. No study material is included.
```

The runner output records the following non-sensitive facts:

| Channel | Result | Operator receipt confirmation | Scope |
|---|---|---|---|
| SMTP | `sent` | QQ mailbox receipt confirmed | one operator-configured 163 SMTP sender to one operator-configured QQ mailbox |
| Feishu | `sent` | target Feishu group receipt confirmed | one operator-configured Feishu custom-bot webhook |

Both results used the same fixed synthetic content summary:

```text
synthetic_content_chars: 73
synthetic_content_sha256: aeb8d952e6fa5e73c2f11f11faf76ff2265d7cd06fcdfe343f3583f3be170e97
```

No report snapshot, study material, source text, user answer, attachment, address, credential, webhook, raw SMTP response, HTTP response, group name, or local path is included in this evidence.

## Formal safety gates verified

- SMTP and Feishu use independent adapter/configuration paths and were smoked separately.
- The smoke runner requires `LIVE_SMOKE=1`, a fixed confirmation string, a single explicit channel, and channel-specific runtime configuration; missing authorization fails closed.
- The product API does not invoke the smoke runner.
- Browser verification with live mode, runtime enablement, and runtime authorization displays `delivery_authorization_required`, `blocked`, and `未发送`; it does not display address or webhook material.
- The deeper `delivery_live_not_approved` gate remains covered by backend tests with explicit per-request authorization. No product API live request was sent.
- Report source lifecycle remains aggregate-only; deleted/unavailable source state is not used to send, retry, or repair delivery.
- Backup/verify/restore tests monkeypatch both Formal adapters and fail if either is called. Restore preserves audit history and does not send, retry, reindex, regenerate reports, or repair delivery state.

## Verification

Commands run from `H:\studybuddy`:

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_b4_delivery_c4_adapters.py backend/tests/test_b4_delivery_c4_config.py backend/tests/test_b4_delivery_c5_smoke.py backend/tests/test_phase9d_delivery.py backend/tests/test_phase9d_backup_restore.py backend/tests/test_phase9d_api.py -q
35 passed in 9.32s

npx playwright test backend/tests/browser_phase9d.spec.js --workers=1 --reporter=line
5 passed

C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
468 passed, 3 skipped in 247.82s
```

The three skipped backend tests are explicit opt-in real ASR/provider smoke tests. Source-size and diff checks are required before C5 documentation is committed.

## Limits and C6 input

This evidence proves only the two exact operator-controlled synthetic channel paths listed above. It does not establish arbitrary SMTP or webhook compatibility, recipient policy, bulk delivery, attachments, HTML email, Feishu cards, signing, scheduling, background work, retry automation, capacity, crash recovery, multi-user authorization, or global production `real-pass`.

The SMTP authorization code and Feishu webhook used during smoke have appeared outside the Formal secret boundary and must be rotated before any future live smoke. C6 must review the C0-C5 isolation boundary, committed code/tests/docs, redaction, source-size/diff results, and this scoped evidence before declaring scoped closeout.

# B4 Delivery C4 Formal Implementation Evidence

> Gate: B4 C4
> Status: `implemented / backend-pass`
> Scope: independent Formal SMTP and Feishu adapter implementation, runtime configuration parsing, and closed live-delivery boundary.
>
> This gate does not authorize Formal live delivery or send a network request.

## Implementation scope

- `backend/app/delivery.py` independently implements `SmtpDeliveryAdapter` and `FeishuWebhookDeliveryAdapter`. It does not import code or configuration from Composer or Integration repositories.
- SMTP is restricted to the declared QQ-compatible hosts `smtp.qq.com` and `smtp.163.com`; sender and recipient are runtime-only values resolved from an opaque target label.
- Feishu accepts only HTTPS URLs at `open.feishu.cn/open-apis/bot/v2/hook/`, rejects redirects encoded as query/fragment values, and resolves them only from a separate runtime target mapping.
- Adapter payloads are deterministic plain-text/Markdown representations of an existing ready report snapshot. Attachments, HTML mail, arbitrary templates, Feishu cards, signatures, and arbitrary endpoints remain out of scope.
- Content is checked before network I/O and has a 1 MiB transport limit. Adapter provider failures are mapped to stable errors without exposing provider details.

## Runtime configuration and secret boundary

- `backend/app/config.py` parses independent SMTP and Feishu target mappings, SMTP host/port/TLS/identity, a bounded timeout, and an optional validated Feishu webhook value.
- SMTP credentials and webhook values are runtime-only fields with `repr=False`; no configuration is persisted by this gate.
- Presence of a credential, target map, or webhook does not enable delivery. Formal does not read `H:\studybuddy-integration\.env.local`.

## Preserved closed behavior

- Default configuration remains `report_delivery_mode=off`, `report_delivery_enabled=false`, and `report_delivery_authorized=false`.
- `off` records `delivery_disabled` and never calls an adapter.
- `dry_run` uses `DryRunDeliveryAdapter`, which does not open a socket or HTTP connection.
- Fully configured and explicitly confirmed `live` requests still stop at `delivery_live_not_approved` before adapter selection or invocation.
- Existing append-only audit, idempotency replay, and explicit retry semantics remain owned by the Phase 9D repository boundary. No worker, scheduler, implicit retry, migration, or parallel delivery state was introduced.

## Focused verification

Commands run from `H:\studybuddy`:

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_b4_delivery_c4_adapters.py backend/tests/test_b4_delivery_c4_config.py backend/tests/test_phase9d_delivery.py -q
22 passed in 2.12s

C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
464 passed, 3 skipped in 261.48s

python backend/scripts/check-source-size.py
git diff --check
```

The three skipped tests are explicit opt-in real ASR/provider smoke tests. The source-size and diff checks passed.

Focused tests cover independent channel allowlists, target mapping parsing, duplicate/malformed configuration rejection, secret repr redaction, payload limits, SMTP timeout mapping, Feishu HTTP error mapping, idempotency replay, explicit retry, default-off no-adapter behavior, and the live gate's no-adapter behavior.

## Limitations and next gate

C4 is implementation and offline/backend evidence only. It does not establish live SMTP or Feishu availability, sender/recipient policy, arbitrary provider compatibility, browser capability state, source lifecycle behavior, backup/restore non-send behavior, or global production `real-pass`.

B4 C5 must add the specified backend/browser/source lifecycle/backup-restore gates and separately authorized, synthetic, channel-specific Formal smoke evidence before C6 can review scoped closeout. Credentials and endpoints previously exposed outside Formal must be rotated before any later live smoke and must not be reproduced in evidence.

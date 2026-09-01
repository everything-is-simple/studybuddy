# B4 Delivery C3 Formal Contract Evidence

> Gate: B4 C3
> Status: `contract-frozen`
> Scope: separate SMTP and Feishu delivery channels, local single-process Formal boundary, default-off delivery, and explicitly authorized synthetic live smoke.

## Evidence reviewed

- `docs/contracts/B3_REPORT_COMPONENT_CONTRACT.md`
- `docs/evidence/B3_REPORT_C6_SCOPED_CLOSEOUT_EVIDENCE.md`
- `backend/app/delivery.py`
- `backend/app/config.py`
- `backend/app/api/study_capture_reports.py`
- `backend/tests/test_phase9d_delivery.py`
- `H:\studybuddy-integration\results\delivery-b4-c2\integration.json`
- `H:\studybuddy-integration\results\delivery-b4-live-smoke\smtp-only.json`
- `H:\studybuddy-integration\results\delivery-b4-live-smoke\feishu-only.json`
- Composer delivery component cards and loopback smoke evidence

## Verified feasibility inputs

- Integration C2 passed in an isolated temporary data root for report export, dry-run no-network behavior, SMTP/HTTP loopback payloads, allowlists, idempotency, explicit failure/retry, source lifecycle, append-only audit, backup/restore non-repair, and restore no-send behavior.
- Explicitly authorized live smoke passed for one operator-configured 163 SMTP sender to one QQ mailbox after the VPN was disabled. The message was synthetic and the operator confirmed receipt.
- Explicitly authorized Feishu live smoke passed for one operator-configured Feishu custom-bot webhook with synthetic text content.
- The live smoke artifacts record no credential, full webhook, full recipient, report body, raw response, or private path.
- The successful live smoke results are exact configuration/network evidence only and do not approve arbitrary SMTP or Feishu deployments.

## Frozen Formal decisions

- Reuse the existing B3 report snapshot and `report_delivery_attempts` repository boundary.
- Keep SMTP and Feishu as separate channels with separate configuration, allowlists, adapter behavior, and evidence.
- Keep `delivery=off` as the default; dry-run never opens a network connection; live remains rejected until B4 C4/C5/C6 authorize the precise implementation.
- Require runtime-only secrets, explicit per-request authorization, channel/target allowlists, deterministic safe content, bounded timeouts, idempotency, append-only audit, explicit retry, and fail-closed stable errors.
- Never persist or expose credentials, addresses, webhook URLs, report bodies, source text, paths, raw provider responses, SQL, or tracebacks.
- Startup, ordinary reads, report generation, verify, backup, and restore must not send, retry, or repair delivery.
- Do not copy Composer or Integration code into Formal.

## C4/C5/C6 acceptance target

C4 independently implements the exact adapters behind the existing boundary without opening live traffic by default. C5 verifies backend and browser blocked/capability states, allowlists, redaction, timeout/error mapping, idempotency/retry, source lifecycle, backup/restore no-send, and separately authorized synthetic live smoke for each channel. C6 reviews the full evidence and records only the exact tested scope.

## Limitations

This evidence does not establish arbitrary SMTP provider compatibility, arbitrary webhook compatibility, bulk delivery, attachments, HTML email, Feishu cards/signatures, scheduler reliability, concurrency/capacity, power-loss recovery, multi-user authorization, or global production `real-pass`. Provider credentials and endpoints used by the live smoke were operator-provided secrets and are not reproduced here.

## Gate result

`B4 C3 = contract-frozen`.

Formal system behavior is unchanged by this gate. B4 C4 may begin. Live delivery remains closed in `H:\studybuddy` until the later Formal implementation and acceptance gates pass.

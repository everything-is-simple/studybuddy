# B4 Delivery Component Formal Contract

> Gate: B4 C3
> Status: `contract-frozen`
> Scope: independently controlled QQ-compatible SMTP and Feishu webhook delivery, with local dry-run as the Formal baseline and explicitly authorized live smoke only.
>
> This contract freezes the Formal boundary. It does not enable live delivery, change the schema, add a migration, or import Composer/Integration code.

## 1. Decision and boundaries

B4 reuses the existing Phase 9D/B3 report snapshot and `report_delivery_attempts` domain. Formal must not create a parallel report, delivery state, audit, credential, or scheduler store. SMTP and Feishu remain separate channels with separate configuration, target allowlists, adapter behavior, and evidence.

The existing Formal default remains authoritative:

- `delivery=off` by default;
- `dry_run` records an audit fact and never opens a network connection;
- `live` remains rejected until the B4 Formal gates authorize a precise adapter;
- no background worker, scheduler, automatic reminder, or implicit retry is introduced.

Composer and Integration evidence establishes feasibility only for its declared scopes. Formal must independently implement against this contract and the existing report/repository boundaries; it must not copy their implementation.

## 2. Approved channel scope

### 2.1 SMTP

The first candidate is standard SMTP over an explicitly configured TLS transport. The verified Integration live smoke used a non-production synthetic message from an operator-configured 163 SMTP account to an operator-configured QQ mailbox. This is evidence for that exact tested configuration and network path only; it does not approve arbitrary SMTP providers, accounts, ports, recipients, or mail content.

Formal must define the provider host, port, TLS mode, sender, and recipient as runtime configuration. Credentials are runtime-only secrets and must never be persisted, returned, or logged. A target label, not an email address, is persisted in the audit.

### 2.2 Feishu webhook

The first candidate is an HTTPS Feishu custom-bot webhook under the approved Feishu host/path scope. The verified Integration live smoke sent a synthetic text message to an operator-configured webhook. This does not approve arbitrary Feishu tenants, bots, webhook URLs, cards, rich content, or signing schemes.

The full webhook is runtime-only secret material. Formal responses and audit facts expose only an opaque target label and stable outcome. URL validation must occur before any request is opened.

## 3. Input and content contract

Delivery is an explicit synchronous request for an existing, ready, project-scoped report snapshot. Clients cannot submit or override the report body, safe payload, project, source identity, stored path, provider metadata, recipient address, webhook URL, or credentials.

The adapter receives only the server-loaded safe report payload and deterministic Markdown from the existing snapshot boundary. It must reject empty, invalid, oversized, or redaction-failing content before network I/O. The first Formal content format is Markdown/plain text for SMTP and the approved deterministic text payload for Feishu; PDF, arbitrary HTML/email templates, Feishu cards, AI narrative, and attachments are out of scope.

Delivery must not disclose source names, paths, source text, transcript/OCR/ASR text, answer keys, submitted answers, secrets, SQL, traceback, or raw provider response. The report content may contain only the already-approved B3 safe aggregate projection.

## 4. Authorization and safety gates

Live delivery requires all of the following, evaluated server-side for every request:

1. runtime mode is `live`;
2. the channel is enabled by explicit runtime configuration;
3. the opaque target label is in the channel's allowlist;
4. operator authorization is enabled;
5. the request carries a valid per-request explicit authorization/confirmation;
6. the report is ready and project-scoped;
7. the request has a valid idempotency key;
8. the channel-specific adapter and secret configuration pass validation.

Any missing or invalid gate fails closed with a stable safe error. Configuration presence alone must never enable delivery. Browser UI may expose capability and blocked reasons, but must not save, echo, or persist secrets. Formal live smoke remains an explicit operator action and never becomes an automatic product path.

## 5. Audit, idempotency, and retry

Reuse the existing append-only `report_delivery_attempts` table and repository semantics. Do not add a second audit table or delivery state machine.

Each attempt records only bounded public facts: project/report identity, channel, opaque target label, mode, safe content fingerprint, idempotency-key fingerprint, status, stable error code, retry relation, and timestamps. It must not store the address, webhook, credential, report body, raw request, raw response, or private path.

The same idempotency key and unchanged content/target request returns a safe replay without another network call. Reuse of a key with a different target, channel, mode, or content fingerprint returns `delivery_idempotency_mismatch`. Retry is explicit, references a prior failed attempt, and creates a new append-only attempt. There is no implicit retry, queue, or background resend.

## 6. Error and provider boundary

Expose only stable errors, including:

- `delivery_disabled`
- `delivery_target_not_allowed`
- `delivery_authorization_required`
- `delivery_live_not_approved` (while the Formal live gate is closed)
- `delivery_idempotency_mismatch`
- `delivery_failed`
- `delivery_timeout`
- `delivery_configuration_invalid`
- `delivery_redaction_violation`
- `payload_too_large`

Provider exceptions, SMTP response text, HTTP response bodies, URLs, addresses, credentials, tracebacks, and local paths must be mapped at the adapter boundary and must not cross the API, log, audit, or evidence boundary. Timeouts are bounded and fail closed. The adapter must not follow redirects or contact a target outside the validated channel allowlist.

## 7. Lifecycle, backup, and restore

Delivery reads an immutable ready snapshot and does not mutate learning facts, source status, materials, revisions, chunks, citations, or report content. Source deletion, purge, stale state, or source unavailability remains represented by the existing report quality aggregates; it does not trigger a send.

Startup, readiness, ordinary reads, report generation, verify, backup, and restore must not invoke an adapter, open a network connection, retry a previous attempt, or repair delivery/source state. Restore targets a new empty data root and preserves migration history, report snapshots, source degradation, and append-only delivery audit facts without sending.

## 8. Acceptance sequence

B4 Formal work is gated as follows:

- **C4:** independently implement or assemble exact SMTP and Feishu adapters behind the existing delivery boundary; preserve default-off/live-reject behavior until verified. Add focused tests for configuration, allowlist, redaction, timeout, provider error mapping, idempotency, explicit retry, and no-network default behavior.
- **C5:** run focused backend tests, browser capability/blocked-state tests, source lifecycle tests, backup/restore non-send tests, complete backend regression when shared behavior changes, and explicitly authorized synthetic live smoke for each approved channel. Evidence must be redacted and channel-specific.
- **C6:** review C0-C5 evidence, Composer/Integration/Formal isolation, source-size and diff checks, browser/regression results, privacy, and restore behavior; record only the exact tested channel/provider/network scope.

B4 C3 does not authorize C4 code to send live traffic, does not authorize production recipients, and does not establish general SMTP/Feishu compatibility.

## 9. Non-goals and not-verified boundaries

The following remain outside this contract: arbitrary SMTP providers, arbitrary webhook services, production recipient policy, bulk mail, attachments, HTML email, Feishu cards, signatures/encryption, scheduler/worker delivery, automatic reminders, multi-user authorization, rate/capacity guarantees, crash/power-loss recovery, cloud deployment, and global production `real-pass`.

## 10. Gate conclusion

`B4 C3 = contract-frozen` for the exact local single-process Formal delivery boundary, with separate SMTP and Feishu channels, default-off behavior, explicit authorization, allowlists, append-only audit, idempotency, safe errors, and controlled synthetic live smoke. B4 C4 may begin; Formal live delivery remains closed until its later gates pass.

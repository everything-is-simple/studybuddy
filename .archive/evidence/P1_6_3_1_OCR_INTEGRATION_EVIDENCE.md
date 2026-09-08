# P1-6-3-1 RapidOCR C2 Integration Evidence

> Status: `integration-not-passed / 2026-08-31`
>
> This evidence records a failed gate. It must not be cited as Formal authorization or real OCR acceptance.

## Executed check

The existing isolated Integration runner was executed on the current Windows/Python 3.10 host:

```text
C:\miniconda\py310\python.exe H:\studybuddy-integration\ocr-rapidocr\run_integration.py
```

Observed bounded console result:

```json
{"component":"ocr-rapidocr","gate":"C2","status":"integration_passed","checks":9}
```

The runner used RapidOCR 1.4.4 with ONNX Runtime 1.20.1 on CPU and produced non-empty real-model results for synthetic PNG, JPEG and WebP inputs. It did not import or invoke the Formal StudyBuddy runtime. No recognized text, image bytes, raw response, stderr, secret, or model path is copied into this evidence.

## Gate evaluation

The runner's self-reported status is not sufficient for the stricter P1-6-3 C2 contract. The effective gate result is `integration-not-passed` because:

- the primary PaddleOCR failure is represented by a hard-coded value and RapidOCR is not invoked through an actual fallback controller;
- no call evidence proves that the primary failure is retained, fallback is attempted exactly once, and no third provider is called;
- timeout is declared but not enforced around real inference;
- output bounds are not enforced by the Integration runner;
- RapidOCR uses package defaults rather than an explicit approved model-root argument;
- model hashes/provenance are not part of the durable C2 artifact;
- simplified local SQLite tables do not exercise the established operation/draft/source contract;
- backup/restore checks a row count but does not prove OCR call count remains zero during backup, verify, restore, startup and read;
- Composer governance still says `smoke_passed`/`Integration not_started`, while the Integration directory and result are uncommitted;
- the result does not validate PaddleOCR primary success in the same C2 matrix.

## Required repair slice

P1-6-3-1 must be rerun only after the Integration workspace provides:

1. explicit local PaddleOCR and RapidOCR model identities/roots and hash inventory;
2. network-disabled initialization;
3. bounded real inference and bounded sanitized output;
4. real primary success and real RapidOCR independent success;
5. controlled primary failure followed by an observed single RapidOCR call;
6. safe retained primary error and fallback reason;
7. stable both-provider failure and no third attempt;
8. operation/draft/source lifecycle integration without copying Formal implementation;
9. backup/verify/restore/startup/read call-count proof that neither OCR engine runs;
10. committed Integration artifacts and synchronized Composer governance status.

Until those checks pass, P1-6-3-2 contract freeze and all Formal implementation/acceptance/browser/closeout slices are blocked.

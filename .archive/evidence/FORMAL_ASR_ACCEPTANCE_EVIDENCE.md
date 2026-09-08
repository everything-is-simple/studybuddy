# Formal ASR Scoped Acceptance Evidence

> Status: `C0-C6 scoped closeout` for the exact local configuration below. This is not a general ASR quality, portability, capacity, or global production `real-pass` claim.

## Scope

- Host: current Windows development host only.
- Runtime: `Const-me/Whisper` 1.12.0 local CLI.
- Provider identity: `whisper-cpp` / `ggml-large-v3-turbo`.
- Audio oracle: public upstream `SampleClips/jfk.wav` fixture only.
- System boundary: explicit local configuration, single-process FastAPI, SQLite, hash-derived originals, and draft-first capture transcription.

The official release asset binary hash comparison remains `not_verified`. The evidence does not establish support for arbitrary audio, languages, formats, runtime installations, model revisions, or concurrent/multi-process use.

## Formal Contract

`WhisperCliCaptureProvider` is independently implemented in `backend/app/providers/_capture.py` and is selected only when all of the following explicit runtime configuration is supplied:

- `STUDYBUDDY_ASR_PROVIDER=whisper-cpp`
- `STUDYBUDDY_ASR_RUNTIME`
- `STUDYBUDDY_ASR_MODEL_PATH`

The adapter keeps original bytes in memory only, uses a per-run temporary directory, suppresses CLI stdout/stderr, parses bounded TXT/SRT output, removes temporary files, and maps unavailable runtime, timeout, empty output, and oversized output to stable provider errors. It never promotes output directly into a material revision: transcription creates a draft; only the explicit user confirmation endpoint creates the indexed revision and citations.

## Evidence

| Gate | Command or test | Result |
|---|---|---|
| Adapter contract | `C:/miniconda/py310/python.exe -m pytest backend/tests/test_formal_asr.py -q` | `4 passed, 1 skipped` (real runtime gate intentionally disabled) |
| Real configured API lifecycle and restore | `STUDYBUDDY_RUN_REAL_ASR_SMOKE=1 C:/miniconda/py310/python.exe -m pytest backend/tests/test_formal_asr.py -q` | `5 passed` |
| Real configured static-browser lifecycle | `STUDYBUDDY_RUN_REAL_ASR_SMOKE=1 backend/scripts/test-browser.ps1 -Spec @('browser_formal_asr.spec.js')` | `1 passed` |
| Focused default browser regression | `backend/scripts/test-browser.ps1 -Spec @('browser_a4.spec.js','browser_frontend_system_matrix.spec.js','browser_formal_asr.spec.js')` | `11 passed, 1 skipped` (real ASR browser gate disabled) |
| Full backend regression | `C:/miniconda/py310/python.exe -m pytest backend/tests/ -q` | `431 passed, 3 skipped` |
| Full Chromium regression | `npx playwright test backend/tests --workers=1 --reporter=line` | `130 passed, 4 skipped` |
| Source-size policy | `C:/miniconda/py310/python.exe backend/scripts/check-source-size.py` | passed |

The opt-in test uses a fresh temporary data root and confirms:

1. create, upload, transcribe, idempotency replay, user edit, and user confirmation succeed;
2. the real provider output remains a draft until explicit confirmation;
3. confirmation creates citation-backed revision data;
4. public API payloads omit stored paths, runtime paths, and model paths;
5. backup and verify succeed, restore targets a new directory, and restore preserves the confirmed transcript facts without invoking the provider.

The browser gate uses the same public fixture in an isolated data root. It verifies the safe capability snapshot, upload, real transcription, visible draft, explicit confirmation, and absence of runtime/model paths, stored paths, or tracebacks from the static page. It also locks the formal response field mapping (`id`/`status`) used by the capture page.

## Explicitly Not Verified

- official release asset hash equivalence;
- recognition accuracy beyond the public fixture;
- broad audio/media format and language support;
- cancellation and subprocess-tree cleanup against the exact production CLI process tree;
- long-running task/queue execution, concurrency, multi-process use, capacity, or production uptime.

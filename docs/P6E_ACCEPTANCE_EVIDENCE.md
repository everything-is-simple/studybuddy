# P6-E 核心工作流整体验收证据

> 本文只记录脱敏的测试 gate 和稳定限制，不记录 API key、Authorization、Provider raw response、完整 prompt、完整合成材料正文、私有路径、SQL、traceback 或 request transcript。

## 验收范围

P6-E fake Provider 主路径覆盖：

```text
导入 → ready → 显式 indexing → retrieval → Q&A thread → answer
→ citation → 正文定位 → 返回材料详情 → 返回 Q&A → 导出 → refresh/history
```

本轮新增：

- `backend/tests/browser_p6e.spec.js`
- `backend/tests/browser_p6e_real_provider.spec.js`

## Gate 结果

| Gate | Result | Evidence |
|---|---|---|
| Fake Provider complete workflow | pass | `browser_p6e.spec.js`: 1 passed |
| Retrieval empty | pass | `browser_p6e.spec.js`: explicit empty status, no answer/citation |
| Default/unconfigured Provider | pass | `browser_p6e.spec.js` and `browser_qa.spec.js` |
| Retry after timeout | pass | `browser_p6e.spec.js` and existing failure contract |
| Duplicate click | pass | existing `browser_qa.spec.js` failure/retry coverage |
| In-flight thread switch / stale response | pass | `browser_p6e.spec.js`, stale response is ignored rather than cancelled |
| Deleted source / export disabled | pass | `browser_p6e.spec.js`, citation lifecycle and material export tests |
| Network failure | pass | `browser_frontend_failure_contract.spec.js` |
| Rate limit / unavailable | pass | `browser_qa.spec.js` |
| Malformed input/provider safety | pass | frontend failure contract and backend provider tests |
| Desktop/narrow workflow | pass | P6-D and P6-E; `390x844` overflow assertion |
| Keyboard/focus/accessibility contract | pass | P6-D and existing Q&A browser tests |
| DeepSeek `deepseek-chat` exact P6-E path | pass (real network, rerun) | exact target/gateway; backend API 2 passed and browser target passed |
| Agnes `agnes-ai-hub` / `agnes-2.5-flash` exact P6-E path | pass (real network, rerun) | exact advanced gateway; backend API 2 passed and browser target passed |

## Commands and results

Fake and related browser regression:

```text
npx playwright test H:/studybuddy/backend/tests/browser_p6e.spec.js --workers=1 --reporter=line
4 passed

npx playwright test H:/studybuddy/backend/tests/browser_p6e_real_provider.spec.js H:/studybuddy/backend/tests/browser_p6d.spec.js H:/studybuddy/backend/tests/browser_qa.spec.js H:/studybuddy/backend/tests/browser_frontend_failure_contract.spec.js H:/studybuddy/backend/tests/browser_material_export.spec.js --workers=1 --reporter=line
19 passed, 3 skipped
```

Backend focused:

```text
D:/miniconda/py310/python.exe -m pytest backend/tests/test_qa_api.py backend/tests/test_ai_citation_lifecycle.py backend/tests/test_material_export.py backend/tests/test_ai_provider.py backend/tests/test_phase5_provider.py backend/tests/test_real_provider_smoke.py backend/tests/test_provider_acceptance_runner.py -q
47 passed, 2 skipped
```

Full backend:

```text
D:/miniconda/py310/python.exe -m pytest backend/tests/ -q
200 passed, 2 skipped
```

The full backend run emitted one existing httpx deprecation warning. No schema or migration was added for P6-E.

## Real Provider policy

The real-provider browser tests are default-skipped and require all of the following to match. This rerun executed each target in a separate process/configuration:

- `STUDYBUDDY_RUN_REAL_PROVIDER_UI_SMOKE=1`;
- `STUDYBUDDY_REAL_PROVIDER_UI_TARGET`;
- `STUDYBUDDY_AI_PROVIDER`;
- `STUDYBUDDY_AI_MODEL`;
- `STUDYBUDDY_AI_BASE_URL`;
- `STUDYBUDDY_AI_API_KEY`.

DeepSeek requires the exact `deepseek` / `deepseek-chat` target. Agnes requires the exact `agnes-ai-hub` / `agnes-2.5-flash` target and the existing advanced profile/gateway configuration. A successful short controlled request would only prove that exact provider/model/gateway run; it would not establish global Provider availability, quota, quality, uptime, or production readiness.

## Rerun results

The exact real-network gates were rerun separately with temporary data roots and synthetic material:

```text
DeepSeek: deepseek / deepseek-chat / https://api.deepseek.com/v1
  backend/tests/test_real_provider_smoke.py: 2 passed
  browser_p6e_real_provider.spec.js: DeepSeek target passed; Agnes target skipped by target gate

Agnes: agnes-ai-hub / agnes-2.5-flash / https://apihub.agnes-ai.com/v1
  backend/tests/test_real_provider_smoke.py: 2 passed
  browser_p6e_real_provider.spec.js: Agnes target passed; DeepSeek target skipped by target gate
```

The browser test's one non-target skip per run is intentional: one configuration can only select one Provider/model at a time. These results establish exact synthetic API/UI evidence, not global availability, quota, quality, uptime or production readiness.

## Remaining limitations

- The rerun executed real network calls for both exact target configurations; the evidence remains synthetic and bounded.
- Provider failure injection in browser tests covers the user-facing contract; it is not evidence that every external Provider emits each failure in production.
- System-level screen reader testing is not performed; accessibility evidence is Playwright/DOM contract based.
- Long-answer and narrow-layout coverage is controlled synthetic coverage, not a capacity or production-scale claim.
- Synchronous Provider HTTP requests are not truly cancelled; stale responses are ignored using UI generation/context checks.
- Supported deployment remains single-process, single-instance, local storage.

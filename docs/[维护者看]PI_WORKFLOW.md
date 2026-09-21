# StudyBuddy Pi Workflow

This guide keeps Pi sessions continuous while keeping project instructions short. It does not replace `AGENTS.md`, which contains only durable repository constraints.

## Start And Continue Work

- Start a named task with `pi -n "area-task"`, for example `pi -n "backend-provider-retry"`.
- Name an already-open session with `/name area-task`.
- Continue the latest project session with `pi -c`; use `pi -r` to select a prior session.
- Use `/tree` to return to an earlier point. Use `/fork` for an alternative approach and `/clone` to preserve a current branch before an experiment.

## Preserve Useful Context

- Prefer SoL-Pi observation pack and evidence-preserving reducer for large tool outputs. Those mechanisms keep a retrievable evidence id or receipt instead of leaving the full payload in the live prompt.
- Allow SoL-Pi online context compact for long sessions once context pressure is high. Do not wait for a manual `/compact` as the only compression path.
- When you still run `/compact`, require it to preserve: current goal, accepted decisions, key files, hard constraints, remaining steps, and verification commands.
- Use `/session` to inspect session size, token use, and cost before a long continuation. Displayed numbers are a snapshot, not a fixed savings promise.
- Session output that may be copied into project files or committable evidence may contain only a safe summary, a stable error code, and redacted paths. Never include provider keys, real textbook tokens, raw provider responses, original source text, databases, artifacts, or a complete session transcript.
- Store durable project facts, user preferences, and failure lessons with Hermes memory. Keep short-lived task state in the current session or its handoff, not in `AGENTS.md`.

## Model Defaults And Switching

- Open `/model`, select the preferred available model, then press `Ctrl+S` to save it as the startup default.
- Open `/thinking`, select the preferred level, then press `Ctrl+S` to save that default.
- Use `/scoped-models` to limit the cycle to available, credentialed models used for this project. Press `Ctrl+P` to cycle them and `Ctrl+L` to select directly.
- Do not put provider credentials, API keys, or machine-specific paths into repository files.

## Verify A Change

1. Restart Pi in `H:\studybuddy` and confirm the saved model and thinking level appear in the status bar.
2. Create a named session with `pi -n`, then use `pi -c` or `pi -r` to confirm it can be identified and continued.
3. Confirm `Ctrl+P` changes only among the models selected in `/scoped-models`.
4. Run `pi --verbose --offline` when investigating startup context or loaded resources. It is a diagnostic, not a token-usage measurement. Confirm the project `.pi/sol-pi.json` enables `observationPack`, `evidencePreservingReducer`, and `onlineContextCompact`, and that the run does not make network requests.
5. After a large `read` or `bash` result, confirm the observation ledger records an observation id plus original size or summary hash. After compact, the evidence id or receipt must still locate that result; the live context must not retain the full raw payload.
6. After an online compact, recover the current goal, accepted decisions, key files, hard constraints, remaining steps, and verification commands. Do not expect the full original tool output to return.

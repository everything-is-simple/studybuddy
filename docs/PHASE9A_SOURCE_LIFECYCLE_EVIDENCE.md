# Phase 9A Source Lifecycle Evidence Draft

> 状态：`draft`。9A-6 的 backend/browser scoped gates 已通过，但 9A-7 backup/restore 与 9A-8 acceptance closeout 尚未完成，因此不得将 Phase 9A 或 9A-6 写成最终 completed。
>
> 本文只记录脱敏的可复现结果，不包含数据库、原文件、正文、Provider key、路径或浏览器运行 artifact。

## Scope

本轮覆盖：

- material soft delete、restore、purge 与计划 module/item source link 状态传播；
- explicit source refresh，确认 startup/read/restore 不自动把 `source_deleted` 提升为 `valid`；
- 新 extraction/revision/re-index 后旧 link 的 `stale` 状态；
- `valid`、`source_deleted`、`source_unavailable`、`stale` 的服务端映射；
- active plan 在来源不可用时保持 active，pending、in_progress、completed item projection 与 progress event 保留；
- module link 和 plan item link 在 plan detail、summary、source API 中的一致展示；
- source link response 不复制正文、材料名称或 stored path；lifecycle mutation 不创建 AI operation 或调用 Provider。

## Evidence

Focused backend：

```text
/cygdrive/c/miniconda/py310/python -m pytest \
  backend/tests/test_phase9a_domain.py \
  backend/tests/test_phase9a_api.py \
  backend/tests/test_phase9a_source_lifecycle.py -q
```

结果：`16 passed`。

完整 backend：

```text
/cygdrive/c/miniconda/py310/python -m pytest backend/tests/ -q
```

结果：`270 passed, 2 skipped`。跳过项是默认关闭的 real Provider smoke，不属于本任务门禁。

Phase 9A Chromium：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
  H:\studybuddy\backend\scripts\test-browser.ps1 browser_phase9a.spec.js
```

结果：`3 passed`，单 worker；覆盖计划 happy path、source lifecycle delete/restore/purge/re-index safe path，以及 failure/retry、390x844 和 keyboard path。

## Contract Observations

- delete 后 link 为 `source_deleted`；restore 只恢复 material lifecycle，link 保持 `source_deleted`；显式 refresh 后才依据当前 source contract 重算为 `valid`。
- purge 保留 plan、item、module、link 和 progress history；link 为 `source_unavailable`，refresh 不会提升为 `valid`，也不恢复材料名称、正文或可点击 source。
- 旧 revision/chunk identity 在新 extraction/revision 被 indexing 后为 `stale`；旧 link 不被替换为新 link，历史 progress 不改变。
- source warning 不阻止 active plan；pending、in_progress、completed item 分别保留其当前 projection。已完成 item 的 progress event 仍为 append-only 历史。
- source validation 按 project scope 执行；不存在或伪造的 source identity reject，不落库。
- source lifecycle mutation 不执行解析、不复制 source text、不自动重新索引、不创建新的 `ai_operations`。显式 `ai-index` 仍是独立用户动作，不能解释为 lifecycle 自动调用 Provider。

## Remaining Limitations

- 9A-7 尚未完成 9A business data 的 backup/verify/restore history closeout。
- 9A-8 尚未完成全量 evidence、STATUS/TODO/ROADMAP 最终收口，因此本草案不能作为 Phase 9A completed 声明。
- 不覆盖真实 Provider、后台任务、多进程、多实例、真实断电或生产容量边界。

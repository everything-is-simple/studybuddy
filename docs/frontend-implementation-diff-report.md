# StudyBuddy 前端实现与设计差异记录

> 审计日期：2026-08-30
> 范围：`frontend-contract-fixtures.json`、`frontend-contract-audit.md`、`frontend-plan.md`、`frontend-contract-audit-report.md`，以及当前 `backend/app/static/`、API route、migration/domain contract 和 browser tests。
> 判定原则：把“实现与设计不同”区分为已修复的文档漂移、明确的产品边界差异和仍待验证的能力缺口；不把 fake/loopback/dry-run 当作真实能力通过。

## 1. 当前实现事实

- 正式静态前端为 `backend/app/static/`，共 21 个 `/app/*.html` 页面；`/` 重定向到 `/app/today.html`，`/legacy` 保留旧 workspace 回退。
- 当前前端契约自动审计：21 页面、152 后端路由、0 个发现项。
- Fixture 状态枚举已与后端 migration/domain 常量对齐：capture、plan、note、practice、report、task。
- 当前完整回归基线：backend `422 passed, 2 skipped`；browser `126 passed, 3 skipped / 129 total`（本次复核）。

## 2. 已发现并已修复的差异

| 编号 | 差异 | 证据 | 处理 |
|---|---|---|---|
| F-01 | `frontend-contract-audit-report.md` 原来只记录 14 个页面，实际已有 21 个页面。 | `backend/app/static/*.html`、自动审计输出 | 已重新生成报告，当前为 21 页面、152 路由、0 发现项。 |
| F-02 | Fixture 曾把 capture session 的 `review_required`/`failed` 漏掉，并把 task 的 `queued` 写成 `pending`。 | `backend/app/migrations/_v12_phase9d_extended.py`、`backend/app/diagnostics.py` | 已修正 fixture，并增加 backend enum 对比检查。 |
| F-03 | Fixture 把 report delivery mode 与 delivery attempt status 混在一个字段中。 | `backend/app/delivery.py`、`backend/app/migrations/_v12_phase9d_extended.py` | 已拆为 `delivery_modes` 与 `delivery_attempt_states`。 |
| F-04 | `frontend-contract-audit.md` 的页面盘点仍描述“待拆页面”，与实际独立页面实现不一致。 | 21 个静态页面、A3-PAGES browser evidence | 已更新为当前入口、已完成范围和后续边界。 |
| F-05 | `frontend-plan.md` 仍把 A3 起点、旧 `/` 入口和 A3-2/A3-3 作为待决定/待实施事项。 | 当前 `/` 路由、A3/A4 browser suites | 已改为当前完成事实和 B0-B4/Practice 后续顺序。 |

## 3. 实现与设计的明确差异（有意保留）

| 编号 | 设计/目标 | 当前实现 | 判定 |
|---|---|---|---|
| D-01 | Practice 页面最终应支持完整 review、mark-mistake、feedback 和更广端到端工作流。 | 已完成 session start/submit/finish/result、来源提醒、retry/stale 安全边界；完整 review/mark-mistake/feedback 尚未迁移。 | **未完成，属于后续切片**；不是当前回归失败。 |
| D-02 | B3 后迁移 reports export 与完整 append-only audit workspace。 | `reports.html` 当前主要是只读报告列表/边界说明；导出/完整审计 UI 尚未开放。 | **按门禁延后**；不能宣称 B3。 |
| D-03 | Provider 设置未来可支持安全写入与 connection-test。 | `settings.html`/`settings-provider.html` 只读展示 capabilities/readiness；没有密钥保存或配置写入。 | **安全契约未批准，按设计保持关闭**。 |
| D-04 | B1/B2/B4 提供真实 ASR、OCR 和 live delivery。 | 当前只有 9D deterministic fake/loopback capture/transcription、report dry-run；live delivery 默认关闭并拒绝。 | **未实现/未验证**；不得扩大 real-pass。 |
| D-05 | 任务页面可展示已批准任务。 | `tasks.html` 只支持单任务详情、cancel/retry；runner 正式只批准 `embedding_index`，没有全局任务列表 API。 | **当前后端契约限制**；设计已明确该边界。 |
| D-06 | 视觉设计覆盖正式前端。 | 21 个 `/app` 页面已使用共享 Neutral Modern tokens/components；`/legacy` 仍保留旧样式。 | **实现符合正式页面设计**；旧样式属于兼容回退，不是未记录的正式入口。 |

## 4. 实现与实现（文档之间）的当前一致性

- `STATUS.md`、`TODO.md`、`PROJECT_PROGRESS_REPORT.md`、`PHASE_ROADMAP.md` 和 `ROADMAP_CAPABILITIES.md` 当前统一使用约 65% 的阶段性估算。
- 当前测试数字为 backend `422/2`、browser `126/3`；历史 gate 数字已明确标注为 historical snapshot。
- A3/A4 已完成声明范围；Practice 只完成第一阶段；B0 为 governance scaffolded/smoke pending；B1-B4 和 D0-D1 仍未完成。
- 仍保留历史 evidence 中的旧 gate 数字，用于追溯，不作为当前基线。
- 本次逐页手工检查确认：21 个正式页面均可访问；无控制台错误；无数据时均显示安全 empty/missing-ID/blocked 状态。`classroom.html` 为采集/报告兼容工作区，`reports.html` 为独立报告页，已将导航文案修订为“课堂工作区”和“报告”。

## 5. 仍需处理的最紧要问题

1. 在 Composer 中选择候选并执行真实、离线优先、脱敏的 B0 smoke；当前 9 个候选全部仍为 `researching`。
2. B0 通过后优先推进 B1 ASR，并验证 timeout/cancel/retry、子进程清理、draft-first、source lifecycle、backup/restore 和浏览器闭环。
3. 继续把 Practice 后续写操作与 B3 report export/audit 分开立项，不绕过 capability gate。
4. 保持 Provider 写入、真实 OCR/ASR、live delivery、Tauri 安装包和多用户能力关闭，直到各自证据完成。

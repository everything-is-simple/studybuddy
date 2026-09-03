# P1-4 可用性收口证据（C0 切片：真实输入与重启复现证据补齐）

> 状态：`C0 slice / evidence-recorded`
> 日期：2026-09-02
> 范围：本文件只记录 P1-4 阶段 D 的第一个切片 C0。C0 的目标是补齐证据、把真相写下来，而不是改业务行为。本切片没有修改 `backend/app/`，没有新增 schema/migration/endpoint/错误码，也没有改动既有 API 的 URL、method、状态码、幂等语义或响应字段名。

审计与台账见 [`../contracts/P1_4_USABILITY_AUDIT_AND_CONTRACT.md`](../contracts/P1_4_USABILITY_AUDIT_AND_CONTRACT.md)。

## 1. 切片范围与交付

| 项 | 内容 |
|---|---|
| 台账条目 | P14-P0-01（真实输入链）、P14-P0-03（逐写操作重启复现）、P14-P0-04（问答/citation 链）；并把新发现的 P14-P0-05 记入台账 |
| 代码实现 | 无 `backend/app/` 变更（C0 是证据切片） |
| 新增测试 | `backend/tests/test_p1_4_real_input_chain.py`、`backend/tests/test_p1_4_restart_durability.py`、`backend/tests/browser_p1_4_real_input_restart.spec.js` |
| 剧本对应 | B1-1~B1-6、B2-1~B2-6、B3-1~B3-8、B4-1~B4-5、B5-1~B5-7 |
| 隔离 | 全部 pytest 使用 `tmp_path`；browser spec 使用 `H:/studybuddy-test/runs/p1-4-real-input-restart`（数据）与 `H:/studybuddy-test/runs/p1-4-real-input-fixtures`（样本）；未触碰 live data root |

## 2. 环境与精确工具

| 项 | 值 |
|---|---|
| 主机 | Windows，单进程、单实例、本地磁盘、单一 data_root |
| Python | `C:\miniconda\py310\python.exe`（3.10） |
| 后端 | FastAPI + `TestClient`（pytest）与 `uvicorn app.main:app`（browser） |
| 浏览器 | Playwright 管理的 Chromium（`chromium-1234/chrome-win64/chrome.exe`），headless |
| Provider | `STUDYBUDDY_AI_PROVIDER=fake`（deterministic）；真实 Provider、真实 OCR、真实 ASR、真实外发为 `not_verified` |
| 样本生成 | DOCX 由 `python-docx`、PPTX 由 `python-pptx`、PDF 由 Chromium `--print-to-pdf` 渲染多页文档；图片由 `Pillow` 生成 |
| 样本落点 | 运行时生成，不进仓库；不包含任何私有资料 |

## 3. 可复现命令与结果数字

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_p1_4_real_input_chain.py -q
11 passed

C:\miniconda\py310\python.exe -m pytest backend/tests/test_p1_4_restart_durability.py -q
7 passed

npx playwright test backend/tests/browser_p1_4_real_input_restart.spec.js --workers=1 --reporter=line
3 passed

C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
486 passed, 3 skipped

npx playwright test backend/tests --workers=1 --reporter=line
147 passed, 4 skipped

C:\miniconda\py310\python.exe backend\scripts\check-source-size.py
source-size check passed

C:\miniconda\py310\python.exe backend\scripts\audit-frontend-contract.py --strict
0 findings

C:\miniconda\py310\python.exe -m pytest backend/tests/test_governance_consistency.py -q
11 passed

git diff --check
clean
```

3 个 backend skip 均为默认关闭的 opt-in 真实 smoke（1 个 ASR、2 个 real provider）；4 个 browser skip 均为默认关闭的 opt-in real-provider/real-ASR smoke。首次完整 browser 运行时 `browser_p1_2_plans_notes_migration.spec.js` 出现一次服务生命周期抖动失败，单独重跑 `3 passed`，随后完整重跑 `147 passed, 4 skipped` 无失败；该抖动与本切片新增文件无关，未做代码改动。

## 4. A4 真实文件链实测结果（L1 + L2 + L3）

每一行都由真实容器样本实测得出，不是合成 TXT，也不是历史 gate 结论的外推。

| 扩展名 | 样本 | 解析状态 | span | 索引 | 检索 | Q&A citation | citation 回原文 | 重启后 |
|---|---|---|---|---|---|---|---|---|
| `.pdf`（多页 + 目录 + 双栏 + 页码） | Chromium 渲染 3 页 | `success` | 3 × `page`（ordinal 1..3） | `ready`，chunk ≥ 1 | `succeeded`，hits ≥ 1 | 1 条，`valid` | 归一化 excerpt 与 `text[start:end]` 一致 | 正文、span 数、索引 `ready`、citation `valid` 均回读成功 |
| `.docx`（标题 + 中文段落 + 表格 + 图片） | `python-docx` | `success` + 明确 warning | 1 × `document` | `ready` | `succeeded` | 1 条，`valid` | 一致 | 一致 |
| `.pptx`（两张文字页 + 一张图片页） | `python-pptx` | `success` | 3 × `slide` | `ready` | `succeeded` | 1 条，`valid` | 一致 | 一致 |
| `.txt`（中文 + 长文件名） | 运行时写入 | `success`，文件名原样保留 | 1 × `document` | `ready` | `succeeded` | 1 条，`valid` | 一致 | 一致 |
| `.md` | 运行时写入 | `success` | 1 × `document` | `ready` | `succeeded` | 1 条，`valid` | 一致 | 一致 |
| 图片页 PDF（无文字层） | Chromium 渲染 | `empty` + `PDF 没有可提取的文字层；本阶段不执行 OCR` | 1 | `empty`，chunk = 0 | `failed`/`retrieval_not_ready` | 无 | 不适用 | 一致（诚实空状态，不伪造 OCR） |
| `.doc` | 二进制头 | `rejected` / `requires_converter` | 0 | — | — | — | — | 一致 |
| `.ppt` | 二进制头 | `rejected` / `requires_converter` | 0 | — | — | — | — | 一致 |
| `.rtf` | 最小 RTF | `rejected` / `unsupported_rtf` | 0 | — | — | — | — | 一致 |
| `.xml` | 最小 XML | `rejected` / `unsupported_format` | 0 | — | — | — | — | 一致 |
| 损坏 PDF | 截断字节 | `failed` / `corrupt_pdf` | 0 | — | — | — | — | 一致 |
| 0 字节 TXT | 空文件 | `empty`，无 error code | 0 | — | — | — | — | 一致 |
| **加密 PDF** | `pypdf` 加密真实 PDF | `failed` / `corrupt_pdf` | 0 | — | — | — | — | 密码不出现在响应中 |

上传边界：超过 `max_upload_bytes` 返回 `413 file_too_large`，非法文件名返回 `400 invalid_filename`，两者都不产生材料记录。

## 5. A3 逐写操作重启复现结果（L3）

每个族的做法一致：用 `/app` 页面实际发送的请求体写入 → 关闭应用 → 在同一隔离 data root 上打开新应用 → 重新读取页面渲染的字段。

| 写操作族 | 页面 | 重启后回读内容 | 结论 |
|---|---|---|---|
| 目标 / 模块 / 计划 / 学习项 / 依赖 / 状态转换 | `plans.html` | 计划 `active`、标题、学习项 id 与状态 | `durable` |
| 节奏设置与分配 | `plans.html`、`today.html` | `target_minutes=90`、`timezone=Asia/Shanghai`、分配 id 与 `planned_minutes=45` | `durable` |
| 学习进度事件 | `plans.html` | `events == ["completed"]` | `durable` |
| 笔记创建 / 编辑 / 模块关联 / 确认 / 来源刷新 / 归档 | `notes.html` | 标题、`confirmed`、区块内容、关联模块；再次重启后 `archived` | `durable` |
| 卡组 / 卡片创建 / 编辑 / 确认 / 复习 | `cards.html` | 编辑后的 front、`ready`、列表包含该卡片；响应无 `answer_key` | `durable` |
| 练习集 / 题目创建 / 编辑 / 确认 | `exercises.html` | 编辑后的 prompt、`ready`；响应无 `answer_key` | `durable` |
| practice start / submit / finish / result | `practice-session.html`、`practice-result.html` | 会话 `finished`，`summary` 含 `score_total`、`total_item_count`、`scored_count`、`submitted_count` | `durable` |
| 错题与反馈 | `review.html` | 错题 id、状态在合法枚举内、occurrence 的 `source_status` 合法、weak-point 非空 | `durable` |
| 问答线程与 citation | `qa.html`、`material-detail.html` | thread 与 assistant 消息保留，citation `valid` 且 offset 落在正文内 | `durable` |
| 删除 → 恢复 → 删除 → purge 的来源生命周期 | `materials.html`、`material-detail.html` | `valid` → `source_deleted` → `valid` → `source_unavailable`；purge 后 `material_name` 为空、无 `excerpt`、材料 404，但问答历史保留 | `durable` |
| 共享 hash 导入（同内容不同名） | `materials.html` | 两条材料、一份原件、重启后都能下载且内容一致 | `durable` |

本切片没有发现「页面显示成功但重启后消失」的 `NOT_DURABLE` 项。

## 6. 浏览器真实用户路径验证（L2 + L3）

`browser_p1_4_real_input_restart.spec.js`，`3 passed`：

1. **B1-1~B1-4 + B1 重启**：在 `/app/materials.html` 一次导入 PDF + DOCX + PPTX + MD + 中文长名 TXT，显示 `已导入 5/5`，列表出现全部 5 项，中文搜索命中 1 条；进入 `material-detail.html` 看到真实 PDF 正文与片段数量，点击「建立 AI 索引」显示已建立；停服 → 重启 → 重新打开，列表与正文、索引状态仍正确。
2. **B2-2~B2-6 + B2 重启**：真实 PDF 建索引后在 `/app/qa.html` 提问，展开「查看对话与引用」，点击 citation 跳到 `material-detail.html`，正文出现高亮；停服 → 重启 → 直接用同一 citation URL 打开，仍显示「已定位引用来源」，且高亮文本与重启前完全一致。
3. **B1-5**：导入 `.doc` 与 `.rtf` 显示 `已导入 0/2`、warn 样式、列表状态为「已拒绝」。

三条路径都断言页面与 DOM 不出现 traceback、`H:\` 路径、SQL、`api_key` 或 `stored_path`。

## 7. 安全检查

| 检查 | 结果 |
|---|---|
| 路径 / `stored_path` | 材料详情、列表、citation 响应均无 `stored_path`；页面断言无 `H:\` |
| SQL / traceback | 页面与响应断言均无 |
| secret | 加密 PDF 的密码不出现在任何响应中 |
| answer key | 卡片、题目、practice item、practice result 全部断言无 `answer_key` |
| 原始 provider 响应 | 未出现；本切片仅使用 deterministic fake provider |
| 未授权正文 | purge 后 citation 不返回 `excerpt`、不恢复 `material_name` |

## 8. C0 新发现（已写入台账）

| ID | 事实 | 层 | 说明 |
|---|---|---|---|
| P14-P0-05 | 同内容不同名的第二个材料**无法建立索引**：`/api/materials/{id}/ai-index` 与 `/ai-index/tasks` 均返回 `400 revision_fingerprint_conflict`，因此该材料无法参与检索、问答与 citation；`/api/qa/ask` 返回 `409 retrieval_not_ready`。删除第一个材料**不**释放指纹，只有 purge 才释放。 | L2/L3 | 由 `test_shared_hash_second_material_cannot_be_indexed_today` 固定为当前真相。修复涉及 revision 指纹契约，需要独立 migration 与 API 决策，不在 C0 内改动。 |
| P14-P1-03 补充 | `revision_fingerprint_conflict` 不在共享错误映射中，用户只会看到「请求失败，请重试」。 | L2 | 已由测试固定。 |
| P14-P1-04 补充 | 计划学习项响应没有 `source_link_status`/`source_status` 字段；来源状态只存在于 `source_links`。`plans.html` 与 `today.html` 因此在来源已删除时仍显示「来源有效」。 | L2 | 已由 `test_plan_item_source_state_lives_on_source_links_not_items` 固定。 |
| P14-P1-04 补充 | 材料索引状态 `not_indexed` 在 `state.js` 中没有对应文案，`material-detail.html` 回退到通用未知状态措辞。 | L2 | 已由测试固定。 |
| P14-P1-06 补充 | `materials.html` 的 accept 列表包含 `.doc`，但后端固定拒绝；导入失败列表直接展示后端错误码。 | L2 | 已由 browser spec 固定。 |

## 9. 明确的 `not_verified` 边界

本切片不声明以下任何一项：

- 真实 Provider（含超时、密钥失效、断网中途）的问答与生成质量；
- 真实 OCR / ASR 的通用可用性；扫描件 PDF 当前按无文字层处理；
- 真实对外交付（delivery 保持 `off`）；
- Windows ACL / 只读目录、磁盘满、真实断电、网络盘、文件系统损坏；
- 多进程或多 worker 共享 `data_root`；
- 数据规模增长后的性能基线、跨天/跨时区节奏正确性、周趋势可视化；
- 进程强杀（本切片使用正常关闭与重启，不等价于强杀恢复）；
- backup → verify → 恢复到新空目录的完整演练（既有 backup/restore 证据不在本切片重新宣称）。

## 10. 结论

C0 切片完成：真实 PDF/DOCX/PPTX/MD/中文长名 TXT 的完整链路已实测，`/app` 主要写操作族的重启复现已逐族验证，真实拒绝与降级行为已固定为测试。C0 是 `implemented + scoped real-pass`，覆盖范围严格限定为本文件第 2、9 节所述的工具、Provider 与输入类别；不等于全局 real-pass。

### C2 来源与解析可解释性（L2/L3，限定范围）

验证工具与环境：`C:/miniconda/py310/python.exe`、本地 Uvicorn、Playwright Chromium，`STUDYBUDDY_AI_PROVIDER=fake`，隔离 `H:/studybuddy-test/runs/p1-4-c2-explainability` data root。真实路径命令：`npx playwright test backend/tests/browser_p1_4_c2_explainability.spec.js --workers=1 --reporter=line`，结果 `2 passed`。

- **P14-P1-04（L2/L3）**：计划 API 的 `items` 不带来源状态，页面现在从 `source_links` 按 `plan_item_id`/`module_id` 映射；无链接显示“未关联来源”，`source_deleted` 等非 valid 状态显示真实文案并禁用材料入口。真实 Chromium 创建计划→关联 DOCX→页面显示 valid→删除材料→停服重启→页面显示 source_deleted，1 条路径通过。关联历史页面矩阵 `7 passed`；既有 restart durability 事实测试同步为修复后预期。
- **P14-P1-05（L2）**：材料详情显示解析状态、解析器、warning 和下一步。真实 Chromium 生成并上传 image-only PDF、含段落 DOCX、无文字 PPTX，分别验证无文字层 OCR 指引、DOCX 复杂对象 warning、PPTX 空正文转换/重试指引。该验证确认页面提示可读，不证明 OCR 或解析通用准确率。
- **P14-P1-06（L2）**：`materials.html` accept 更新为 `.pdf,.txt,.md,.docx,.pptx`；DOC/PPT/RTF/XML 明确需转换或不支持。真实上传 4 个拒绝样本，页面显示用户文案，不显示 `requires_converter`/`unsupported_rtf`/`unsupported_format` 原始码；后端拒绝 contract 未改变。
- **Focused 结果**：`C:/miniconda/py310/python.exe -m pytest backend/tests/test_p1_4_c2_explainability.py backend/tests/test_p1_4_restart_durability.py::test_plan_item_source_state_lives_on_source_links_not_items -q` 为 `5 passed`；完整后端分组回归在 C2 修复旧事实断言后，已验证分组 `488 passed, 3 skipped`（全量命令因 10 分钟窗口超时，最终全量数字未重宣称）。source-size 与 `audit-frontend-contract.py --strict` 均通过，后者 `0 findings`。
- **安全检查（L2）**：C2 页面和真实 DOM 断言无 `stored_path`、路径、SQL、traceback、`api_key`；导入拒绝列表只渲染 `safeError` 用户文案；没有新增 API、schema、原始 provider 响应或正文泄露路径。

C2 结论：`implemented / scoped browser-pass`，来源状态真实路径达到 L2/L3（含正常重启回读），解析提示与拒绝提示达到 L2；真实 OCR、通用解析准确率、多进程、强杀恢复和新空目录 backup/restore 在本切片为 `not_verified`。

### C3 `/app` 批量导出（L2/L3，P2 可用性补全）

C3 复用既有 `POST /api/materials/export`，未新增或修改 API、schema、响应字段、ZIP 布局、状态码或幂等语义。正式 `/app/materials.html` 新增当前页选择、已选数量，以及“原件 ZIP / 文本 ZIP / 全部 ZIP”三种操作。选择范围只保留当前可见 active 页；筛选、翻页、刷新、上传后刷新和切换回收站都会清空，避免导出不可见材料。无选择和导出中按钮禁用，失败后恢复并允许重试。

验证工具与环境：`C:/miniconda/py310/python.exe`、本地 Uvicorn、Playwright Chromium、隔离 `H:/studybuddy-test/runs/p1-4-c3-batch-export` data root。命令 `npx playwright test backend/tests/browser_p1_4_c3_batch_export.spec.js --workers=1 --reporter=line` 结果 `2 passed`：

1. 从正式 `/app/materials.html` 选择中文 TXT 与 Markdown，分别下载并解压三种 ZIP，核对 entry 路径、中文文件名及正文；筛选后选择清零；正常停服重启后重新选择并再次导出 4 个 entries。该路径建立 L2，并对持久材料的重启后再次导出建立限定 L3 证据。
2. 模拟 `413 export_too_large`，页面显示安全可操作文案，按钮恢复，解除故障后重试成功；删除材料并切到回收站后不显示批量工具栏或 checkbox。DOM 不出现 raw error code、`stored_path`、路径、SQL、traceback 或 `api_key`。

Focused gate：`test_p1_4_c3_batch_export.py`、`test_material_export.py`、`test_api_input_boundaries.py` 和 governance 共 `29 passed`；关联 `/app` browser `13 passed`；C3 重复 browser gate `4 passed`，其中失败路径在同一事件循环双击并断言只发一个请求；source-size、diff check 和 `audit-frontend-contract.py --strict`（0 findings）通过。完整 backend 为 `504 passed, 3 skipped`。最新完整 Chromium 为 `150 passed, 4 skipped, 1 failed`：唯一失败曾是 C3 未修改的 P1-2 计划成功文案被异步“计划已加载”覆盖。后续独立根因修复确认：点击已选计划会发出冗余 detail/rhythm 请求，旧 `selectPlan()` 可晚于 mutation 刷新并覆盖成功反馈。`plans.html` 现对当前计划重复选择 no-op，并以独立 selection/mutation generation 阻止过期选择写状态；确定性延迟响应、P1-2 和 Phase 9A 组合重复门禁为 `35 passed`。修复后的完整 Chromium 为 `152 passed, 4 skipped`，完整 backend 为 `506 passed, 3 skipped`；4/3 个 skip 均为既有 opt-in real smoke。C3 归类为 P2 可用性补全，不再把它描述为当前每日学习链的 P0 阻断。

C3 的 `not_verified` 边界：256 MiB 极限真实 ZIP、200 项上限的性能/内存、磁盘满、下载中浏览器/服务强杀、Windows ACL、网络盘、多 worker、backup→verify→新空目录 restore 均未在本切片验证。下一步进入 C4 时应按 P2-02~P2-06 分别冻结 contract，不把规模、任务列表、source-link、cram 和跨天趋势混成一次改动。

### C4-0 拆分与 C4-1 `/app` cram 冲刺工作流（L2/L3）

C4-0 将原“规模与完整工作流”拆为 C4-1 cram、C4-2 source-link、C4-3 task-list、C4-4 周趋势、C4-5 规模测量和最终 C4-6 backup/restore gate。本文本次只记录 C4-1；没有实施或关闭 C4-2～C4-6。

C4-1 在 `practice.html` 增加冲刺目标创建、列表、详情、`draft -> active -> completed`、归档、ready/valid 题目选择与 session 创建。`practice-session.html` 继续复用既有 start/submit/finish；URL 携带 `cram_goal_id`，`practice-result.html` 因此读取既有 cram result endpoint。普通 session 不携带该参数，继续读取普通 result endpoint。未新增或修改 API、migration、schema、后端状态机或错误码。

页面契约把过去的 `target_date` 表达为派生的“已过目标日期”：历史目标仍可见、可归档，但不提供激活或新建 session；不会写入伪造状态或启动自动排程。选题仅包含 `ready` 且全部 citation 为 `valid` 的题目；无引用的 user-created ready 题仍允许。写操作使用共享 `Idempotency-Key` 与 busy guard；修复了 busy 结束时误启用原本因空题而禁用按钮的问题，失败后恢复原始业务禁用状态。

可复现结果：

```text
npx playwright test backend/tests/browser_p1_4_c4_cram.spec.js --workers=1 --reporter=line --timeout=60000
2 passed

C:/miniconda/py310/python.exe -m pytest backend/tests/test_phase9c_api.py backend/tests/test_phase9c_domain.py backend/tests/test_phase9c_source_lifecycle.py backend/tests/test_phase9c_backup_restore.py -q
21 passed
```

Chromium 第一条从正式 `/app` 创建目标、激活、选择题目、创建 cram session、开始、提交、结束、读取 cram result、完成目标；正常停服重启后从目标列表与 session 列表回读，并再次进入结果页。随后创建普通 practice session，确认结果页仍走普通路径。第二条覆盖已有空题库、API 历史过期目标、真实 material/index/citation 题在 source delete 后从候选中移除、同一事件循环双击只发一个请求、500 安全失败后重试成功。DOM 断言不出现 `answer_key`、`answer_json`、traceback、`stored_path` 或本地路径。

最终回归：完整 backend 为 `506 passed, 3 skipped`；完整 Chromium 为 `154 passed, 4 skipped`。3/4 个 skip 均为既有 opt-in real ASR/Provider smoke。相关组合 Chromium（C4-1、普通 practice、推荐、visual）为 `14 passed`；后端 Phase 9C + contract/governance 组合为 `39 passed`；source-size、`git diff --check` 与前端 contract audit（0 findings）通过。

### C4-2 `/app` source-link 工作区（L2/L3）

C4-2 在 `plans.html` 提供模块/学习项 owner 选择、当前资料 chunk 候选、添加/删除与显式刷新；后端新增公开 DELETE 路由和 identity-only candidates GET，未新增 schema/migration。DELETE 严格校验 project 与 owner scope；归档计划的 item link 删除返回 `409 study_plan_edit_not_allowed`。来源状态仍由服务端计算，soft-delete 后为 `source_deleted`，restore 后只有显式 refresh 才恢复为 `valid`；不返回正文、stored_path 或 SQL。

验证：`test_p1_4_c4_2_source_links.py` `2 passed`；`browser_p1_4_c4_2_source_links.spec.js` 已覆盖正式 `/app` 添加/删除/刷新、来源生命周期、失败安全重试与归档保护。源码大小、`git diff --check` 与前端 contract audit `0 findings` 通过。C4-2 结论为 `implemented / scoped browser-pass`，关闭 P14-P2-03。L3 限定正常停服重启/同一 SQLite data root；backup/restore 专项、强杀、多 worker 与规模仍未验证。

### C4-3 task-list contract（API + `/app` static）

C4-3 冻结并实现 `GET /api/tasks`：仅返回当前 project 的脱敏公共 task rows，支持 `status`、`task_kind`、`operation_type` 筛选，`limit` 默认 25、范围 1–100，`offset >= 0`，按 `created_at,id` 倒序，并返回 `items/total/limit/offset`。无 schema/migration 变更；既有单任务 read/cancel/retry 路径保持不变。`tasks.html` 已从“待实现”提示切换为真实列表、状态筛选、空态、失败提示、刷新和详情入口，并保留原有详情动作。

验证：`test_p1_4_c4_3_task_list.py` `1 passed`；`browser_a4.spec.js` 与 `browser_frontend_system_matrix.spec.js` 组合 `11 passed`；专用真实 success-path `browser_p1_4_c4_3_task_list.spec.js` `1 passed`；frontend contract audit `0 findings`，source-size 与 `git diff --check` 通过。真实导入/索引/排队任务进入 `/app/tasks.html`，状态筛选、空态、详情入口和 DOM 隐私断言均通过。当前结论为 `implemented / scoped browser-pass`；L3 仅限正常停服重启后的 SQLite/data_root 读取，不包含强杀、多 worker 或 backup/restore。C4-4~### C4-6 backup → verify → 新空目录 restore 专项 gate

新增 `backend/tests/test_p1_4_c4_6_backup_restore.py`，使用既有 backup library 验证完整闭环：代表性材料（共享原件 + soft-deleted 材料）、active plan/item、progress event、rhythm settings、queued operation task；执行 `backup_data`、`verify_backup`、`restore_backup(confirm=True)`、`verify_restored_data`，然后在新 data root 进行两次正常启动并读取 `/api/health`、`/api/readiness`、plans、tasks、weekly-trend。验证迁移前后关键快照一致，schema `14` 与 `schema_migrations=14` 保持一致。

结果：C4-6 专项测试 `1 passed`；restore acceptance `passed`。该 gate 仅证明 local single-process/single-instance、SQLite、本地磁盘、正常停服时的 backup/restore 与重启读取；不证明真实断电、强杀中间态、多 worker、网络盘/ACL 或生产级灾备。未自动运行 provider、index、source refresh、repair、排程或提醒。

### C4-4 周趋势 contract（scoped implementation）

新增只读 `GET /api/study/plans/{plan_id}/rhythm/weekly-trend`，复用 `study_progress_events` 与既有 rhythm timezone，不新增 schema/migration，不修改 plan/progress/rhythm 写入语义。响应固定返回请求结束日向前 7 个 local days 的每日 started/completed/skipped/reopened 计数与 totals；事件按配置 IANA timezone 归属，避免按 UTC 日期误分桶。`today.html` 增加近七天完成趋势展示，并沿用现有安全错误/空态处理。

验证：`test_p1_4_c4_4_weekly_trend.py` `1 passed`；既有 Phase 9B rhythm 与 frontend contract 组合 `13 passed`；frontend contract audit `0 findings`，source-size 与 `git diff --check` 通过。专用真实 `/app/today.html` browser fixture `browser_p1_4_c4_4_weekly_trend.spec.js` 已 `1 passed`，覆盖真实计划/进度事件、7 日卡片、失败安全提示与隐私断言；API 专项测试另覆盖 Asia/Shanghai 跨 UTC 日界线归属。当前结论为 `implemented / scoped browser-pass`；L3 仍仅限正常 SQLite 读取，不包含强杀、多 worker 或 backup/restore。### C4-5 资料规模与批量体验测量（已关闭，measurement-only）

新增仅用于本地测量的 `backend/scripts/measure_p1_4_c4_5.py`。脚本创建临时 SQLite data root，生成合成 operation task rows，通过真实 `GET /api/tasks` 测量有界列表读取，不写入仓库、不新增生产 API/schema、不保留数据库或测量产物。初始基线（本机单进程、fake provider、limit=100）为：task-list 10/100/500/1000/2000 rows 分别约 `16.630/27.144/27.236/33.852/33.275 ms`，均遵守最多返回 100 rows。材料导入端到端基线为 10/100/500 个小型 TXT 分别约 `335.380/3563.606/27695.033 ms`，列表仍最多返回 100 rows；该测量包含逐文件 HTTP、解析和 SQLite 写入，不等同纯导入函数耗时。结果不是容量承诺，也不是多 worker/生产规模结论。基于当前有界证据，不新增产品 API、失败重试队列、批量进度页或新的筛选/排序能力；后续只有在真实使用观察证明摩擦阈值被触发时才另立 contract。专用 browser measurement `browser_p1_4_c4_5_measurement.spec.js` 已 `1 passed`：真实 `/app/materials.html` 20 行渲染约 `276 ms`，`/app/tasks.html` 列表渲染约 `106 ms`；失败刷新安全展示通过。真实 queued task 在观察窗口内可能快速完成，因此取消仅记录为“完成先于取消观察”，不把取消耗时伪造为成功指标。重复点击的功能性防抖仍由 C4-1/C4-2 专项覆盖。C4-5 关闭 P14-P2-06，取消未形成成功耗时指标，不能解释为取消性能已验证。

C4-1 结论为 `implemented / scoped browser-pass`，关闭 P14-P2-04。L3 仅指同一 local single-process、SQLite、本地磁盘 data root 上正常停服重启后的目标/session/result 回读；强杀、断电、多 worker、跨时区日期显示、backup→verify→新空目录 restore、自动提醒/选题和真实规模仍为 `not_verified`，并分别留给后续切片或明确 non-goal。

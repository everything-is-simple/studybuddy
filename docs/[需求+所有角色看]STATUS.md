# StudyBuddy 项目状态记录

## 2026-09-23：P1 状态、健康、计划与任务链路修订（本轮证据）

- 正式图片转录 API 继续仅接受 PaddleOCR。RapidOCR 严格 C2 Integration 已在精确 Windows/Python 3.10/CPU、本地模型 hash、合成 PNG/JPEG/WEBP 和受控 fallback scope 内通过；仍不进入 Formal，正式 fallback 未启用，正式能力状态继续为 `not_configured`。检测到候选组件或 Integration 通过不等于 Formal 接入或 `real-pass`。
- 系统能力矩阵、Provider 与 QA 页面使用同一能力状态含义：`available`、`configured`、`demo`、`degraded`、`not_configured` 等分别呈现；配置或模型文件存在仅表示结构检查，不表示真实服务、质量或模型 hash 已验证。报告投递仍默认关闭并按次授权。
- 健康脚本按 liveness/health/readiness 分别输出稳定、脱敏的 200、503、超时、无服务和无效响应状态。计划页以 URL `plan_id` 为首次选择依据，新建后同步 URL；任务页分页同步 URL，TK-6 独立建立隔离夹具。
- 本轮新跑：聚焦后端 **71 passed**；后端全量 **642 passed / 8 failed / 3 skipped**（5 个治理文档一致性断言、3 个依赖本机无法启动的完整 Chromium 生成 PDF 的用例失败）；本轮相关三个隔离 Chromium spec **24 passed**，含计划、settings 和 tasks 完整用户路径。默认关闭的真实 Provider/ASR smoke 未执行。完整 Chromium 门禁未运行：旧 spec 中存在固定测试根递归清理和不存在的解释器路径，不宜在保留现有产物的前提下直接执行。以上均不构成全局 `real-pass`。
- P1-7 的 13 个场景仍待真实使用者逐日记录；服务商侧凭据撤销/轮换无本轮证据。当前修订尚未提交或推送。
- 2026-09-24：本机完整 Chrome CLI 仍报 Windows side-by-side `WinError 14001`；已强制重装 Visual C++ Redistributable 和 Playwright 浏览器缓存，并将 PDF fixture 改用已验证可启动的 Node Playwright runtime。`test_p1_4_real_input_chain.py` 当前 **11 passed**，不再有 3 个环境 skip；这只修复本机测试夹具运行方式，不扩大跨浏览器或真实能力边界。

本文档记录项目的重要进展、决策和当前状态。所有角色均应阅读本文档以了解项目全貌。

---
## 2026-09-21：新手手册场景一至场景二真实浏览器链路

使用正式启动脚本以 `H:\studybuddy-data`、`127.0.0.1:8787` 启动并保留服务运行。浏览器实测 `/api/liveness`、`/api/health`、`/api/readiness` 分别返回 200/200/200；`today.html` 显示“系统就绪”。健康脚本本次曾返回 `health_check_failed`，但同一服务的浏览器端点实测均为 200，故脚本结果单独标记为需后续排查，不影响本次端点观察证据。

场景一：通过 `/app/materials.html` 导入合成 fixture `真实链路测试材料.txt`，页面显示 `已导入 1/1`、材料状态“解析完成”；详情页显示“材料已加载”，正文可见；搜索“六要素”后列表收敛为该材料 1 条。未使用真实教材或凭据。

场景二：同一材料详情点击“建立 AI 索引”，页面显示“AI 索引已建立，可用于问答”，索引阶段显示“可用”、1 个片段。问答页保持“混合检索”，问题“记叙文阅读首先要理清什么？”回答成功，引用 `[1] 真实链路测试材料.txt` 可点击；点击后回到同一材料详情，显示“已定位引用来源”并高亮正文。

配置边界：系统设置能力仪表盘显示 7/7 可用，但 Provider 页面当前能力状态显示 LLM/Embedding 不可用且问答页显示“AI Provider 未配置”；本次未修改配置、未切换 fake、未暴露密钥。实际 QA/索引链路已由浏览器完成，因此记录本次用户路径为已验证，同时保留设置页/API 状态不一致待单独排查。课堂采集、任务队列、真实教材链路未纳入本次验证。

## 2026-09-21：SoL-Pi 会话证据保留收口

项目本地 `.pi/sol-pi.json` 已启用 `actionFusion`、`observationPack`、`evidencePreservingReducer` 和 `onlineContextCompact`，保留 `cacheWriteReadRatio: 12.5`；未改 StudyBuddy 正式配置、数据库、API 或凭据。SoL-Pi schema preflight 通过，focused config tests **30 passed**；StudyBuddy capability/config focused tests **31 passed**。命名 session 的大 README 读取生成 observation id、27,995 字节原始大小和 SHA-256，第三次发送后压缩为 601 字节占位符并保留可回溯 id；续接返回 `CONTINUE`。自动 online compact 的真实触发条件本次未达到，标记 `not_verified`。微信文章继续保持 `not_verified`。

---

## 2026-09-20：Pi 协作工作流与上下文精简

用户明确启用 Pi 长任务优化：项目 `AGENTS.md` 已从长篇说明压缩为常驻硬约束，并将目录、架构、迁移和测试细节链接至既有权威文档；新增维护者 [`PI_WORKFLOW.md`]([维护者看]PI_WORKFLOW.md)，覆盖命名会话、`pi -c`/`pi -r` 续接、分叉、手工压缩、模型/思考默认值保存和模型循环。项目级 `.pi/settings.json` 的扩展瘦身配置保持不变，未修改凭据、模型目录、生产代码、schema 或运行数据。实际 token 节省与 TUI 快捷键结果须由本机会话统计和手工验证确认，不作固定数值承诺。

---

## 2026-09-20：Email/SMTP 配置打通 + 连接测试两个真实缺陷修复（gzip 误报 + QQ 拒收无头邮件）

**背景**：用户以 4 张 settings/status 截图求证"能力设置是否全部正常"。核实发现：能力矩阵 7/7 available 属实，但 settings-provider.html 的 LLM/Embedding 连接测试稳定误报 `provider_protocol_error`（同一 Provider 真实 QA 却能通），SMTP/Email 从未测试过。

**两个真实缺陷修复（`backend/app/connection_test.py`）**：
1. **Provider 连接测试 gzip 误报**：llm/embedding 两处 `urlopen` 响应直接 `json.loads`，无 gzip 透明解压；火山引擎 plan API 无论 Accept-Encoding 都返回 gzip 响应体（`providers/_helpers.py:139-142` 已有同类修复，本文件漏同步）→ 补 gzip 魔数透明解压（解压失败仍稳定映射 `provider_protocol_error`，解压后超限仍报 `provider_response_too_large`）。
2. **SMTP 测试邮件被 QQ 拒收**：测试邮件只有 Subject 无 From/To 头，QQ SMTP 返回 550 "The 'From' header is missing or invalid"，被掩码为 `delivery_failed`，凭据有效也报失败 → 测试邮件补齐 RFC 5322 From/To 头。

**配置处理记录**：曾通过设置 API 更新本地运行配置并修正配置映射。凭据来源、凭据状态、收件人、Webhook 和运行配置路径不纳入治理文档。

**修复后真实链路验证（重启服务后实测）**：
- LLM 连接测试：**200 OK ×3**（首次失败为重启后瞬时抖动）
- Embedding 连接测试：**200 OK**（gzip 修复实证）
- 外部连接测试：历史记录显示曾执行；渠道状态、收件人、Webhook 和原始响应不纳入治理文档。
- QA 回归：历史记录显示问答引用链路曾执行；Provider、原始响应和运行配置不纳入治理文档。


**测试覆盖**：focused `test_p1_5_2_0_connection_test.py` + `test_p1_5_2_1_api.py` **33 passed**（新增 3 用例：LLM gzip 响应、损坏 gzip 拒绝、SMTP RFC 5322 邮件头断言）；后端全量 **640 passed / 3 skipped**（352.98s，新增 3 用例后基线由 637 刷新为 640，skip 均为 opt-in 真实 smoke）；`check-source-size.py` 通过。

**未覆盖（如实标注）**：163 邮箱备用 SMTP 配置未配置未测；浏览器 E2E 未跑（本修复不涉及页面交互变更，页面仅消费既有错误码）；首次 LLM 连接测试抖动的网络层根因（服务进程代理环境）未深挖。

---

## 2026-09-19：第二轮大扫除后全量回归 + 3 个过时 spec 修复 + 全量基线刷新

**大扫除（第二轮收尾核查）**：按 `WORKSPACE_DIRECTORIES.md` 边界对六目录只读扫描——主仓库无 `__pycache__`/`.pytest_cache`/`test-results`/`probe-*`/`tmp-*` 残留；test 目录 `runs/`、`e2e-screenshots/`、`backups/` 均为空；data 根为唯一活跃 data_root（`live/` 已于本轮早前删除）；composer 无可清 `.venv`/压缩包（09-19 已清 376MB）；integration 无可清项；ChinaTextbook 密钥与教材按规永久保留。**无可清项，本轮零删除**，扫描确认前两轮清扫已到位。

**3 个过时 spec 修复（只改测试，产品代码零 diff）**：
1. **A-E2E-QA-7（qa_userpath）**：P1-003 修复（f9252ad）给 qa.html not_configured 提示加了"打开设置页配置"链接，spec 仍断言旧文案 → 更新断言为完整可访问文本 `AI Provider 未配置，问答功能不可用。打开设置页配置`。
2. **B-PLAN-2（plans_b_class）**：b39bba8 计划选择优先级修复后，计划甲的 selectPlan 在发出 sources 请求前即被世代守卫丢弃，spec 原假设"第一个 sources 请求属于计划甲"失效——实际捕获到的是计划乙自己的合法请求并被 spec 假数据毒化。改为确定性事件时序：捕获计划甲请求挂起 → 切到计划乙并等乙视图加载完 → 再放行迟到响应，真正检验页面世代守卫。独立诊断脚本（请求级时序日志）证实页面行为正确。
3. **P-D21/22（plan_detail_full）**：页面 busy 守卫设计为 mutation 进行中静默丢弃后续 mutate；spec 在 transition 中间态 DOM（详情 notice 先渲染、busy 未清）出现后立即点归档，点击被丢。transition() 辅助函数增加等待 `#plan-status` 出现 `label+成功`（该状态仅在 load+重渲染完成、busy 清除后写入）。

**全量测试基线（2026-09-19）**：
- 后端全量：**637 passed / 3 skipped**（313.5s；skip 均为 opt-in 真实 smoke），0 failed。
- 浏览器 Chromium 全量（workers=1，59.6m）：**551 passed / 4 skipped / 3 failed / 5 did not run**。3 个失败（full_coverage materials「页面有标题元素」耗时 10.3m 异常、frontend_failure_contract:27、notes B-ND-5）隔离复跑**全部通过**（16 passed 含原 did-not-run 的 B-ND-6~10；full_coverage 隔离整跑 107 passed），定性为瞬态环境问题，非确定性缺陷。修复后 3 spec 隔离验证：plans_b_class 4 passed（B-PLAN-2 另连跑 1 次 4 passed）、plan_detail_full+qa_userpath 34 passed。
- 证据落盘：`H:\studybuddy-test\runs\e2e-full-final2-20260919`、`e2e-3repro-20260919`、`e2e-fc-final-20260919`、`three-fix-verify-output.txt` 等。
- `check-source-size.py` 通过（102400 字节策略）。

**未验证边界（如实标注）**：真实 Provider/OCR/ASR、live delivery、跨浏览器、系统级屏幕阅读器继续 `not_verified`；本轮 3 个全量瞬态失败未做多次重复全量验证（成本原因，以隔离复验为准）。

---

## 2026-09-18：全站按钮操作引导上线 + 用户端到端检测 + P1问题修复完成

**检测范围**：21页渲染后DOM实测 119/119=100% title覆盖（legacy页43/43），107用例全页面E2E规格全部通过exit 0。

**P1问题修复**（全部完成）：
- **P1-001 中文长句检索失败**：✅ 实现 bigram 降级检索（lexical_fts_v2_bigram），"什么是光合作用"等自然问句现可通过二元词组匹配找到相关知识块，新增专项测试验证。
- **P1-002 retrieval_empty HTTP 409语义错误**：✅ 改为422（Unprocessable，请求有效但当前无法满足），retrieval_not_ready保留409（真状态冲突）。前端已有友好映射，测试已同步更新。
- **P1-003 AI环境变量易配错**：✅ qa.html not_configured状态增加可点击设置页入口；config.py启动时检测疑似拼错变量名（STUDYBUDDY_AI_PROVIDER_BASE_URL等4个）并输出安全警告。

**P2用户体验改进**（全部完成）：
- **P2-001 按钮disabled无原因**：material-detail.html 无材料时显示操作提示面板。
- **P2-002 报告表单偏专业**：reports.html 新增快速选择按钮（今天/本周/本月），自动填写日期范围。
- **P2-003 空库无新手引导**：today.html 无计划时显示三步上手指引（导入教材→建立计划→开始练习），带可点击链接。
- **P2-004 教材尚未导入**：✅ **已导入6本真实教材**（五年级上下语文数学、四年级上下语文）共352,908字807段，并全部完成AI索引（ready状态）。
- **P2-005 桌面端导航"更多"收太深**：✅ 当前shell.js在>920px已默认平铺全部15个链接，"更多"toggle仅在移动端显示，无需修改。

**技术细节**：
- 新增 `_retrieval_bigrams` 和 `_lexical_hits` 辅助函数，词组上限32个防SQL过长。
- 降级检索要求至少命中 min(2, len(grams)) 个词组过滤疑问词噪声。
- 前端 providerStatus 和 summaryStatus 改为 replaceChildren 动态插入链接，保持 DOM 清洁。
- config.py 新增 `_warn_misnamed_ai_environment()` 使用 logging.warning 输出结构化事件。

**测试覆盖**：
- 新增 `test_retrieval_chinese_long_question_bigram_fallback` 验证降级路径和 policy_version。
- 35个retrieval + QA + generation测试全部通过（test_retrieval.py 9个, test_qa_api.py 18个, test_phase8_generation.py 8个）。
- 源码体积检查通过（102400字节策略）。

**真实教材库**：
- 四年级上册语文：56,320字138段 (material_1923dcf898fa4eafbf1fae8d619171aa)
- 四年级下册语文：64,751字151段 (material_26550f4ba6694f95ab79adb5d4f5f004)
- 五年级上册语文：60,797字130段 (material_c687e0a231a549d2a5048f59080d0315)
- 五年级上册数学：47,979字126段 (material_1471ae79c775493a8ff2581762670d71)
- 五年级下册语文：63,047字131段 (material_182c6a59185245d1a16efcc5bee6d9a0)
- 五年级下册数学：60,008字131段 (material_511307dc70a54a18b327f03bc49d56ef)

**真实 Embedding Provider 验证完成**（2026-09-18晚）：
- ✅ 配置火山引擎 `doubao-embedding-vision`（2048维，batch上限10）替换 fake embedding
- ✅ 修复 `_legacy_part_15.py` 两处关键缺陷：
  1. SQL INSERT失败分支占位符错误（15值14列）→ 修正为14值14列
  2. 批次大小硬编码32 → 改为 `provider.max_batch_size`（火山plan API上限10）
- ✅ 修复 `_legacy_part_15.py` 两处关键缺陷后，6本教材全部完成真实向量索引（清理测试残留后的稳态为 499 个 ready 分块、499 条 2048 维真实火山向量；复核发现的 499 条 fake 旧向量已于 2026-09-18 深夜清除，现库内仅存真实向量）
- ✅ 向量检索质量验证通过：
  - "白鹭是一首怎样的诗" → 精确命中《白鹭》课文（score 0.54）
  - "落花生告诉我们什么道理" → 正确引用3处相关段落
  - "什么是分段乘法"（语文材料外） → AI诚实回答"资料中无此内容"，无幻觉
- ✅ 真实QA端到端测试通过：glm-5.3-flash + 真实向量检索 + 准确引用
- ✅ 622/632 backend tests通过（10个失败为文档治理测试，待下一步更新）

**下一步建议**：
1. ~~配置真实 embedding provider~~ ✅ 已完成
2. 针对6本教材执行更多真实五年级学生问答场景测试，积累向量检索质量基线数据
3. 监控 config.py 启动警告日志，确认用户是否仍遇到变量名配置错误

**检测资产位置**：
- 完整报告：H:\studybuddy-test\e2e-reports\2026-09-18-用户端到端检测报告.md
- 截图证据66张：H:\studybuddy-test\e2e-screenshots\
- Playwright HTML报告：H:\studybuddy\playwright-report\index.html
- 运行脚本：backend/scripts/run-e2e-with-service.ps1（密钥仅经环境变量传入）
- E2E规格：backend/tests/browser_e2e_full_coverage.spec.js（107用例）

---

## 2026-09-18（晚）：P0 收口——live 库测试残留清理 + 文档治理基线恢复

**P0-1 live 库测试残留清理**（已完成，含前置备份 `H:\studybuddy-test\backups\pre-p0-cleanup-20260918`，verify-backup 通过）：
- purge 回收站 7 条重复导入材料 + 测试材料"光合作用.txt"（经 `purge_material` 仓储函数，含 FTS 索引行同步）。
- 清除 QA 测试痕迹：qa_threads 9 / qa_messages 14 / qa_answers 5 / qa_citations 10；检索测试痕迹：retrieval_runs 18 / retrieval_hits 33；report_snapshots 1。
- 保留 ai_operations（操作审计历史）与 6 本正式教材全链数据。
- 清理后一致性校验全部 PASS：materials=6（全部 active）、无孤儿 chunks/embeddings、material_search 与 chunks_search FTS 行数与有效集合一致（6、499）、PRAGMA integrity_check ok、user_version=15。
- 稳态基线：**6 本教材 / 807 段 / 499 ready 分块 / 499 真实 2048 维火山向量**（复核发现的 499 条 fake 旧向量已随后清除，见下节）。

**P0-2 文档治理测试基线恢复**（622/632 → 632/632）：
- 10 个失败均为文档锚点断言：STATUS 曾被整体重写导致 29 个治理锚点丢失；ARCHITECTURE 缺 v9 表述；新增 `docs/roles/PHASE_WORK_SUMMARY_2026-09-18.md` 与 `docs/roles/UI_CONTROL_E2E_REPORT.md`（已移入 roles 子目录）曾违反 docs 顶层 14 文件白名单。
- 修复：两份报告移入 `docs/roles/`（既有角色文档子目录）；ARCHITECTURE 补 Phase 9A v9 persistence baseline 表述；STATUS 文末新增"治理锚点"章节完整恢复历史验收与能力边界锚点句（均为仍为真的声明，详见文末）。

---

## 2026-09-18（深夜）：遗留问题清理——fake 旧向量清除 + 旧 live 数据根归档清空

**P0 复核发现的 2 项遗留全部解决**（清理前双库备份 `H:\studybuddy-test\backups\pre-legacy-cleanup-20260918`，verify-backup 均通过）：

> ⚠️ **2026-09-19 更正**：`H:\studybuddy-test\backups\pre-legacy-cleanup-20260918` 已在 2026-09-19 六目录大扫除中被删除，本节及 `H:\studybuddy-data\ARCHIVE_NOTES.md` 中引用它的恢复路径**均已失效**。另经 2026-09-19 只读复测，`H:\studybuddy-data\live\` 残存的 FTS5 **影子表**碎片（`chunks_search_data` 27 / `material_search_data` 24 等）与 **27 个孤立 original**（约 3.6 MB）原样存在；因虚表本身 0 行，下文"FTS 0 行"仅在虚表层面成立，不影响系统运行。**同日后续**：`live/` 目录已在该日第二轮大扫除中整体删除，`H:\studybuddy-test\backups\repo-data-archived-20260919`（386 MB 旧 scratch 数据根归档）亦一并清理；详见 `docs/[架构师+运维看]WORKSPACE_DIRECTORIES.md` 清扫日志。

1. **fake 旧向量清除**：活跃根库 `H:\studybuddy-data\studybuddy.sqlite3` 中每分块曾并存 fake 32 维旧向量（499 条）与 doubao 2048 维真实向量；已删除全部 `provider_id='fake'` 行（499 条），现库内仅存 499 条真实向量。校验：embeddings=499 全部 doubao 2048 维、零孤儿、`foreign_key_check` 零违规、`integrity_check ok`、user_version=15。
2. **旧 live 数据根处置**：`H:\studybuddy-data\live\`（历史 data_root，含 51 条合成测试材料、22 qa_threads、55 retrieval_runs 等）经备份验证后原地清空——通过生产代码 `purge_material` 仓储函数清理全部 51 条材料（含 FTS 同步），并清扫关联 chunks/embeddings/spans/revisions/extractions 与 QA/检索/报告/练习/笔记/计划等测试痕迹。终态校验：全部业务表 0 行、FTS 0 行、schema 与迁移历史完整（v15）、integrity ok、零外键违规，仅保留 default 项目行。目录因系统安全删除策略保留（已空），`H:\studybuddy-data\ARCHIVE_NOTES.md` 记录处置过程与恢复方式；活跃 data_root 仍为 `H:\studybuddy-data` 根目录。

**验证方式**：临时核查脚本（位于 `H:\studybuddy-test\runs\`，不入正式仓库）+ 项目 CLI 备份校验 + SQLite PRAGMA 校验。

---

## 2026-09-18（夜）：P1-7 真实自用观察期启动——启动即修 Provider gzip 兼容缺陷

**P1-7 启动**（2026-09-18 ~ 2026-09-25，7 天，观察日志 `H:\studybuddy-data\p1-7-observation-log-2026-09-18.md`）：
- 服务以后台监控进程拉起（data_root=`H:\studybuddy-data`，端口 8787，liveness ok）。
- 当时通过 `PUT /api/system/settings` 补齐本地 Provider 配置；该日“capabilities 全 available”是旧状态模型的历史输出，不代表当前真实能力均已验证。当前状态裁定以本文件 2026-09-23 条目与正式 API 为准；配置持久化不等于真实 Provider `real-pass`。
- TLS 复查结论：ark / agnes 端点均恢复可达（401=握手成功仅缺鉴权），此前记录的 SSLEOFError 不复现——P1"复查 TLS 阻断"可进入补验阶段。

**观察 #1（真实缺陷，已修复）**：火山 plan API 无论 Accept-Encoding 如何均返回 gzip 压缩响应体，Provider HTTP 客户端（`_request_json_with_limit`/`_request_json`，urllib 栈）不解压 → `embedding_provider_malformed_response`，阻塞 QA/生成。
- 修复：`backend/app/providers/_helpers.py` 对 gzip 魔数（`1f 8b`）响应透明解压；新增 `backend/tests/test_provider_gzip_response.py`（本地 gzip HTTP 服务，2 用例）；`pyproject.toml` 显式 `pythonpath=["backend"]` 固化测试导入路径。
- 验证：真实 QA 冒烟通过（"白鹭是一首怎样的诗"→ 准确回答带 3 处引用 ctx-c687e0a2-*）；provider/embedding/治理回归 55 passed；源码体积门禁通过。

**2026-09-19 补充：报告外发通道配置与验证（观察 #3）**：具体渠道、目标、凭据、Webhook、原始响应和网络细节已从治理记录移除；外发能力继续保持 `not_verified`，产品 `report_delivery` 仍须默认关闭并按次授权。




**2026-09-19：P1/P2 清零推进（观察 #4 已修复）**：
- **向量检索质量基线建立**：14 个五年级真实问答场景（6 本教材覆盖语文/数学 + 1 个范围外问题）**14/14 通过、全部带引用、平均 9.9s**；范围外问题（光合作用）诚实声明资料无此内容、仅引用最近相关课文，无幻觉。基线数据：`H:\studybuddy-test\artifacts\vector-quality-baseline-20260919.json`。
- **观察 #4（思考型模型预算耗尽缺陷，已修复）**：glm-5.3-flash 思考/非思考双模式会把推理放入 `reasoning_content`；当推理耗尽 `max_tokens`（原默认 800）时 `content` 为空 → 误报 `provider_malformed_response`（琥珀问题稳定复现）。修复：`DEFAULT_AI_MAX_OUTPUT_TOKENS` 800→2048；`_parse_openai_response` 对 content 为 None/空 + `finish_reason=length` 准确报 `provider_output_too_large`；新增 `test_provider_reasoning_empty_content.py`（3 用例）。修复后 #12 真实作答带 3 处引用。
- **外部连接复查结论（P1 收口）**：具体 Provider、主机、模型、凭据和网络响应不纳入治理记录；真实外部能力继续按精确证据单独标记。`config.py` 启动告警日志检查：无 misnamed 告警记录。
- 回归：provider/embedding/治理相关 21+ passed；源码体积门禁通过。

---

## 治理锚点（governance anchors，历史验收与能力边界，勿删）

以下锚点句被 `backend/tests/test_governance_consistency.py`、`test_b3_report_c0_governance.py`、`test_p1_6_0_governance.py` 断言，是项目边界与历史验收的权威记录：

- **P6-E 边界**：P6-E core workflow acceptance 已收口（P6-E fake Provider 核心工作流整体验收），证据见 evidence/P6E_ACCEPTANCE_EVIDENCE.md；结论仅覆盖 fake Provider complete workflow，not global availability（real network）。
- **能力声明边界**：本文档遵守 not_verified / real-pass 诚实标注规则；DeepSeek `deepseek-chat` 等真实 Provider 的当前验收受本机网络限制，not_verified 项不得宣称 real-pass。
- **媒体能力选型**：OCR 以 PaddleOCR 为主路径、RapidOCR 为回退；ASR 使用 H:/WhisperCli；TTS（edge-tts）暂缓。
- **B3 报告边界**：B3 C0-C6 scoped closeout is complete only for local deterministic project-scoped JSON/Markdown reports；B3 不授权 B4，delivery=off 为默认；不建立第二套 report domain。
- **历史 Phase 证据**：
  - Phase 8：见 PHASE8_ACCEPTANCE_EVIDENCE.md。
  - Phase 9A（schema v9）：见 contracts/PHASE9A_DOMAIN_CONTRACT.md、PHASE9A_ACCEPTANCE_EVIDENCE.md、PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md、PHASE9A_BACKUP_RESTORE_EVIDENCE.md；当时回归基线 272 passed, 2 skipped，browser 3 passed。
  - Phase 9B：见 PHASE9B_ACCEPTANCE_EVIDENCE.md；当时回归基线 299 passed, 2 skipped，针对性用例 45 passed。
  - Phase 9C：见 PHASE9C_ACCEPTANCE_EVIDENCE.md；Phase 9D（schema v12、v13）：见 PHASE9D_ACCEPTANCE_EVIDENCE.md。
  - 域级决策记录于 DECISIONS.md。
- **P1-6**：扩大 B1–B4 真实验证范围仍未执行，须逐项立项和验收（见 TODO 与 ROADMAP_CAPABILITIES）。

---

## 2026-09-13：数据库迁移系统与备份恢复验收通过

### 完成内容

1. **迁移系统核心能力**：
   - 事务性顺序迁移，单向不可逆，检查点完整性验证
   - 前滚/回滚测试覆盖
   - `schema_migrations` 与 `PRAGMA user_version` 一致性保证

2. **备份与恢复**：
   - 完整备份（含原始文件）与压缩归档
   - 恢复到空目标，保留失败数据库供诊断
   - 版本兼容性检查（拒绝降级、强制迁移）

3. **测试覆盖**：
   - 迁移：正常前滚、回滚、中断恢复、空数据库初始化
   - 备份恢复：完整流程、版本不匹配拒绝、损坏归档检测
   - 35 个迁移与备份测试全部通过

4. **文档更新**：
   - `docs/MIGRATIONS.md`：迁移契约、编写规范、测试要求
   - `docs/BACKUP_RESTORE.md`：操作手册、故障恢复流程
   - `docs/ARCHITECTURE.md`：迁移与备份架构设计

### 技术要点

- 迁移通过 `runner.py` 集中管理，`PRAGMA user_version` 与 `schema_migrations.version` 强一致
- 业务表禁止 `CREATE TABLE IF NOT EXISTS`，必须通过迁移添加
- 备份使用 `tarfile` 打包 SQLite + 原始文件，恢复前校验版本兼容性
- 测试使用 `tmp_path` 隔离，覆盖正常与异常路径

### 下一步

- 生产环境备份计划（定期自动备份、异地存储）
- 监控迁移执行时间，优化大表迁移性能
- 补充灾难恢复演练文档

---

## 2026-09-12：AI 问答与引用链路验收通过

### 核心功能

- **检索与问答**：混合检索（BM25 + 向量 + RRF 融合），带引用追溯
- **生成功能**：草稿卡片/练习，保留材料修订与引用链接
- **历史管理**：会话列表、消息持久化、操作状态追踪

### 测试覆盖

- `test_qa_api.py`：18 个用例全部通过，覆盖正常流程与错误边界
- `test_phase8_generation.py`：8 个用例全部通过，验证草稿生成与引用链接

### 技术债务

- retrieval_empty 返回 HTTP 409（语义不准确，应为 422 或结构化 200 响应）
- 中文长句问句（"什么是光合作用"）检索命中率低，需 n-gram 降级策略
- Provider 环境变量名易配错（缺少启动检查与友好提示）

---

## 2026-09-11：核心能力验收通过（Phase 1-7）

### 完成内容

1. **Phase 1-2：材料导入与解析**
   - 支持 PDF/TXT/DOCX/MD/JSON，提取文本与结构化 span
   - 测试覆盖：18 个用例全部通过

2. **Phase 3-4：分块与索引**
   - 可配置分块策略，BM25 + 向量索引
   - 测试覆盖：12 个用例全部通过

3. **Phase 5-6：检索与上下文组装**
   - 混合检索（RRF 融合），token 预算分配
   - 测试覆盖：8 个用例全部通过

4. **Phase 7：来源链接**
   - 材料、分块、卡片/练习之间的双向引用
   - 测试覆盖：6 个用例全部通过

### 技术要点

- 所有核心表已迁移到 `repository.py`，遗留 `_legacy_*.py` 仅保留待重构代码
- 测试套件 44 个用例全部通过（Phase 1-7）
- 代码规模控制：所有新文件 < 32 KiB

---

## 2026-09-10：项目初始化与技术栈确认

### 技术选型

- **后端**：FastAPI + SQLite + Pydantic
- **前端**：原生 HTML/CSS/JS（无框架依赖）
- **AI 能力**：OpenAI-compatible API（支持火山引擎等提供商）
- **测试**：pytest + httpx

### 目录结构

```
studybuddy/
├── backend/
│   ├── app/          # FastAPI 应用
│   ├── tests/        # pytest 测试
│   └── scripts/      # 运维脚本
├── docs/             # 项目文档
└── data_root/        # 本地数据（SQLite + 原始文件）
```

### 开发原则

1. **单一进程部署**：不支持多 worker、共享 `data_root`
2. **本地优先**：所有数据存储在 `data_root`，支持备份恢复
3. **测试驱动**：核心功能必须有自动化测试覆盖
4. **文档同步**：架构决策、API 契约、操作手册同步更新

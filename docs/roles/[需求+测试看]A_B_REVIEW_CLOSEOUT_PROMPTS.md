# 21 页 A/B 审查收尾 · Prompt 包（定稿 v2 · 3 份）

> 用途：把「21 个正式页面的 A/B 审查」主线收口。本文档只收录收尾所需 prompt，每条自包含、可直接投喂（GLM 做实现/一审，GPT 做独立二审）。
> 状态五级：`implemented` / `tested` / `e2e-real-pass` / `not_verified` / `blocked`。只有 A 类纯用户路径全部通过且独立二审通过，页面才能标 `e2e-real-pass`；`e2e-real-pass` 一律指限定范围（本地单进程 / SQLite / Chromium / 确定性 fake Provider）。
> 定稿日期：2026-09-15。基线 commit：`8ad2d4a`（capture/classroom A/B 二审收口）。
>
> **v2 说明（取代本文件早先的 4 份版）**：4 份版 Prompt 2 的前提「完整 Chromium 串行从未取得可审计退出汇总」已失效——09-14 capture/classroom 轮已取得完整汇总 **425 passed / 4 skipped / 1 failed（430 tests）**，唯一失败为 settings B-SET-5 既有偶发（两次隔离复跑 17 passed）。剩余真实缺口只有：① B-SET-5 根因未修；② index.html 从未按七维度审查；③ tasks.html 双标签并存、升级判据未定；④ 收尾改动落在代码后，需在最终 HEAD 上重新取得一次完整汇总作为收口基线；⑤ 21 页权威总表与主线关闭需要独立复核。据此合并为 3 份：**尾项收口 → 最终统一验收 → 独立复核结项**。

---

## 0. 收尾基线：21 页现状盘点

| # | 页面 | 当前状态 | 依据 |
|---|---|---|---|
| 1 | today.html | `e2e-real-pass` | 09-10 二审（A 类 7） |
| 2 | qa.html | `e2e-real-pass` | 09-10 二审（A 类 9） |
| 3 | practice.html | `e2e-real-pass` | 09-10 二审（A 类 7） |
| 4 | practice-session.html | `e2e-real-pass` | 09-10 二审 |
| 5 | practice-result.html | `e2e-real-pass` | 09-10 exercises/practice-result 二审 |
| 6 | exercises.html | `e2e-real-pass` | 09-10 同上 |
| 7 | notes.html | `e2e-real-pass` | 09-11 A + B 审 |
| 8 | note-detail.html | `e2e-real-pass` | 09-11 A + B 审 |
| 9 | cards.html | `e2e-real-pass` | cards A/B 二轮收口（f95c9de） |
| 10 | materials.html | `e2e-real-pass` | 09-13 materials/plans B 审 |
| 11 | material-detail.html | `e2e-real-pass` | 09-13 同上 |
| 12 | plans.html | `e2e-real-pass` | 09-13 同上（URL plan_id 怪癖已修 b39bba8） |
| 13 | plan-detail.html | `e2e-real-pass` | 09-13 同上 |
| 14 | reports.html | `e2e-real-pass` | 09-12 A + B 审 |
| 15 | review.html | `e2e-real-pass` | 09-13 A + B 审 |
| 16 | settings.html | `e2e-real-pass` | 09-13 A + B 审 |
| 17 | settings-provider.html | `e2e-real-pass` | 09-13 A + B 审 |
| 18 | capture.html | `e2e-real-pass` | 09-14 A + B 审 |
| 19 | classroom.html | `e2e-real-pass` | 09-14 A + B 审 |
| 20 | **tasks.html** | **`scoped browser-pass`（A/B 已审，待升级；文档存在与 `not_verified` 并存的双标签矛盾）** | 09-13 A 类 7 + B 类 7 已过；当轮完整 Chromium 374 项在第 298 项超工具窗口未取得汇总；09-14 轮已取得 425/4/1（唯一失败为非 tasks 的 B-SET-5） |
| 21 | **index.html** | **未审（510 B 兼容跳转页，从未做七维度审查）** | 仅被入口统一测试（browser_migration.spec.js）顺带覆盖 |

注：STATUS/TODO 头部写「21 个正式页面全部完成 A/B 二审」，该口径是宽松的——index.html 实际从未做过七维度审查，tasks.html 的「完成」卡在状态标签未定。**本表是准确口径，收尾以此为准。**

### 收尾缺口（= 3 份 prompt 的依据）

| 缺口 | 归属 |
|---|---|
| B-SET-5 flaky 根因（2600ms 固定等待 vs 2500ms 路由延迟，余量仅 100ms；两次隔离复跑通过 ≠ 根治） | Prompt 1 · 任务 A |
| index.html 从未按七维度审查（唯一一页） | Prompt 1 · 任务 B |
| tasks.html 双标签并存、升级判据未定 | Prompt 1 · 任务 C + Prompt 2 判定 |
| 收尾改动落在代码后，最终 HEAD 需一次新鲜完整 Chromium 汇总 + 全部门禁 | Prompt 2 |
| 21 页权威总表 + 主线关闭 + 防自审自批 | Prompt 3（必须新上下文） |

### 明确不在本收尾范围（`not_verified`，不阻塞升级，另立专项）

真实 Provider（生成/评分）、真实 OCR/ASR 质量、live delivery、跨浏览器、完整人工键盘逐键走查、系统级屏幕阅读器（NVDA/JAWS/VoiceOver）、cram 冲刺会话 A 类全链、极端长内容与长时稳定性。

---

## 公共约束块（投喂每份 prompt 时必须整体粘贴在最前面）

```text
【本机环境与运行约束（必须遵守）】
- git：所有 git 命令加 -c http.proxy= -c https.proxy= 前缀，否则走系统代理会静默挂起。
- 禁用 git stash（曾触发 auto-gc 毁掉 .git 对象库）。基线对比只用文件级 cp 或 git show HEAD:<path>。
- Playwright：输出目录必须显式 --output="H:/studybuddy-test/runs/<名称>-<时间戳>"，
  否则默认清理 test-results 会被 safe-delete 守卫拦截中断。
- pytest 全量：CODEBUDDY_SAFE_DELETE_ENABLED=0 C:/miniconda/py310/python.exe -m pytest backend/tests/ -q
- 完整 Chromium（~430 项）单次串行超过 20 分钟工具窗口：必须后台启动 + --reporter=list
  重定向到 .log 文件，完成后读 log 取 total/passed/failed/skipped/did-not-run 与退出码，不要前台等待。
- 浏览器测试运行入口：backend/scripts/test-browser.ps1，或 cd H:/studybuddy && npm run test:browser（workers=1）。
- data root 只用 H:/studybuddy-test/runs/<时间戳> 独立空目录；绝不写 H:\studybuddy\data 或 H:\studybuddy-data\live。
- Provider 一律确定性 fake：STUDYBUDDY_AI_PROVIDER=fake。
- 诚实规则：能力不足/未覆盖一律如实标 not_verified；禁止为收尾放宽断言、加 sleep、加 retry、skip 用例凑绿。
- 状态标签唯一：一个页面同一时点只能有一个页面级状态标签；not_verified 不作为页面级标签使用，
  只用于在页面状态之下列出具体未验证维度（维度级 not_verified 与页面状态并存是既定实践）。
```

---

## Prompt 1：尾项收口（B-SET-5 根因修复 + index.html 审查 + tasks 证据准备）

```text
【角色】StudyBuddy 前端审查执行者（A 类实现 + 一审）。完成后由独立二审方复核。
【投喂时】必须在本 prompt 前整体粘贴本文件《公共约束块》。

【背景】
H:\studybuddy 是本地单进程学习系统，正式前端为 backend/app/static/ 下 21 个 HTML 页面。
当前 19 页为限定范围 e2e-real-pass；剩余尾项三个：
1) settings B-SET-5 flaky 未根治；
2) index.html（510 B 兼容跳转页）从未按七维度审查；
3) tasks.html A 类 7 + B 类 7 已过，但文档存在「scoped browser-pass」与「not_verified」双标签矛盾，
   且升级判据未定。
本任务处理这三个尾项并修复真实缺陷；不做与尾项无关的功能开发。

【任务 A：settings B-SET-5 根因修复（必做项，不是可选项）】
- 独立复现 browser_settings_b_class.spec.js 的 B-SET-5：至少 3 次运行，记录失败频率与失败点。
  若 3 次均未复现，不得据此判定「无问题」：100ms 余量分析本身就是根因证据，
  仍须按下述类别修复并连续 3 次全绿收口。
- 判定根因类别：产品代码竞态 / 测试固定等待余量过小（当前 2600ms 固定等待对 2500ms 路由延迟仅
  100ms 余量）/ 服务启动关闭生命周期 / 响应延迟边界 / 多项叠加。
- 修复根因。禁止仅加长 sleep、放宽断言、外层 retry 掩盖。测试必须等待可观察状态或事件，
  不依赖窄时间余量。
- 修复后验证 settings.html 与 settings-provider.html 既有守卫未回归：
  generation/request-token 守卫、编辑表单作废在途验证、保存按钮不被迟到响应恢复、
  失败与恢复状态、busy/disabled 防重复、secret 不回显、刷新后真实状态。
- 收口标准：browser_settings_b_class.spec.js 连续 3 次全绿。

【任务 B：index.html 兼容跳转页 A/B 审查收口】
按七维度裁剪适配跳转页（index.html 全部内容为 meta refresh + canonical + location.replace + 兜底链接）：
1. 页面结构：无内联 <style>；不依赖 css/tokens.css、css/app.css、js/*.js。
2. 正常路径（A 类）：/app/index.html、/app/、/ 三种入口最终 URL 均为 /app/today.html 且 today 正常渲染。
3. 降级路径：Playwright context { javaScriptEnabled: false } 下 meta refresh 仍能跳转；
   兜底 <a href="/app/today.html"> 可点击落到 today 页。
4. 边界：带 query/hash（如 /app/index.html?x=1#y）不报错；直接深链 today 正常。
5. 响应式：390×844 与 1920×1080 无横向溢出（一次断言即可）。
6. 契约/治理：backend/scripts/audit-frontend-contract.py --strict = 0 findings
   （21 页白名单已含 index.html）。
7. 真实业务链路：不适用，如实标注。
- 复用并扩充 backend/tests/browser_migration.spec.js 既有跳转断言；如需独立用例，
  新建 backend/tests/browser_index_redirect_userpath.spec.js（命名与既有 A 类 spec 一致）。
  若判定既有覆盖已足够可不新增文件，但必须写清复用哪个用例、断言什么，不得空口称通过。
- 结论定性：index.html = 「兼容跳转页边界通过（限定范围）」，不伪称完整业务 E2E。
- 边界：不修改跳转目标 /app/today.html（唯一既定入口），不引入共享 CSS/JS 依赖。

【任务 C：tasks.html 证据准备（本任务不改状态标签，升级判定统一在 Prompt 2）】
- 从 09-14 完整汇总（STATUS 记录 425 passed / 4 skipped / 1 failed，430 tests）与可查日志确认：
  browser_tasks_userpath.spec.js、browser_tasks_b_class.spec.js、browser_p1_4_c4_3_task_list.spec.js
  均全绿，且唯一失败 B-SET-5 与 tasks 无关。
- A 类纯度复核：browser_tasks_userpath.spec.js 是否存在 page.request 直调业务 API 建数据/取关键 ID；
  如有，收紧为纯 UI 路径。
- 复核此前观察到的 plans full-coverage 归档断言失败：确认是既有 flaky 还是真实缺陷；
  真实缺陷则修（含回归），flaky 则给出复现与归因。
- 本任务只修真实缺陷、准备证据；不改 tasks.html 状态标签。

【测试要求】
1. focused：settings B 类（连续 3 次）、tasks A/B 专项、browser_migration（及新增 index 用例）、
   静态基线 / 页面契约。
2. 若改动后端或测试服务生命周期：CODEBUDDY_SAFE_DELETE_ENABLED=0 全量后端。

【门禁】
- C:/miniconda/py310/python.exe backend/scripts/check-source-size.py --base HEAD
- C:/miniconda/py310/python.exe backend/scripts/audit-frontend-contract.py --strict
- git diff --check

【文档】
- 只在本任务确实修改了 backend/app/、backend/app/static/ 或测试时，更新
  docs/[需求+所有角色看]STATUS.md 与 docs/[需求看]TODO.md。
- 不新建 docs/evidence 或 docs/contracts 文档；不把专项通过扩大为全局全绿。

【交付物】
1. B-SET-5 根因、修复内容、3 次连跑结果。
2. index.html 审查结论 + 用例清单（复用或新增）+ 执行命令与 passed 数。
3. tasks 相关 spec 在 09-14 汇总中的证据摘录；A 类纯度复核结论；plans 归档失败归因。
4. 执行过的全部命令与准确结果；git diff 摘要；是否仍有阻塞 Prompt 2 的问题。

【边界】不做与三个尾项无关的功能开发；不提交/推送，除非用户明确要求。
```

---

## Prompt 2：最终统一验收（最终 HEAD 上的一次新鲜完整回归 + 状态判定）

```text
【角色】StudyBuddy 测试基础设施与验收执行者。依赖 Prompt 1 完成。
【投喂时】必须在本 prompt 前整体粘贴本文件《公共约束块》。

【背景（v2 更正后的事实）】
09-14 轮已取得完整 Chromium 汇总 425 passed / 4 skipped / 1 failed（430 tests），
唯一失败为 settings B-SET-5。但 Prompt 1 修复了 B-SET-5 并新增/扩充了 index 用例，代码已变。
收口基线必须在最终 HEAD 上重新取得一次完整、落盘、可审计的退出汇总；
该汇总同时是全局回归基线和 tasks.html 升级的直接证据。

【执行】
一、完整 Chromium 串行（fresh run）
- 在 H:/studybuddy-test/scripts/ 下产出可复用运行脚本（.ps1）：时间戳 --output、
  --reporter=list 落 .log、记录退出码、--workers=1。后台执行，完成后读 log 取汇总。
- 汇总口径必须包含：total / passed / failed / skipped / did not run
  + 每个 failed / did-not-run 的 spec 文件::用例名 + 一行失败摘要。
- EPERM 处置：若在非本轮 spec 的 fixture 清理处 EPERM 中断，记录具体路径与 spec，
  改为每 spec 独立时间戳 data root + 显式 --output；不得删他人目录绕过。

二、失败归因规则
- B-SET-5 此时已修：任何 settings 失败都是新问题，必须修复并重跑，不得再引用「既有偶发」。
- 其他已知 flaky 家族（browser_p6e、phase9c 会话时序、cram/plans 数据依赖）逐项归因：
  本轮引入 → 修复 + 重跑受影响专项 + 重新完整运行；
  既有 flaky → 给出复现命令与余量分析，并明确说明是否影响任何页面的验收结论。
- 只有最终完整运行 0 failed、0 did not run 才可宣称全绿；
  分组串行必须如实标注「分组串行，非单次连续运行」，不得伪称单次全绿。

三、完整后端 + 门禁
- CODEBUDDY_SAFE_DELETE_ENABLED=0 C:/miniconda/py310/python.exe -m pytest backend/tests/ -q
- check-source-size.py --base HEAD；audit-frontend-contract.py --strict；git diff --check；
  静态基线、视觉矩阵、系统矩阵等规定矩阵 spec。

四、21 页验收映射表
- 每页列出：A 类 spec、B 类 spec、共享/系统矩阵 spec、当前状态、已验证范围、not_verified 维度。
- 共享 spec 必须说明哪些用例覆盖哪页；不得只写 spec 文件名。
- index.html 按「兼容跳转页边界」口径，不要求伪造业务操作。

五、状态判定（五级；标签二选一）
- tasks.html 升级判据（全部满足才升限定范围 e2e-real-pass）：
  ① browser_tasks_userpath / browser_tasks_b_class / browser_p1_4_c4_3_task_list
     在本次完整汇总中全绿；
  ② B-SET-5 已修且 settings 相关 spec 在本次完整汇总中全绿；
  ③ focused 后端（-k task）+ 全量后端 + 门禁三件套通过；
  ④ A 类纯度复核通过。
  任一不满足 → 保持单一标签 scoped browser-pass（= tested 的项目惯用写法）并写清缺口，
  禁止与 not_verified 并存。
- 其余 19 页：本次完整汇总与门禁全绿则维持限定范围 e2e-real-pass；
  受 Prompt 1 改动影响的页面（settings 两页、index）按本次证据定稿。
- 不得因「要收尾」强行升级任何页面。

【文档】
- 更新 STATUS/TODO 为单一当前摘要；清理矛盾：
  「21/21 完成」与「index 未审」并存、全绿与失败并存、tasks 双标签、
  index 误写完整业务页、历史快照冒充当前基线。
- 不删有价值历史记录，但当前结论必须唯一。不新建 evidence/contracts 文档。

【交付物】
1. 完整 Chromium 汇总 + 退出码 + log 路径 + 可复用脚本路径。
2. 失败归因清单（含 flaky 家族的复现命令与余量分析）。
3. 完整后端结果 + 门禁结果。
4. 21 页验收映射表。
5. 修复清单、未验证边界、是否满足进入 Prompt 3、git status/diff 摘要。

【边界】不做与验收无关的功能开发；不修改断言凑过；不提交/推送，除非用户明确要求。
```

---

## Prompt 3：独立复核与正式结项（必须新上下文执行）

```text
【角色】StudyBuddy 最终独立复核者。不得由 Prompt 1/2 的执行者或同一上下文兼任。
你没有权限仅凭前两位执行者的总结宣布通过；必须独立读代码、测试、diff 与实测结果。
【投喂时】必须在本 prompt 前整体粘贴本文件《公共约束块》。

【目标】判断这句话是否有充分证据：
「StudyBuddy 的 21 个正式页面已完成 A/B 审查；不存在正在进行或尚未开始的页面。」
（仅描述页面 A/B 审查，不含真实 Provider、真实 OCR/ASR、live delivery、跨浏览器、
 系统级屏幕阅读器或全局生产 real-pass。）

【检查一：数量与范围】
- 确认 backend/app/static/ 下恰有 21 个正式 HTML 页面，无遗漏、无误计。
- index.html 按「兼容跳转页边界」口径处理。
- 每页都有 A/B 覆盖映射；不接受「由全量测试覆盖」的笼统说法。

【检查二：证据真实性】
抽查并复读高风险 8 页：settings.html、settings-provider.html、tasks.html、capture.html、
classroom.html、reports.html、review.html、index.html。重点：
- A 类纯度：是否页面 UI 建数据；page.route/mock 用例是否标注 B 类要素；
  是否存在 page.request 播种被写成纯 A 类。
- 是否存在 sleep、弱 OR、静默 catch、跳过断言；是否只验证 HTTP 200 而未验证用户可见结果；
  是否验证错误恢复而非只验证错误出现。
- 是否覆盖迟到响应、busy 防重复、XSS 纯文本、安全错误映射。
- 是否泄露路径、SQL、traceback、secret、原始 provider 错误或正文。
- 是否把隔离复跑通过冒充完整回归全绿。

【检查三：状态一致性】
- 逐页终态（五级 + 兼容跳转页边界通过）。
- 独立判断：tasks.html 是否该升级；B-SET-5 是否已根治；
  capture/classroom 是否确有 A/B 两类独立证据；index.html 是否完成其口径内审查。
- 双标签（页面状态与 not_verified 并存）必须清零。

【检查四：测试复核】
- 跑高风险页 focused specs。
- 核对 Prompt 2 完整汇总 log 的完整性与退出码；代码其后有变动则重跑必要门禁。
- check-source-size + git diff --check。
- 发现产品或测试缺陷 → 直接修复并跑相应回归；发现缺陷后不得宣布结项。

【文档结项】
- 只更新 docs/[需求+所有角色看]STATUS.md 与 docs/[需求看]TODO.md；
  权威 21 行总表（序号|页面|状态|A 类 spec+用例数|B 类 spec+用例数|收口轮次/commit|not_verified 项）
  可另落 docs/roles/[需求+测试看]UI_AB_REVIEW_MATRIX.md 并在 STATUS 链接。
- 数据必须核对实际 spec 文件存在性，不得照抄文档。
- 当前摘要必须写：完成 X/21、进行中数、未开始数、每个非 e2e-real-pass 页面及原因、
  完整 Chromium 精确结果、完整后端精确结果、not_verified 能力边界。
- 只有证据满足才可写「21/21 页面 A/B 审查完成，进行中 0，未开始 0」；
  不满足则列出阻塞页与最小修复任务，禁止为形式收尾强行通过。

【最终回复格式】
## 独立结论（通过 / 有条件通过 / 不通过）
## 页面统计（完成 / 进行中 / 未开始）
## 逐页状态（21 行表）
## 发现的问题（按严重程度，附文件与行号）
## 实测结果（命令、passed/failed/skipped、退出码）
## 文档修改
## 未验证边界
## 是否允许正式结项（只能回答「允许」或「不允许」+ 理由）

【边界】不为形式收尾强行通过；不提交/推送，除非用户明确要求。
```

---

## 使用顺序

```text
Prompt 1（尾项收口：B-SET-5 根因 + index 审查 + tasks 证据准备）
    ↓
Prompt 2（最终统一验收：最终 HEAD 新鲜完整 Chromium + 后端 + 门禁 + 状态判定）
    ↓
Prompt 3（独立复核 + 权威总表 + 主线关闭；必须新上下文）
```

严格串行；Prompt 3 不得与 Prompt 1/2 同一执行者或同一上下文。
每份完成后按双层审核规程由独立二审方（GPT）复跑关键结论后方可定稿状态。

# practice.html + practice-session.html 七维度 UI 测试计划

> 规程依据：双层审核工作规程（GLM 一审 + GPT 二审）。页面状态采用五级：`implemented` / `tested` / `e2e-real-pass` / `not_verified` / `blocked`。**只有 A 类纯用户路径全部通过且 GPT 二审通过，页面才能标记 `e2e-real-pass`。**
> 本文档是两页唯一测试计划（七个维度一章一节，不拆分多份）。
> 范围说明：practice-result.html 与 review.html 是本链路的下游页面，本计划只覆盖其作为「结果出口 / 错题复盘出口」的链接与数据流，不替代对这两页的独立审查。

## 范围与测试分类

- A 类（纯用户路径 E2E）：`backend/tests/browser_practice_userpath.spec.js`——所有数据经页面 UI 创建（材料导入→索引→练习集→AI 草稿→确认→推荐练习→会话→作答→完成→复盘），材料/练习/会话 ID 一律从页面 URL/链接获取，禁止测试代码直调业务 API 取关键 ID 或建数据；网络故障注入只用 `page.route` 并显式标注。
- B 类（接口与故障注入，既有）：`backend/tests/browser_p2_fe3_practice_session_app.spec.js`、`browser_p2_fe3_practice_result_app.spec.js`、`browser_p2_fe3_review_app.spec.js`、`browser_practice_workflow.spec.js`、`browser_practice_recommendations.spec.js`、`browser_p1_4_c4_cram.spec.js`、`browser_p2_fe4_weak_points_app.spec.js`——允许 `page.request`/路由 mock，用于补边界与错误验证。

## 维度一：页面结构

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| practice 页标题/导航/冲刺目标区/推荐练习区/练习会话区/错题库区 | A-E2E-PRAC-1/2/3 | [x] tested |
| practice 页全部按钮/表单/下拉可定位（含新建的「来自练习集的题目」入口区） | A-E2E-PRAC-1/4 | [x] tested |
| practice-session 页标题/返回练习链接/会话状态区/重试按钮/逐题作答区（题号/题面/选项/上一题/提交/完成会话） | A-E2E-PRAC-2/4/6 | [x] tested |
| 冲刺目标创建表单与目标列表渲染 | A-E2E-PRAC-6 | [x] tested |

## 维度二：正常用户路径（A 类）

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| materials 页导入真实 TXT → material-detail 页建索引 →（id 从 URL 获取） | A-E2E-PRAC-1 | [x] tested |
| exercises 页 UI 创建练习集 → 生成题目草稿（topic+material id）→ 草稿出现 → 确认 → ready | A-E2E-PRAC-1 | [x] tested |
| practice 页推荐练习出现已确认题目（含来源有效标签）→ 勾选两题 → 创建练习会话 → 跳转会话页 | A-E2E-PRAC-2 | [x] tested |
| 会话开始 → 逐题提交（自动推进到下一题）→ 完成会话 → practice-result 页真实得分 | A-E2E-PRAC-2 | [x] tested |
| 错题（确定性答错自动生成）出现在 practice 错题库且显示真实题面 → 查看错题 → review 页状态/薄弱点汇总 | A-E2E-PRAC-3 | [x] tested |
| 已完成会话在列表内联查看结果（内嵌得分与结果页一致） | A-E2E-PRAC-3 | [x] tested |
| exercises 页「开始作答」→ practice 页单题入口 → 一键创建单题会话 → 作答 → 结果（缺陷 1 回归） | A-E2E-PRAC-4 | [x] tested |

## 维度三：错误路径

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 会话列表/错题/推荐练习 GET 注入 500 → 安全文案（请求失败，请重试），无 traceback/内部错误码/路径 | A-E2E-PRAC-5 | [x] tested |
| 取消注入后经页面刷新按钮真实恢复三区数据 | A-E2E-PRAC-5 | [x] tested |
| 会话详情加载失败 → 重试按钮 → 恢复 | A-E2E-PRAC-5 | [x] tested |
| 不存在的 exercise_id（单题入口）→ 安全文案「题目不存在」 | A-E2E-PRAC-4 | [x] tested |
| 全程页面可见文本敏感信息扫描（traceback/SQL/密钥/Windows 路径） | 所有用例（assertNoSensitiveVisibleText） | [x] tested |
| 会话不存在/缺会话标识安全文案 | B 类既有 `browser_p2_fe3_practice_session_app.spec.js`（2/4 用例）与 `browser_practice_workflow.spec.js` retry 用例 | [x] tested |

## 维度四：数据持久化（含服务真重启）

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| **杀进程→同 data root 重启服务→等 /api/readiness→重开页面**：两个练习会话（推荐练习/单题练习）均保留且状态已完成 | A-E2E-PRAC-7 | [x] tested |
| 重启后错题保留且题面正确、内嵌结果得分与重启前一致（1/2） | A-E2E-PRAC-7 | [x] tested |
| 重启后 review 页错题与薄弱点汇总（出现次数）持久 | A-E2E-PRAC-7 | [x] tested |

## 维度五：数据边界与状态边界

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 草稿题目不能创建会话（后端 `exercise_not_ready` 404）；确认后才能进入推荐 | A-E2E-PRAC-1/2（确认前置）+ 后端 `test_phase9c_api` | [x] tested |
| 确定性评分边界：答对得分/答错 0 分且自动生成错题（multiple_choice answer_key 索引） | A-E2E-PRAC-2/4（1/2 与 0/1 两种结果）+ 后端回归 | [x] tested |
| 同一题目重复答错 → 同一错题案例新增发生记录（不重复建案例），薄弱点出现次数累加 | A-E2E-PRAC-3（1 次）→ A-E2E-PRAC-7（2 次） | [x] tested |
| 会话过期（expired）不可提交、显示已过期 | B 类既有 `browser_practice_workflow.spec.js` expired 用例 + 后端 `test_phase9c_domain` | [x] tested |
| 提交幂等（Idempotency-Key 重放/不一致 409） | 后端 `test_phase9c_api.py::test_s3_api_round_trip_privacy_and_idempotency` | [x] tested |
| 错题 API 不泄露 answer_key/answer_json（题面为公开字段） | 后端 `test_phase9c_api.py::test_s4b_api_mistake_surfaces_exercise_prompt`（本轮新增） | [x] tested |

## 维度六：响应式和键盘

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 5 档 viewport（1280×720/1440×900/1920×1080/768×1024/390×844）：practice 与 practice-session 无横向溢出 | A-E2E-PRAC-6 | [x] tested |
| 截图留证（供二审人工核验）：`H:\studybuddy-test\artifacts\practice-userpath\practice-*.png`、`session-*.png`（10 张） | A-E2E-PRAC-6 | [x] tested |
| 键盘：冲刺目标表单 Enter 提交；Tab 可达表单/按钮 | A-E2E-PRAC-6 | [x] tested |
| 焦点样式自动检查（outline style/width 或 box-shadow 至少一项可见）：`#cram-title`、`#refresh-cram` | A-E2E-PRAC-6 | [x] tested |
| 100 字长中文目标标题窄屏不撑破布局 | A-E2E-PRAC-6（含 390 档） | [x] tested |
| 会话页逐题作答控件 aria-label（选择答案/填写答案） | B 类既有 spec 断言 + 本轮人工核对 | [x] tested |
| 完整人工视觉焦点可见性审查（全部交互元素）、屏幕阅读器 | **未覆盖** | [ ] not_verified |

## 维度七：真实链路

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 经 materials 页导入真实 TXT fixture（H:\studybuddy-test\fixtures\practice-userpath\练习链路测试材料.txt）→ material-detail 建索引 → 练习集生成 AI 草稿（引用该材料 chunk）→ 确认 → 推荐来源有效 → 会话 → 确定性评分 → 错题 → 复盘 → 弱点 | A-E2E-PRAC-1→7 全链 | [x] tested |
| 真实 Provider（DeepSeek/Agnes 练习生成、真实评分） | 本轮明确不覆盖（全部 deterministic fake Provider） | [ ] not_verified |
| 真实 OCR/ASR 材料进入练习链路 | 本轮明确不覆盖 | [ ] not_verified |

## 执行记录（2026-09-10 第一轮，GLM 一审）

```text
执行命令 1：
cd H:/studybuddy && npx playwright test backend/tests/browser_practice_userpath.spec.js --output="H:/studybuddy-test/runs/pw-out-practice-userpath-5"
结果：7 passed（19.6s）；复跑（-6 目录）再次 7 passed（19.7s），稳定。

执行命令 2（本页相关既有回归）：
practice/result/review/workflow/recommendations/cram/weak-points 共 7 spec：27 passed。
static_core/static_pages/frontend_page_contract/frontend_visual_matrix：14 passed。

执行命令 3：
C:/miniconda/py310/python.exe -m pytest backend/tests/ -q
结果：628 passed, 3 skipped（3 skips 为 opt-in 真实 Provider/ASR smoke；含本轮新增 test_s4b_api_mistake_surfaces_exercise_prompt）。

执行命令 4：
C:/miniconda/py310/python.exe backend/scripts/check-source-size.py --base HEAD → passed
C:/miniconda/py310/python.exe backend/scripts/audit-frontend-contract.py --strict → 0 findings
git diff --check → 通过

环境：
- Python：C:\miniconda\py310\python.exe（uvicorn app.main:app，单进程）；Node/Playwright Chromium
- data root：H:/studybuddy-test/runs/practice-userpath-<时间戳>（独立空目录，未触碰 H:\studybuddy\data 与 H:\studybuddy-data\live）
- Provider：deterministic fake（STUDYBUDDY_AI_PROVIDER=fake）；未验证真实 GLM/DeepSeek/Agnes 练习生成与评分。
```

## 本轮发现并修复的缺陷（A 一审，GLM）

1.【缺陷·已修·前端】`exercises.html`「开始作答」跳转 `/app/practice.html?exercise_id=…`，但 practice.html 完全忽略该参数：用户点「开始作答」后落到一个与该题目毫无关联的页面，用户路径断裂。修复：practice.html 新增「来自练习集的题目」入口区，读取 exercise_id，ready 题目展示题面 + 「为该题目创建练习会话」按钮（POST 创建单题会话后跳转会话页）；非 ready 显示安全状态说明；无效 ID 显示「题目不存在」。回归：A-E2E-PRAC-4。
2.【缺陷·已修·前端】practice.html 错题库把题目文本 `replaceChildren(链接)` 覆盖成「查看错题」，题目内容丢失，多条错题无法区分。修复：题面文本与「查看错题」链接分行展示。回归：A-E2E-PRAC-3。
3.【缺陷·已修·后端+前端】错题 API 从不返回题面：`mistake_cases` 表不含题目内容，`get_mistake_case`/`list_mistake_cases` 响应无 `question` 字段，真实数据下 practice 错题库永远显示占位「题目」、review 页无题面可复盘（既有 B 类 spec 全部 mock 数据，掩盖了该缺陷）。修复：`get_mistake_case` 按 project 关联 exercises 补充公开字段 `question` 与 `exercise_type`（不含 answer_key/answer_json，隐私边界不变）；前端随之显示真实题面。回归：后端 `test_s4b_api_mistake_surfaces_exercise_prompt` + A-E2E-PRAC-3/7。
4.【缺陷·已修·前端】practice.html 会话详情内嵌「查看结果」读取不存在的 `result.score/result.total` 字段（API 真实返回 `summary.score_total/summary.total_item_count`），内嵌得分永远显示「得分: 0 / 0」，与 practice-result 页不一致。修复：改读 `result.summary` 真实字段。回归：A-E2E-PRAC-3/7（内嵌得分 = 1/2 与重启前一致）。

## 页面状态结论（GPT 二审前）

| 页面 | 状态 | 依据与未覆盖项 |
| --- | --- | --- |
| practice.html | `tested`（倾向 `e2e-real-pass`，待 GPT 二审） | A 类 7 用例（含真重启）+ B 类回归 27 passed + 后端全量 628 passed；修复缺陷 1/2/3/4。**未覆盖**：真实 Provider、完整人工视觉焦点审查、屏幕阅读器、cram 冲刺会话创建的 A 类全链（仅覆盖目标创建与列表） |
| practice-session.html | `tested`（倾向 `e2e-real-pass`，待 GPT 二审） | 同上；逐题作答/完成/过期边界由 A 类 + B 类共同覆盖。**未覆盖**：真实 Provider、会话过期倒计时的真实时钟边界（后端确定性测试覆盖）、屏幕阅读器 |
| 两页合并 | `tested` | A 类、浏览器 B 类与后端边界测试通过；真实 Provider 与完整人工视觉审查仍未验证，GPT 二审通过前不升级为 `e2e-real-pass` |

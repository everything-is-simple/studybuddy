# plans.html + plan-detail.html 七维度 UI 测试计划

> 规程依据：双层审核工作规程（GLM 一审 + GPT 二审）。页面状态采用五级：`implemented` / `tested` / `e2e-real-pass` / `not_verified` / `blocked`。**只有 A 类纯用户路径全部通过且 GPT 二审通过，页面才能标记 `e2e-real-pass`。**
> 本文档是两页唯一测试计划（七个维度一章一节，不拆分多份）。旧版"静态元素逐项勾选"记录已被本版取代（旧版 64 项全过的结论只能算 `tested`）。
> 旧版截图核对结论仍然有效，要点：来源区"正在加载"是未选中计划所致；"0 个项目"缺陷已修；开始/完成按钮需 active 计划 + item_id URL；截图重叠为拼接伪影。

## 范围与测试分类

- A 类（纯用户路径 E2E）：`backend/tests/browser_plans_plan_detail_userpath.spec.js`——所有数据经页面 UI 创建，plan_id 从页面"打开详情"链接/URL 获取，禁止测试代码直调业务 API 取关键 ID。
- B 类（接口与故障注入）：`backend/tests/browser_plans_plan_detail_full.spec.js`（describe 已标注 B-class）——允许 `page.request` 观察/取 ID、路由拦截注入失败；**不是纯用户路径 E2E**，用于补边界与错误验证。

## 维度一：页面结构

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| plans 页标题/导航/空状态（暂无目标/暂无模块/请先创建学习目标） | P-A | [x] tested |
| plans 页全部按钮/表单/下拉存在且可定位 | P-A~P-I、A-E2E-PLAN-FULL-LIFECYCLE | [x] tested |
| plan-detail 页标题/返回链接/刷新进度/缺 plan_id 错误态 | D-A/B、D-D15 | [x] tested |
| 详情区状态徽章/学习项卡片/依赖/进度摘要/进度历史渲染 | D-A/B | [x] tested |

## 维度二：正常用户路径（A 类）

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 页面建目标→建模块→建计划草稿→加 2 个学习项（含绑定模块）→加依赖→存节奏→加分派 | A-E2E-PLAN-FULL-LIFECYCLE | [x] tested |
| 确认→激活→经 today 页任务链接进入 detail（URL 含 item_id/return_to）→开始学习→记录完成 | A-E2E-PLAN-FULL-LIFECYCLE | [x] tested |
| 暂停→恢复→完成计划→归档（编辑禁用验证） | A-E2E-PLAN-FULL-LIFECYCLE | [x] tested |
| 从页面"打开详情"链接导航（不从 API 取 plan_id） | A-E2E-REAL-SOURCE-LINK、PERSIST | [x] tested |
| 状态转换点击（B 类补充：确认/激活/暂停/恢复/完成/归档全链） | P-D20、P-D21/22 | [x] tested |

## 维度三：错误路径

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 空目标名/空模块名/空计划名（required 拦截 + 后端空值拒绝） | P-B、P-C、P-D15 | [x] tested |
| 依赖自环（predecessor==successor）拒绝 | P-F | [x] tested |
| 节奏接口失败→提示"节奏加载失败，可重试"且不阻塞页面 | P-G39 | [x] tested |
| 缺 plan_id → "缺少计划标识"，无重试按钮 | D-D15 | [x] tested |
| 计划加载失败 → 错误提示 + 重试恢复 | D-D16/17/18 | [x] tested |
| 对话框取消路径（prompt 空值/取消不产生数据） | P-B、A-E2E-RESPONSIVE-AND-KEYBOARD | [x] tested |
| 页面错误状态不泄露 traceback/SQL/路径/密钥（显式可见文本扫描） | A-E2E-RESPONSIVE-AND-KEYBOARD | [x] tested |

## 维度四：数据持久化（含服务真重启）

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 刷新页面后计划/学习项/排序/描述保留 | P-D19、P-E23/24/25/28 | [x] tested |
| **杀进程→同 data root 重启服务→等 /api/health→重开页面**：目标/计划/项目数/状态徽章/节奏参数/分派/进度全保留 | A-E2E-PERSIST-REAL-RESTART | [x] tested |
| 重启后 today 页任务仍可见（经页面验证跨页持久化） | A-E2E-PERSIST-REAL-RESTART | [x] tested |
| 来源链接重启后保留（杀进程→同 data root 重启→重进详情验证来源仍在→删除验证消失） | A-E2E-REAL-SOURCE-LINK（stopServer/startServer 段） | [x] tested |

## 维度五：数据边界与状态边界

> 命名说明：StudyBuddy 为本地单进程单用户系统，本维度是数据/状态边界，**不是**登录/角色/多用户隔离（系统不提供该能力，不在此声称）。

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 不存在/无效 plan_id（路由拦截模拟） | D-D16/17/18 | [x] tested |
| 草稿计划不渲染开始/完成按钮（状态边界） | D-C14、P-D20 前置 | [x] tested |
| 已完成计划禁用编辑；归档目标/模块从下拉移除；归档计划从列表移除 | P-B10、P-C14、P-D21/22、A-E2E-PLAN-FULL-LIFECYCLE | [x] tested |
| 已归档学习项不可保存 | P-E26 | [x] tested |
| 不属于当前计划的 item_id：进度/来源操作被后端拒绝，且不泄露 traceback | `test_phase9a_api_rejects_cross_plan_item_progress_and_source`（B 类 API 边界） | [x] tested |
| 跨项目 plan_id：其他 project 返回 404，且不泄露计划标题/traceback | `test_phase9a_api_rejects_cross_project_plan_access`（B 类 API 边界） | [x] tested |
| 依赖环 A→B→A：后端拒绝且保留已有依赖 | `test_phase9a_api_dependency_cycle_and_state_errors`（B 类 API 边界） | [x] tested |

## 维度六：响应式和键盘

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 5 档 viewport（1280×720/1440×900/1920×1080/768×1024/390×844）：无横向溢出、plans 与 plan-detail 关键元素/长标题断言 | A-E2E-RESPONSIVE-AND-KEYBOARD | [x] tested |
| 截图留证（供二审人工核验，DOM 断言之外的视觉检查） | H:\studybuddy-test\artifacts\plans-userpath\*.png（10 张） | [x] tested |
| 键盘：Enter 提交目标表单；Tab 可达各表单/操作按钮；Enter/Space 选中计划；Tab 到"打开详情"；disabled（来源添加按钮空态）被跳过；prompt 取消不产生数据 | A-E2E-RESPONSIVE-AND-KEYBOARD | [x] tested |
| 长中文标题（100 字）窄屏不撑破布局 | A-E2E-RESPONSIVE-AND-KEYBOARD | [x] tested |
| 焦点样式自动检查（outline style/width、box-shadow 至少一项可见）：`#goal-title`、`#refresh-progress` | A-E2E-RESPONSIVE-AND-KEYBOARD（assertFocusStyle） | [x] tested |
| 自动焦点样式：目标输入框、详情刷新按钮具有 outline/box-shadow | A-E2E-RESPONSIVE-AND-KEYBOARD | [x] tested |
| 完整人工视觉焦点可见性审查（全部交互元素） | **未覆盖** | [ ] not_verified |

## 维度七：真实链路

| 检查项 | spec（用例） | 状态 |
| --- | --- | --- |
| 经 materials 页面导入真实 TXT fixture（H:\studybuddy-test\fixtures\真实链路测试材料.txt）→ material-detail 页点"索引"→"索引已建立" | A-E2E-REAL-SOURCE-LINK | [x] tested |
| plans 页来源候选出现该材料片段→添加来源链接→链接列表持久→刷新后仍在 | A-E2E-REAL-SOURCE-LINK | [x] tested |
| plan-detail 来源状态经页面验证：未关联→有效（静默）→删除后未关联 | A-E2E-REAL-SOURCE-LINK | [x] tested |
| 真实 Provider（DeepSeek/Agnes 问答、卡片、练习生成） | 本轮明确不覆盖 | [ ] not_verified |

## 执行记录（2026-09-09 第一轮，GLM 一审）

```text
执行命令 1：
cd H:/studybuddy && npx playwright test backend/tests/browser_plans_plan_detail_userpath.spec.js --output="H:/studybuddy-test/runs/pw-out-userpath-<时间戳>"
结果：4 passed（A-E2E-PLAN-FULL-LIFECYCLE 14.6s / A-E2E-REAL-SOURCE-LINK 9.6s / A-E2E-RESPONSIVE-AND-KEYBOARD 9.5s / A-E2E-PERSIST-REAL-RESTART 13.4s）

执行命令 2：
cd H:/studybuddy && npx playwright test backend/tests/browser_plans_plan_detail_full.spec.js --output="H:/studybuddy-test/runs/pw-out-full-<时间戳>"
结果：（B 类）24 passed

执行命令 3：
C:/miniconda/py310/python.exe backend/scripts/check-source-size.py --base 3327254
结果：source-size check passed（32768 字节策略）

环境：
- Python：C:\miniconda\py310\python.exe（uvicorn app.main:app，单进程）
- Node/Playwright：仓库 package-lock 锁定版本，Chromium
- viewport：响应式用例覆盖 5 档；其余默认 1280×720
- data root：H:/studybuddy-test/runs/plans-plan-detail-userpath-<时间戳>（独立空目录，未触碰 H:\studybuddy\data 与 H:\studybuddy-data\live）
- Provider：deterministic fake（STUDYBUDDY_AI_PROVIDER=fake）；计划和进度页面使用 fake Provider，未验证真实 GLM/DeepSeek Provider，未验证真实问答、卡片和练习生成。

本轮发现并修复的缺陷：
1.【缺陷·已修】plans.html 选中计划后列表不高亮：selectPlan 从不调用 renderLists，selected 类要等"刷新数据"才出现。修复：selectPlan 内按 dataset.planId 原位 toggle selected（不重建节点，保留焦点）。
2.【行为确认·非缺陷】plan-detail 学习项卡片来源行只在状态异常时显示（valid 静默、无链接显示"来源：未关联来源"），appendSource 设计如此。
```

## 页面状态结论（GPT 二审前）

| 页面 | 状态 | 依据与未覆盖项 |
| --- | --- | --- |
| plans.html | `tested` | A 类 4 用例 + B 类 24 用例通过；自动化已覆盖计划/项目边界与依赖环；**未覆盖**：完整人工视觉焦点审查、真实 Provider |
| plan-detail.html | `tested` | 同上；return_to=today 经页面点击验证 |
| 两页合并 | `tested` | A 类、浏览器 B 类和 API 边界测试通过；本次 GPT 二审已独立复跑通过，但真实 Provider 与完整人工视觉审查仍未验证，暂不升级为 `e2e-real-pass` |

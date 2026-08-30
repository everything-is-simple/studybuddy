# StudyBuddy 前端契约审计清单

> 状态：`completed / scoped browser-pass`
> 更新：2026-08-30
> 目的：在不改变后端 API、数据库 schema 或能力边界的前提下，收口原生多页前端的路由、字段、状态、错误、响应式、键盘和隐私契约。

## 1. 审计规则

每个页面必须逐项确认：

- 页面文件存在，并可从 `/app/` 访问；
- 页面调用的 endpoint、HTTP method、请求头和 JSON 字段与正式后端一致；
- 响应字段和状态值来自正式 API，不使用历史字段猜测；
- loading、empty、ready、failed、retry 和必要的 draft/stale/pending_review 状态可见；
- 写操作有重复提交保护、成功/失败反馈和安全重试；
- 窄屏 360/390px 无非预期横向滚动，键盘焦点可见且顺序合理；
- DOM、URL、错误提示和日志不包含路径、SQL、secret、token、traceback、raw provider response、答案 key 或不应公开的正文。

完成标记必须区分：`implemented`、`browser-pass`、`scoped-pass`、`not_verified`，不能只用“页面存在”作为完成证据。

## 2. 当前页面盘点

| 计划任务 | 当前入口 | 当前判断 | 下一步 |
|---|---|---|---|
| 今天 | `today.html` | 正式静态页已通过当前基线 | 后续仅处理首页聚合/主行动产品决策 |
| 计划 | `plans.html` + `plan-detail.html` | 列表与详情已拆分并通过首批证据 | 继续保持来源状态与安全回退 |
| 资料库 | `materials.html` | 导入/搜索/生命周期已通过静态页证据 | 后续能力按路线门禁推进 |
| 材料详情 | `material-detail.html` | 详情/导出/问答跳转已通过静态页证据 | citation detail 仍为 legacy-only |
| 问答 | `qa.html` | thread/索引/问答已通过静态页证据 | citation detail 面板仍为 legacy-only |
| 笔记 | `notes.html` + `note-detail.html` | 列表与详情已拆分并通过首批证据 | 写操作仍保留 legacy-only 边界 |
| 卡片 | `cards.html` | 读取/来源状态已通过静态页证据 | 创建/生成/复习写操作仍 legacy-only |
| 练习 | `exercises.html` + `practice-session.html` | 读取与首批 session 流程已通过证据 | 完整 review/feedback 仍待后续切片 |
| 练习会话 | `practice-session.html` | 独立页面已完成首批拆分 | 继续补齐后续 review/feedback 行为 |
| 练习结果 | `practice-result.html` | 独立页面已完成首批拆分 | 保持 nested summary 与隐私边界 |
| 复盘 | `review.html` + `practice.html` | `review.html` 首批读取/来源边界已完成 | mark-mistake/feedback/redo 完整 UI 待后续 |
| 课堂采集 | `capture.html` | 已有 fake/loopback 限定路径 | 审计上传/转写/确认状态 |
| 报告 | `reports.html` + `classroom.html` | `reports.html` 已完成只读列表页 | 导出/完整审计等待 B3 |
| 系统设置 | `settings.html` + `settings-provider.html` | 只读 Provider/readiness 状态页已完成 | Provider 写入/connection-test 未批准 |
| 任务 | `tasks.html` | 只有单任务详情，无全局列表 API | 明确“尚无全局列表”的限制 |

## 3. 本次实现差异记录

### 3.1 设计文档与正式实现

- **已对齐**：`backend/app/static/` 实际包含 21 个正式页面，覆盖 `frontend-plan.md` 目标树中的今天、计划、资料、问答、笔记、练习、复盘、课堂采集、报告、设置和任务页面；所有正式页面均可从 `/app/` 访问。
- **已对齐**：正式页面的 API 调用经共享请求层处理；自动审计结果为 21 个页面、152 条后端路由、0 个 endpoint/直接 fetch/旧字段/CSS token 发现项。
- **已对齐**：`tokens.css`、`app.css`、`state.js`、`shell.js` 已在正式静态页面使用；未发现 HTML inline style、未定义 CSS token 或缺少 page scope 的 API 页面。
- **已修复的实现差异**：fixture 定义了 `capture.status=review_required` 与 `task.status=queued`，但 `state.js` 原先缺少这两个用户文案。已补齐为“需要复核”和“排队中”，并由契约测试确认。
- **仍存在的设计边界**：`reports.html` 当前是只读列表/预览范围，报告导出/完整审计仍受 B3 门禁约束；Provider 配置写入、真实 ASR/OCR、live delivery、系统级 screen reader 和无界长时稳定性没有因页面存在而完成。
- **未执行的可视化项**：本次环境没有可用的 `@瀏覽器`、`@電腦`、`Visualize` MCP 工具，因此未完成带截图的人工视觉检查；已执行仓库 Playwright 的 DOM、响应式、焦点、触控尺寸和隐私断言，不能将其等同于人工视觉验收。

### 3.2 路线图/状态文档与实现

- **已对齐**：`PHASE_ROADMAP.md`、`PROJECT_PROGRESS_REPORT.md`、`STATUS.md` 和 `TODO.md` 对 Phase 9A/9B/9C 限定范围完成、Phase 9D 部分立项 scoped closeout、Phase 10 local-v1 scoped closeout 的当前结论与代码/测试证据一致；不能扩大为全局 `real-pass`。
- **发现文档漂移**：`frontend-plan.md` 的旧快照段落仍写“材料管理已有旧 workspace，待拆屏”“计划/笔记/报告/任务前端缺页”，并保留 A3-1 的“仅四个页面”和 A3-2 的“下一步进入 A3-3”措辞；这些与当前 21 页正式实现、A3-PAGES/A3-VISUAL/A4 声明和 126 项浏览器基线不一致。该差异已在本文件记录，后续应清理旧叙述，避免被误读为当前待办。
- **发现文档口径风险**：`TODO.md` 顶部仍有“前端不代表完整产品化页面架构或 Neutral Modern 视觉系统已经完成”的历史性概括，但同一文件和 `STATUS.md` 已声明 A3-VISUAL 在限定范围完成。准确口径应是“限定范围 scoped browser-pass，不代表 deferred capability 或全局 real-pass”，而不是“视觉系统尚未完成”。
- **路线未完成项保持有效**：`frontend-plan.md` 的缓存/刷新策略、首页聚合 API、Provider 配置写入、capture 命名决策、真实 ASR 资料、B3/B4 和 D0/D1 等开放项没有被本次页面存在性或测试结果关闭。

### 3.3 测试与用户端到端证据

- 契约审计：通过，21 页面、152 路由、0 发现项。
- 源码尺寸检查：通过。
- 后端全套：`421 passed, 2 skipped`；skip 为默认关闭的 opt-in 真实 Provider smoke。
- 浏览器全套：`126 passed, 3 skipped`，共 129 项；skip 为默认关闭的 opt-in 真实 Provider UI smoke。
- 用户端到端：通过仓库 Playwright 的导入、材料生命周期、Q&A、多材料问答、计划、笔记、练习、课堂采集、跨页导航、错误恢复和旧入口兼容场景；完整套件第二次串行运行稳定通过。
- 稳定性备注：第一次完整浏览器串行运行出现 1 个 Phase 9C 时序失败，单独重跑该规格和目标用例通过，第二次完整运行全通过；这属于残余的长套件时序风险，后续仍应关注，不把一次重跑结果解释为无风险保证。

## 4. 已发现的高风险类别

### 共享层

- [x] `api.js` 对字符串 JSON body 自动补 `Content-Type: application/json`；保留调用方显式 header。
- [x] `api.js` 统一解析安全 detail、HTTP status 和 `x-request-id`。
- [x] `api.js` 增补 Provider、检索、来源、任务、编辑保护、幂等和导出错误映射。
- [x] A3-FC-1 首轮自动扫描已发现并修复 capture 直连 `fetch`、材料上传和 Q&A 写操作缺少 retry 文案；Q&A 已改用正式的材料级 index 路由。
- [x] 为可取消请求统一接入 `AbortSignal`：所有有 API 的页面使用 `setPageScope()`，`api.js` 自动追踪请求，`pagehide` 统一取消；上下文切换后的渲染正确性仍由 A3-FC-3 验证。
- [x] `shell.js` 补齐报告、任务、系统设置入口，并实现可访问的移动端“更多”导航。
- [x] 新增 `css/tokens.css` 作为唯一设计 token 来源，所有 21 个正式静态页面已加载；`app.css` 不再重复声明 token。
- [x] `app.css` 补齐当前页面已使用的状态 token，消除未定义 CSS 变量。
- [x] 清理 HTML `style=""`；将通用间距、dialog、隐藏 input、inline code、列表缩进和 skeleton 尺寸迁入共享 CSS。业务页面仍保留局部布局 CSS，完整组件视觉统一属于 A3-VISUAL。
- [x] 新增 `browser_frontend_shared_layer.spec.js`，验证 tokens、无 HTML inline style、移动端 ARIA 导航、自动幂等头和请求取消。

### 页面契约

- [x] 用脚本提取静态页面 endpoint，与 FastAPI route inventory 做存在性比对；脚本：`backend/scripts/audit-frontend-contract.py`。
- [x] 对关键资源建立字段/状态 fixture：capture、plan、note、practice、report、task。
- [x] 对每个写操作提供统一 Content-Type、Idempotency-Key、失败重试和重复点击基础策略；核心三页已完成逐页回归。
- [x] **A3-FC-3-2**：已统一 `source_status`、`verification_status`、`pending_review`、`uncertain`、`stale` 等状态的显示文案，并完成正式页面的 `sbState` 迁移；采集/报告/系统页面的 lifecycle/source 矩阵已纳入专项证据。
- [x] 删除核心三页旧字段名和旧状态判断；禁止页面兼容未知字段而掩盖契约漂移。
- [x] **A3-FC-3-2**：正式页面已补齐 stale/failure/source-lifecycle、360–1920 宽度、键盘与隐私 DOM 浏览器矩阵；`audit-frontend-contract.py --strict` 与专项治理测试通过。

### 后续阶段边界

- **A3-PAGES：** `plan-detail.html`、`note-detail.html`、`practice-session.html`、`practice-result.html`、`review.html`、`reports.html`、`settings.html` 的正式任务页拆分及其独立回归。现有混合页面继续作为兼容入口；后续能力仍须遵守 B0-B4 门禁。
- **A3-VISUAL（已完成声明范围）：** 所有正式 `/app` 页面使用 Neutral Modern tokens；共享 card、button、badge、notice、dialog、focus、grid 组件和 360–1920 视觉/触控验收已通过。它不扩大任何 deferred capability。

## 4. 静态页能力冻结

`frontend-static-capability-matrix.md` 是 A3-FC-3-2 的唯一静态页面能力口径；`frontend-static-failure-retry-matrix.md` 是失败、重试和安全 browser evidence 的唯一索引。两者共同防止把旧 `/legacy` 或后端 API 证据错误写成 `/app` 已迁移操作。

## 5. 当前阶段分工

以下工作都属于 **A3-FC 前端契约与架构收口**，但拆成三个可验收子阶段，避免混在一起：

- **A3-FC-1（本轮完成首版）：** 自动扫描 endpoint、直接 fetch、旧字段/状态、CSS token、写操作 retry；建立资源状态 fixture 和自动化测试。
- **A3-FC-2（共享层）：** 收口 `api.js`、`shell.js`、`app.css`，包括 AbortController、幂等策略、统一状态组件、移动端“更多”导航和共享视觉 token。
- **A3-FC-3-2（逐页）：** 已完成全部正式静态页面的 response/状态/错误/安全审计与 browser 矩阵；当前 A3-FC 已按声明范围关闭。
- **A3-PAGES（已完成首批声明范围）：** 拆分正式页面，不再把新功能混入旧页面；后续功能仍须遵守 B0-B4 门禁。
- **A3-VISUAL（已完成声明范围）：** Neutral Modern 视觉统一、共享组件收敛和 360–1920 视觉验收已通过，不改变 API 或业务行为。

## 6. 执行顺序与门禁

1. **A3-FC-1：** 页面/API/字段/状态/错误审计与自动化 route 检查已完成。
2. **A3-FC-2：** `api.js`、`shell.js`、`app.css` 共享层收口及 focused tests 已完成。
3. **A3-FC-3-2：** 正式页面的状态、stale/failure/source-lifecycle、360–1920、键盘和隐私矩阵已通过，A3-FC 按声明范围关闭。
4. **A3-PAGES：** 首批独立页面已按任务拆分，每页单独接入正式 API，不新增临时端点。
5. **A3-VISUAL：** Neutral Modern 视觉统一和局部 CSS 收敛已完成；不扩大为 deferred capability。
6. **收口：** 当前完整 backend/browser、源码尺寸和 diff 检查通过；后续工作转入 Practice 增量切片与 B0-B4 门禁。

## 7. 明确不在本阶段

- 不引入 React/Vue/Vite；
- 不修改 schema、migration、后端业务语义或错误码；
- 不接入真实 ASR/OCR、真实外发或新的 Provider；
- 不把 fake/loopback/dry-run 标记为 real-pass；
- 不删除旧入口，直到新页面具有可回退的浏览器证据。

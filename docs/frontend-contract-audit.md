# StudyBuddy 前端契约审计清单

> 状态：`in_progress / A3-FC`
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
| 今天 | `today.html` | 已有 API 灰盒 | 接入统一 shell/状态组件，确认默认主行动 |
| 计划 | `plans.html` | 列表与详情暂合并 | 拆 `plan-detail.html` |
| 资料库 | `materials.html` | 已有导入/搜索/生命周期 | 契约字段和错误码审计 |
| 材料详情 | `material-detail.html` | 已有详情/导出 | 审计 citation/source 状态 |
| 问答 | `qa.html` | 已有 thread/引用/索引入口 | 统一取消、错误和 stale 处理 |
| 笔记 | `notes.html` | 列表与详情暂合并 | 拆 `note-detail.html` |
| 卡片 | `cards.html` | 已有限定范围页面 | 统一状态 token 和来源状态 |
| 练习 | `exercises.html` | 已有练习集页面 | 与 practice session 边界对齐 |
| 练习会话 | — | 缺少独立页面 | 新建 `practice-session.html` |
| 练习结果 | — | 缺少独立页面 | 新建 `practice-result.html` |
| 复盘 | `practice.html` | 会话和错题暂合并 | 新建 `review.html`，保留回退入口 |
| 课堂采集 | `capture.html` | 已有 fake/loopback 限定路径 | 审计上传/转写/确认状态 |
| 报告 | `classroom.html` 内嵌区域 | 不是独立产品页面 | 新建 `reports.html` |
| 系统设置 | `settings-provider.html` | 只有 Provider 状态 | 新建 `settings.html`，只开放正式契约动作 |
| 任务 | `tasks.html` | 只有单任务详情，无全局列表 API | 明确“尚无全局列表”的限制 |

## 3. 已发现的高风险类别

### 共享层

- [x] `api.js` 对字符串 JSON body 自动补 `Content-Type: application/json`；保留调用方显式 header。
- [x] `api.js` 统一解析安全 detail、HTTP status 和 `x-request-id`。
- [x] `api.js` 增补 Provider、检索、来源、任务、编辑保护、幂等和导出错误映射。
- [x] A3-FC-1 首轮自动扫描已发现并修复 capture 直连 `fetch`、材料上传和 Q&A 写操作缺少 retry 文案；Q&A 已改用正式的材料级 index 路由。
- [x] 为可取消请求统一接入 `AbortSignal` 入口；`api.js` 自动追踪无外部 signal 的请求，`pagehide` 统一取消；逐页 stale 防护仍由 A3-FC-3 验证。
- [x] `shell.js` 补齐报告、任务、系统设置入口，并实现可访问的移动端“更多”导航。
- [x] `app.css` 补齐当前页面已使用的状态 token，消除未定义 CSS 变量。
- [ ] 将各页面重复的局部状态样式迁移到共享 CSS，减少 inline style 和 raw color；共享状态基础样式已先建立。

### 页面契约

- [x] 用脚本提取静态页面 endpoint，与 FastAPI route inventory 做存在性比对；脚本：`backend/scripts/audit-frontend-contract.py`。
- [x] 对关键资源建立字段/状态 fixture：capture、plan、note、practice、report、task。
- [x] 对每个写操作提供统一 Content-Type、Idempotency-Key、失败重试和重复点击基础策略；逐页行为验证仍由 A3-FC-3 完成。
- [ ] 统一 `source_status`、`verification_status`、`pending_review`、`uncertain`、`stale` 等状态的显示文案。
- [ ] 删除旧字段名和旧状态判断；禁止页面兼容未知字段而掩盖契约漂移。

### 视觉与可访问性

- [ ] 所有页面使用 Neutral Modern tokens，不在页面继续新增 raw hex。
- [ ] 统一 card、button、badge、notice、dialog、focus 和 grid 组件。
- [ ] 逐页完成 360、390、430、600、768、820、1024、1366、1440、1920 宽度验收。
- [ ] 确认所有主操作触控命中区至少 44px，状态不只依赖颜色。
- [ ] 在视觉迁移前不删除现有行为回归路径。

## 4. 当前阶段分工

以下工作都属于 **A3-FC 前端契约与架构收口**，但拆成三个可验收子阶段，避免混在一起：

- **A3-FC-1（本轮完成首版）：** 自动扫描 endpoint、直接 fetch、旧字段/状态、CSS token、写操作 retry；建立资源状态 fixture 和自动化测试。
- **A3-FC-2（共享层）：** 收口 `api.js`、`shell.js`、`app.css`，包括 AbortController、幂等策略、统一状态组件、移动端“更多”导航和共享视觉 token。
- **A3-FC-3（逐页）：** 按页面检查 response 字段、状态映射、loading/empty/ready/failed/retry、键盘、窄屏和隐私；每页修复后单独回归。
- **A3-PAGES（依赖 A3-FC-2/3）：** 拆分正式页面，不再把新功能混入旧页面。
- **A3-VISUAL（最后）：** 只做 Neutral Modern 视觉统一，不改变 API 或业务行为。

## 5. 执行顺序与门禁

1. **A3-FC-1：** 完成页面/API/字段/状态/错误审计表和自动化 route 检查。
2. **A3-FC-2：** 完成 `api.js`、`shell.js`、`app.css` 共享层收口及 focused tests。
3. **A3-FC-3：** 补齐页面状态、失败恢复、重复提交、stale、键盘、窄屏和隐私测试。
4. **A3-PAGES：** 按任务拆分缺失页面，每页单独接入正式 API，不新增临时端点。
5. **A3-VISUAL：** 共享层和行为门禁通过后，完成 Neutral Modern 视觉统一。
6. **收口：** 运行完整 backend、完整 browser、源码尺寸和 diff 检查，并同步 `frontend-plan.md`、`TODO.md`、`ROADMAP_CAPABILITIES.md`、`STATUS.md`。

## 5. 明确不在本阶段

- 不引入 React/Vue/Vite；
- 不修改 schema、migration、后端业务语义或错误码；
- 不接入真实 ASR/OCR、真实外发或新的 Provider；
- 不把 fake/loopback/dry-run 标记为 real-pass；
- 不删除旧入口，直到新页面具有可回退的浏览器证据。

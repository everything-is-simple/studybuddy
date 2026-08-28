# StudyBuddy 前端产品化设计计划（v2，可编辑）

> **文档性质**：这是 StudyBuddy 前端的产品设计、信息架构、低保真 draft 草图、接口映射与实施门禁，不是已完成的前端实现声明。
>
> **事实基线（2026-08-30；A3-1 已更新）**：后端 schema v13；local single-process / single-instance / SQLite / local-disk v1；最近一次完整 backend 基线为 413 passed、2 skipped（默认关闭的真实 Provider smoke）。A2.X（repository/main/migrations/providers 的行为保持型拆分）已完成，Phase 9A/9B/9C 已在各自限定范围完成，Phase 9D 的部分立项范围已 scoped closeout，Phase 10 Gate J 已通过。A3-1 已建立 `backend/app/static/` 并由 app factory 挂载到 `/app`；旧根路由 `/` 仍由 `backend/app/api/web.py` 返回内嵌 `templates/index.html`，处于迁移兼容期。
>
> **状态判定优先级**：实施状态、测试基线与支持边界以 `STATUS.md` 和 `TODO.md` 为准；`PHASE_ROADMAP.md` 与 `ROADMAP_CAPABILITIES.md` 规定顺序和门禁；本计划只映射前端行为，不能提升任何后端能力等级。整体完成度百分比仅是阶段性估算，现有历史文档存在 55%–60% 与约 65% 两种口径，A3 实施不依赖该数字。

## 0. 本次修订结论

旧版计划把前端范围冻结在“资料 → Q&A → Provider → 课堂采集”，并且曾把部分后端能力写成“尚未完成”。这已经落后于当前系统：Phase 8、9A、9B、9C 已在限定范围完成，Phase 9D 的确定性采集/转写、报告、dry-run 交付和相关 UI/恢复门禁已完成 scoped closeout，Phase 10 Gate J 还补齐了显式任务、重试/取消、诊断和运行状态能力。

本版改为：

1. **先建立学习产品壳，再按用户任务拆屏**，不把所有能力塞回一个 workspace。
2. **把当前已具备的能力全部纳入产品导航和页面规划**，但严格区分"后端已实现""前端待产品化""真实能力未验证"。
3. **所有 AI 生成物、转写、引用、报告都 draft-first / 可追溯 / 可回退**；前端不能用静态卡片伪造成功。
4. **draft 草图先于视觉精修**：先验证任务路径、信息优先级和状态，再绑定 Neutral Modern 设计系统实现。
5. **已验证能力立即集成，未实现能力先预留**：现有后端契约已通过对应 gate 的能力，在正式前端迁移时优先接入；真实 OCR/ASR、真实 live delivery、通用 Provider/model、全局 production real-pass 仍是限制，预留界面必须由 capabilities/状态码驱动。
6. **不改变既定 roadmap 顺序**：前端按 `ROADMAP_CAPABILITIES.md` 的 A3 → A4 → B0 → B1 → B2 → B3 → B4 → D0 → D1 顺序配合；学习产品页面的增量接入属于页面迁移切片，不新增或重排路线阶段。本文件只规定前端如何配合，不重新排序后端路线。

### 前后端协同原则（2026-08-30 同步）

**前端实现时考虑后端**：
- 为后端未来能力预留 UI 占位和接口抽象
- 未实现能力必须明确标注状态（"配置中"/"尚未验证"/"不可用"）
- 不伪造成功状态，不隐藏能力边界

**后端实现时考虑前端**：
- 提供清晰的能力状态查询 API（`/api/capabilities`、task status 等）
- 错误响应包含稳定错误码和安全的用户可见消息
- 新能力通过 C0-C6 门禁后立即提供前端集成所需的契约文档

**增量集成策略**：
- 后端能力已验证 → 立即集成到前端 UI，移除"尚未验证"标注
- 后端能力未实现 → 前端预留界面但诚实标注，避免用户混淆
- 不因"前端未完成"阻塞后端能力实现，也不因"后端未实现"停止前端框架建设

此原则适用于 A3/A4 的原生前端交付，以及 B0-B4 能力流水线和 D0-D1 桌面验证；页面可提前保留入口，但只有对应后端门禁通过后才开放真实动作。

## 0.1 当前系统进度与最近变化（供前端实施读取）

截至本次审计，系统应按以下口径报告：

| 最近变化 | 当前事实 | 前端动作 |
|---|---|---|
| A2.X 收口 | 4 个核心大文件已完成行为保持型拆分；`main.py` 为兼容 façade，模板已移到 `backend/app/templates/index.html`；schema v13、413 passed/2 skipped | A3 只处理正式静态资源与前端壳，不再把后端大文件拆分算作前端工作 |
| Phase 7 收口 | embedding/indexing/retrieval mode 已实现；Mistral `mistral-embed` 仅在精确 gateway/model 配置通过真实 gate | 前端显示 lexical/vector/hybrid、索引状态和失败重试；verified 标签只绑定精确配置，不写成通用可用 |
| Phase 8 收口 | Cards/Exercises 在 deterministic fake-provider、Chromium、backup/restore 范围完成 | 卡片/练习页面优先接入；真实 Provider generation 和 short-answer 人工复核仍显示受限状态 |
| Phase 9A–9C 收口 | 计划/节奏/笔记、练习/错题/薄弱点/冲刺已有限定范围的 backend/API/UI/恢复证据 | 目标、计划、笔记、练习、复盘页面直接消费已冻结 API，并保留 draft/pending_review/source status |
| Phase 9D scoped closeout | deterministic fake/loopback capture/transcription、确认后 S2 接入、脱敏报告、delivery off/dry-run、相关 API/UI/lifecycle/restore 已通过；真实 OCR/ASR 与 live delivery 未立项 | 课堂/报告页面立即迁移已验证 fake/loopback/dry-run 路径；真实动作由 capabilities 与 gate 状态禁用，不能显示“已发送”或“真实转写” |
| Phase 10 Gate J | local v1 上线收口；只有显式 `embedding_index` task 可经 runner 执行，支持状态/进度/lease/retry/cancel/diagnostics | 设置/系统状态页接入 readiness、diagnostics、task 状态；Q&A、生成、OCR/ASR、报告、delivery 不得误标后台任务 |
| A3 尚未开始 | 仍是单页 workspace，无正式 static root/mount；目标拆屏尚不存在 | 先冻结现有行为回归，再建立唯一 static root 与独立页面；不得声称正式多页前端已交付 |

**进度结论**：后端与限定范围的产品能力已明显领先于正式前端架构。前端当前不是“等待后端完成”，而是“把已验证 API/UI 行为从内嵌 workspace 迁移到正式产品壳，同时为真实能力和未批准操作保留状态位”。整体完成度不作为本计划的实施门槛：`STATUS.md`/`TODO.md` 记为约 65%，而较早的阶段文档仍为 55%–60%；两者都不是测试通过率，也不是全局 `real-pass`。

## 1. 产品目标与用户任务

### 1.0 当前产物基线（以 `backend/app/templates/index.html` 为准）

本节是当前实现快照，不是目标信息架构：

- `/` 仍由 `backend/app/api/web.py` 直接返回内嵌 `INDEX_HTML`；A3-1 已确认正式 static root 为 `backend/app/static/`，由 app factory 以 `StaticFiles(directory=..., html=True)` 挂载到 `/app`。
- 当前只有一个约 240 行 HTML 行结构、约 156 KB 的单页 workspace。页面同时包含材料导入/批量导入、搜索/筛选/分页、回收站、材料详情/下载/导出、Q&A、卡片与练习、学习计划与节奏、练习反馈/冲刺、资料笔记、课堂采集/转写确认、报告预览/导出/交付审计。
- 当前真实交互通过页面内 `fetch()` 调用后端 API；已保留重复提交保护、幂等键、过期响应保护、失败提示、重试入口、citation 定位、草稿确认/拒绝/归档和文件下载等行为。
- 旧入口导航仍是同页锚点（材料、问答、卡片与练习、练习反馈、学习计划、资料笔记、课堂与报告），不是独立页面路由；A3-1 新增的 `/app/` 灰盒已提供今天、资料、材料详情、问答四个独立页面，但尚未替换旧入口，也没有任务中心、Provider 配置写入页或系统诊断页。
- 当前样式仍是旧 workspace 的 system sans + 灰蓝色 raw hex 规则，与 Neutral Modern 的 token、组件、accent 使用约束尚未绑定。Neutral Modern 只能作为后续迁移目标，不能在当前产物状态中写成已完成。
- 当前课堂采集明确触发的是 `deterministic` 转写；报告页面明确展示脱敏快照，delivery 仅允许默认 off/allowlisted dry-run，live 仍固定拒绝。不得把这些 UI 存在误写成真实 ASR 或 live delivery 已通过。

因此，后文出现“必须提供”“目标页面”“A3/A4/B0-B4/D0-D1”时，均表示按路线门禁推进的迁移目标；出现“当前 UI/当前产物”时，均以本节事实为准。迁移期间优先保留上述已有行为，再逐页迁移并补回归测试。

### 1.1 核心用户

- 主要用户：个人学习者，管理课程资料、学习计划、笔记、练习和复习反馈。
- 次要用户：需要查看学习进展和脱敏报告的教育者/家长；当前仅规划为本地只读报告使用者，不引入多用户权限。
- 实现维护者：需要从页面状态直接定位稳定错误码、任务 ID 和安全操作结果。

### 1.2 StudyBuddy 必须让用户完成的闭环

```text
导入材料
  → 解析 / revision / chunk / 显式索引
  → 建立知识模块与学习目标
  → 创建并激活学习计划
  → 按节奏分配今日任务
  → 读笔记 / 问答 / 看引用
  → 卡片复习 / 练习 / 错题复盘
  → 冲刺复习（可选）
  → 课堂音频转写为 draft（仅在能力门禁允许时）
  → 生成脱敏报告快照（只读）
```

每一步都要能看到：当前状态、下一步动作、来源是否仍有效、失败如何重试，以及哪些内容还没有被用户确认。

## 2. 已具备能力盘点：后端事实 → 前端责任

| 能力域 | 当前后端事实 | 前端必须提供 | 当前 UI 状态 |
|---|---|---|---|
| 材料管理 | 单文件、批量/文件夹导入、列表、搜索、分页、软删/恢复/永久删除、原文/提取文本导出 | 资料库、导入反馈、回收站、详情、版本/来源状态、导出确认 | 已有旧 workspace，待拆屏 |
| AI 索引与检索 | lexical/vector/hybrid、显式 indexing、任务化 embedding index、retry/cancel、source lifecycle 过滤 | 索引状态、模式摘要、失败重试、不可引用状态 | 后端已具备，待统一 UI |
| Q&A | thread/history、scope、多材料、同步 ask、citation detail/定位、幂等、stale response 保护 | 对话页、材料范围、引用侧栏、重试与错误引导 | 旧 UI 已有，需产品化迁移 |
| Provider | capabilities、fake/demo、generic configured/unverified、精确 Provider evidence | Provider 状态和能力说明；若无安全配置写入 API，不做假设置表单 | 当前产物已显示能力状态；无配置写入/连接测试页 |
| 目标/模块/计划 | goal、knowledge module、plan/item、DAG dependency、状态转换、progress event、source links | 学习总览、模块页、计划详情、依赖和进度记录 | 后端已具备，前端缺页 |
| 学习节奏 | IANA timezone、daily/weekly rhythm、allocation、timeline/load/progress summary | 今日学习、周节奏、调整分配、超限/重复提示 | 后端已具备，前端缺页 |
| 笔记 | user note、block、module link、citation source link、AI draft、confirm/reject/archive、导出 | 笔记编辑器、块级来源、AI 草稿审阅、版本保护 | 后端已具备，前端缺页 |
| 卡片 | deck/card、AI draft、引用校验、confirm/reject/archive、review history | 卡组、卡片审阅、记忆结果、来源状态 | 后端已具备，前端缺页 |
| 练习 | exercise set、MC/TF/short answer、draft/ready、attempt、deterministic grading | 练习会话、提交、结果、简答待人工复核 | 后端已具备，前端缺页 |
| 错题/薄弱点 | mistake case、反馈、redo、archive、weak-point projection | 错题清单、反馈、再练、薄弱点摘要 | 后端已具备，前端缺页 |
| 冲刺复习 | cram goal、session、结果，且不改写 plan/progress/rhythm | 冲刺目标、限时练习、结果页 | 后端已具备，前端缺页 |
| 课堂采集 | capture session、音频资产、fake/loopback transcription、draft edit/confirm/reject/archive、S2 接入 | 上传、任务/转写状态、分段草稿、确认门 | 9D scope 后端/UI 部分已有，需正式拆页 |
| 报告 | report snapshot、daily/weekly/monthly/exam_alert、脱敏 preview/export | 报告列表、预览、导出、来源降级提示 | 后端已具备，前端缺页 |
| 交付 | 默认 off、allowlisted dry-run、live 仍拒绝、append-only delivery audit | 只显示安全审计和 dry-run；不显示“已发送” | 当前产物已有交付检查/审计；仍不是 live delivery |
| 任务/运行 | 单进程 task runner；approved `embedding_index` enqueue/read/cancel/retry；liveness/health/readiness/diagnostics | 全局任务状态、重试/取消、系统状态入口 | 后端已验证；当前产物仅有部分运行/交付状态表达，尚无正式任务/诊断页，A3/A4 迁移时立即接入；其它 task kind 必须显示“尚未接入任务运行器” |
| 备份/恢复 | operator CLI/manifest/verify/restore；不在浏览器暴露内部路径 | 只读运行状态与安全指引，不复制 CLI 管理面板 | 前端不纳入 MVP 操作面 |

## 2.1 前后端能力集成矩阵（实施时的单一判定口径）

| 前端能力状态 | 后端判定 | 页面表现 | 允许的动作 |
|---|---|---|---|
| `verified_available` | 对应 API、浏览器路径及必要恢复/隐私门禁已通过 | 正常入口、真实 loading/empty/error/success | 可调用已冻结 API；失败必须给出稳定错误码和 retry |
| `implemented_scoped` | 后端实现且有局部/限定范围证据，但不具备通用 real-pass | 正常入口 + “仅适用于当前验证范围”提示 | 仅调用限定范围；不扩展 provider/model/环境结论 |
| `reserved_not_enabled` | API/数据模型已预留，真实执行未实现或未批准 | 可见能力说明、禁用主动作、说明解锁条件 | 不能伪造成功；允许查看历史 draft/failed/audit |
| `not_available` | 后端没有正式 endpoint/契约 | TODO/占位，不进入成功路径 | 不猜字段、不造临时 endpoint |

集成优先级固定为：

1. A3 先接入 `verified_available` 的材料、索引、retrieval mode、Q&A、citation、导出和现有 failure contract。
2. 在 A3/A4 页面迁移切片中立即接入 Phase 8、9A、9B、9C 的已验证 API/状态；Phase 9D 已验证的 capture/dry-run 路径随 A4 接入，report 页面按 B3 的正式报告门禁接入。这是迁移集成，不是改变 roadmap 顺序。
3. 任务/诊断仅接入后端明确批准的 `embedding_index`；其它操作只显示状态/预留。
4. B1/B2/B4 未通过 C0-C6 前，页面只保留真实能力状态、draft/历史和禁用原因；B3 报告能力按其正式 gate 逐步扩展，不与 live delivery 绑定。

每次后端 gate 收口后必须同步三处：API contract（字段/错误/权限边界）、前端状态映射（可执行/禁用/历史）、浏览器验收路径（成功/失败/窄屏/键盘/隐私）。若三者缺一，前端不得移除限制标识。

## 3. 信息架构（目标产品）

> **当前产物映射**：下面的一级导航和文件树是 A3 之后的目标边界；当前所有能力仍位于 `/` 的单页 workspace 中。不要把目标文件已经存在、已经挂载或已经完成迁移写入状态报告。

### 3.1 一级导航

1. **今天**：今日计划、待处理草稿、最近材料、学习连续性与下一步。
2. **学习计划**：目标、知识模块、计划、节奏与计划进度。
3. **资料库**：材料、搜索、索引状态、回收站、材料详情。
4. **问答**：线程、材料范围、回答和引用。
5. **笔记**：用户笔记、来源块、模块归档、AI 草稿审阅。
6. **练习**：卡组、练习集、练习会话、结果。
7. **复盘**：错题、薄弱点、再练、冲刺复习。
8. **课堂采集**：音频采集、转写草稿与确认接入。
9. **报告**：本地脱敏报告快照与导出；交付审计为次级区域。
10. **系统设置**：Provider 能力/配置（仅在后端契约存在时）、运行状态、任务、隐私说明。

> 移动端不压缩全部导航：主导航保留“今天 / 计划 / 资料 / 练习”，其余进入“更多”抽屉；当前上下文必须保留。

### 3.2 页面文件原则

每个独立用户任务一个 HTML 文件；`index.html` 只作为“今天”入口，不承载全产品长页面。

```text
<正式静态根目录>/
├── index.html                     # 今天 / 总览（当前已落地于 backend/app/static/）
├── plans.html                     # 目标、模块、计划列表
├── plan-detail.html               # 单个计划、items、依赖、进度、节奏
├── materials.html                 # 资料库、搜索、索引、回收站入口
├── material-detail.html            # revision、来源、导出、进入问答
├── qa.html                         # thread、问答、citation
├── notes.html                      # 笔记列表与编辑
├── note-detail.html                # block、来源、draft 审阅
├── practice.html                   # 卡组、练习集、会话入口
├── practice-session.html           # 做题与提交
├── practice-result.html            # 结果、错题、反馈
├── review.html                     # 错题、薄弱点、冲刺目标
├── capture.html                    # 课堂采集、转写草稿、确认
├── reports.html                    # 报告快照、预览、导出、审计
├── settings.html                   # Provider/运行状态/任务/隐私
├── css/
│   ├── tokens.css
│   └── app.css
└── js/
    ├── api.js                     # fetch、错误映射、取消、request ID
    ├── shell.js                   # 壳、导航、drawer、toast、dialog
    ├── today.js
    ├── plans.js
    ├── materials.js
    ├── qa.js
    ├── notes.js
    ├── practice.js
    ├── review.js
    ├── capture.js
    ├── reports.js
    └── settings.js
```

**A3-1 结果**：正式 static root 已冻结为 `backend/app/static/`，app factory 挂载为 `/app`，当前提供 `index.html`、`materials.html`、`material-detail.html`、`qa.html` 以及共享 `css/app.css`、`js/api.js`、`js/shell.js`。旧 `/` 保留为迁移期兼容入口；缓存头/版本化刷新策略和何时切换 `/` 仍是 TODO。不得把 `/app/index.html` 的灰盒交付误写成四页完整功能迁移。

## 4. 低保真 draft 草图（先评审任务，再做视觉）

草图故意使用文字框和状态标签，不代表最终视觉；每张草图都要先验证“用户一眼知道下一步是什么”。

### Draft A：今天 / 总览

```text
┌──────────────────────────────────────────────────────────────┐
│ StudyBuddy                         今天  计划  资料  练习  ⋯ │
├──────────────────────────────────────────────────────────────┤
│ 早上好，继续你的学习                                          │
│ [继续：函数极限 · 第 2 项]  [查看计划]                        │
│                                                              │
│ ┌ 今日节奏 ───────────┐  ┌ 需要处理 ───────────────────────┐ │
│ │ 进度 2/4              │  │ ○ 1 个笔记草稿待确认            │ │
│ │ ██████░░ 50%         │  │ ○ 3 个练习待复盘                │ │
│ │ 预计 35 分钟          │  │ ! 1 个来源已不可用              │ │
│ └──────────────────────┘  └────────────────────────────────┘ │
│                                                              │
│ 最近材料                         Provider / 系统状态          │
│ [线性代数讲义] 可引用             [已配置 · 未验证]           │
│ [课堂记录 03-12] 正在索引         [索引任务 运行中]           │
└──────────────────────────────────────────────────────────────┘
```

**必须实现的状态**：首次空状态、未配置 Provider、索引运行中、待确认草稿、来源降级、任务失败可重试。不要显示虚构的学习天数或完成百分比；没有真实数据时用“尚未开始”。

### Draft B：计划详情

```text
┌──────────────────────────────────────────────────────────────┐
│ ← 学习计划      函数与微积分基础              [暂停] [更多]   │
│ 状态：进行中     本周 3/5 项     来源：2 个模块 / 4 份资料   │
├──────────────────────┬───────────────────────────────────────┤
│ 计划目录              │ 当前任务                              │
│ 01 极限 ─ 已完成      │ [第 2 项] 证明连续性                   │
│ 02 导数 ─ 进行中 ●    │ 依赖：极限 · 已满足                    │
│ 03 积分 ─ 未解锁      │ 来源：线性代数讲义 · p.12               │
│                      │ [开始学习] [记录进度] [问答]           │
├──────────────────────┴───────────────────────────────────────┤
│ 节奏：周一/三/五  ·  本地日期  ·  调整分配                     │
│ 进度事件：开始 / 部分完成 / 完成 / 跳过                         │
└──────────────────────────────────────────────────────────────┘
```

**关键规则**：DAG 依赖不可满足时必须解释；已确认/激活计划的编辑保护要转化为清晰提示；进度采用 append-only 事件，不提供“偷偷改历史”的控件。

### Draft C：资料库 + 材料详情

```text
┌──────────────────────────────────────────────────────────────┐
│ 资料库                                      [导入资料]        │
│ [搜索材料________________] [全部状态⌄] [回收站]              │
├──────────────────────────────────────────────────────────────┤
│ 名称                 状态          revision    更新时间       │
│ 线性代数讲义.pdf     可引用        current     今天           │
│ 课堂记录 03-12       正在索引      current     5 分钟前       │
│ 旧讲义                已删除        —           —              │
└──────────────────────────────────────────────────────────────┘

详情：
┌───────────────┬──────────────────────────────────────────────┐
│ 材料信息        │ 提取内容 / spans                            │
│ 生命周期状态    │ [正文定位区域]                              │
│ revision 状态   │                                              │
│ [进入问答]      │ [导出文本] [导出原件] [重建索引]              │
└───────────────┴──────────────────────────────────────────────┘
```

导入流程必须区分：选择文件 → 上传成功 → 提取成功/失败 → 索引中 → 可引用。回收站删除与永久删除必须有影响说明；`deleted`、`purged`、`stale` 不得显示成正常引用。

### Draft D：Q&A / citation

```text
┌──────────────────────────────────────────────────────────────┐
│ 问答       线程：极限复习                 [新建对话]           │
├──────────────┬───────────────────────────────┬───────────────┤
│ 对话列表      │ 消息时间线                     │ 引用           │
│ 极限复习 ●    │ 你：ε-δ 定义如何理解？         │ [ctx-…]        │
│ 导数练习      │                                │ 线性代数讲义   │
│               │ AI：……                         │ revision 2     │
│ 材料范围      │ [引用 1] [引用 2]               │ [定位正文]     │
│ ☑ 讲义        │                                │ 可用状态：valid │
│ ☐ 课堂记录    │ ┌───────────────────────────┐ │               │
│               │ │ 输入问题________________ │ │               │
│               │ │                    [发送] │ │               │
│               │ └───────────────────────────┘ │               │
└──────────────┴───────────────────────────────┴───────────────┘
```

窄屏顺序：线程抽屉 → 消息 → 固定底部输入 → 引用可展开面板。发送期间禁止重复提交；切换 thread/scope 后旧响应不能覆盖当前内容；引用无效时显示原因和回到材料入口。

### Draft E：笔记 / AI 草稿审阅

```text
┌──────────────────────────────────────────────────────────────┐
│ 笔记：极限的直觉                         [保存] [导出]         │
│ 模块：函数与微积分基础     状态：用户编辑                      │
├─────────────────────────────┬────────────────────────────────┤
│ 内容块                        │ 来源                            │
│ [标题] ε-δ 的直觉             │ 讲义 p.12  valid                │
│ [段落] ……                    │ 课堂记录 stale                  │
│ [待确认 AI 草稿]              │ [查看 citation]                 │
│ [添加块]                      │                                  │
├─────────────────────────────┴────────────────────────────────┤
│ 草稿操作：[编辑] [确认接入] [拒绝] [归档]                      │
└──────────────────────────────────────────────────────────────┘
```

AI 草稿与用户内容视觉分层；确认前不写入正式用户笔记语义；用户已编辑内容不可被生成动作静默覆盖。

### Draft F：练习 / 错题 / 冲刺

```text
┌──────────────────────────────────────────────────────────────┐
│ 练习                         [开始练习] [创建卡组]             │
│ 卡组：微积分基础（12 张）     练习集：极限（8 题）              │
├──────────────────────────────┬───────────────────────────────┤
│ 今日练习                      │ 薄弱点                          │
│ 进度 3/8                      │ 1. ε-δ 表述                     │
│ [选择题内容]                 │ 2. 单调性判断                   │
│ ○ A  ○ B  ○ C  ○ D           │ [去复习] [创建冲刺目标]           │
│ [提交答案]                   │                                 │
├──────────────────────────────┴───────────────────────────────┤
│ 结果：正确 / 错误 / 待人工复核                                  │
│ 错题：[查看原因] [添加反馈] [再练一次] [归档]                    │
└──────────────────────────────────────────────────────────────┘
```

`short_answer` 只能显示“待人工复核”或后端真实状态，不生成确定分数。答案 key 不进入普通列表或前端日志。冲刺练习必须明确它不会改写正式计划进度。

### Draft G：课堂采集 / 转写确认

```text
┌──────────────────────────────────────────────────────────────┐
│ 课堂采集                                    [新建采集]         │
│ 标题 [________________] 课程 [____________]                  │
│ [选择音频]  上传状态：未上传 / 已上传                          │
├──────────────────────────────────────────────────────────────┤
│ 转写能力：未验证 / 可用范围 / 尚不可用                         │
│ [开始转写]（未满足门禁时禁用，并说明原因）                      │
├──────────────────────────────┬────────────────────────────────┤
│ 转写草稿（draft）              │ 复核清单                       │
│ 00:00  [文本可编辑]            │ ! uncertain 片段 2             │
│ 00:18  [文本可编辑]            │ 时间戳：Provider 未提供         │
│ 01:02  [文本可编辑]            │ confidence：Provider 未提供    │
│ [保存修订]                     │ [确认接入资料] [拒绝] [归档]     │
└──────────────────────────────┴────────────────────────────────┘
```

绝不把上传成功渲染为转写成功。只有用户明确确认后才进入 capture material 的 S2 revision/chunk/retrieval 链路。真实 OCR/ASR 未通过 W0/W1/W2 时，页面必须诚实禁用真实动作。

### Draft H：报告 / 系统状态

```text
┌──────────────────────────────────────────────────────────────┐
│ 报告                       [生成快照] [导出 JSON/Markdown]     │
│ 类型 [周报⌄]  日期窗口 [本地时区]  状态：只读                   │
├──────────────────────────────┬────────────────────────────────┤
│ 学习摘要                      │ 来源与限制                      │
│ 计划进度：有数据/无数据       │ 资料已删除：1                   │
│ 练习反馈：……                 │ 数据窗口：本地日期               │
│ 脱敏摘要                      │ 无法推断：未提供的事实           │
├──────────────────────────────┴────────────────────────────────┤
│ 交付审计：delivery off · dry-run 可审计 · live 未批准           │
└──────────────────────────────────────────────────────────────┘
```

报告是快照，不是实时医疗/教育评估结论；无数据使用安全零值或“无数据”，不得虚构表现。交付区域只表达审计状态，不提供伪造的发送成功。

## 5. 页面状态合同

每个页面都必须有以下语义状态，并使用文字、图标/结构和 `role=status` / `role=alert` 表达，不只依赖颜色：

- `loading`：请求进行中，主要重复操作禁用。
- `empty`：没有数据，提供唯一清晰的下一步。
- `ready`：可操作数据。
- `draft`：待用户编辑/确认，不能当成最终事实。
- `processing`：解析、索引、任务或转写进行中。
- `failed`：稳定中文错误说明、可重试动作、必要时显示安全 request/operation/task ID。
- `stale`：来源或索引需要更新，不能正常引用。
- `deleted` / `source_unavailable`：历史记录仍可见，但正文/引用不可用。
- `pending_review` / `uncertain`：需要人工复核，不能自动升级为正确。
- `confirmed` / `active` / `completed` / `archived`：严格对应后端状态转换，不由前端自行猜测。

统一错误映射至少覆盖：未配置 Provider、配置无效、未验证、超时、网络失败、额度/限流、检索为空、来源失效、任务失败、任务过期、编辑保护、幂等冲突、导出失败、数据不可用。

## 6. 交互与响应式合同

### 6.1 响应式断点

必须验证 360、390、430、600、768、820、1024、1366、1440、1920px：

- 360–430：4 列逻辑；侧栏/引用变为抽屉或底部面板；表格变为信息行；输入和主操作保持 44px 命中区。
- 600–834：8 列过渡；计划、材料详情、练习结果采用上下或 1–2 栏布局，不横向挤压。
- 1024–1180：桌面双栏但不强行显示三栏；Q&A 优先保障回答和输入。
- 1280 以上：12 列，展示上下文侧栏和来源详情；不因宽屏增加无意义装饰。
- 1920：内容最大宽度受控，不能把信息拉成难读的长行。

### 6.2 交互基线

- API 请求统一经过 `api.js`，不在页面直接调用外部 Provider、本地程序、SQLite 或文件路径。
- 所有写操作支持 loading、成功、失败、重复点击保护；可重试动作使用新的安全请求上下文。
- 任务页只接入后端已批准的 task kind；当前仅 `embedding_index` 可由 runner 执行，Q&A、生成、OCR/ASR、报告、交付不能伪装成后台任务。
- URL 只携带非敏感 ID（material/thread/scope/citation/plan/session），不携带 key、原文、绝对路径或 raw response。
- 允许浏览器刷新后从服务端恢复非敏感上下文；不把回答、密钥、原文敏感内容放进 localStorage。
- 所有可检查主元素使用稳定 `data-od-id`；不把 viewport、平台选择器、设计旋钮、目标数徽章放进产品 UI。

## 7. 后端契约门禁（实施前必须完成）

| 门禁 | 必须核实/补齐的内容 | 结论 |
|---|---|---|
| A3-1 静态资源 | 正式目录、`StaticFiles` mount、HTML 路由、缓存/刷新策略、旧 `/` 兼容 | 已确认并实现：`backend/app/static/` → `/app`；缓存细则与旧入口最终切换仍 TODO |
| A3-2 页面读 API | 总览聚合是否需要新安全 endpoint，或由现有多个 API 组合 | 当前可组合，但需避免首屏请求瀑布 |
| A3-3 Provider 设置 | 现有 capabilities 只提供状态快照；配置写入、脱敏回读、连接测试是否已有正式 API | 当前计划不得假定存在 |
| A3-4 任务 | `/api/tasks/{task_id}`、cancel、retry 与 enqueue/read 的完整页面字段 | 已有局部能力，需固定公共响应合同 |
| A3-5 计划/节奏 | 列表、详情、progress、rhythm、source refresh 的错误和分页策略 | 后端已具备，需 API mapping 测试 |
| A3-6 笔记/学习 | notes、cards、exercises、practice、mistakes、weak-points、cram 的列表/详情字段 | 后端已具备，需确认前端最小 payload |
| A3-7 采集/报告 | capture/transcript/report/delivery 的状态、能力、导出与隐私字段 | 后端已具备限定范围，需拆出稳定 UI contract |
| A3-8 统一错误 | 不能把 traceback、SQL、路径、raw provider error 返回浏览器 | 必须保持现有安全边界并补页面断言 |
| A3-9 数据范围 | 单 project scope、无登录/多用户、无云同步 | 页面不设计账户/权限切换 |

发现缺口时先建立后端契约、测试和文档任务；禁止在前端猜字段或新建临时端点。

## 8. 分阶段实施顺序

### A3：正式前端根与核心阅读闭环

1. 冻结 API/行为/旧 workspace 兼容基线。
2. ✅ 确认并挂载唯一正式 static root：`backend/app/static/` → `/app`；旧 `/` 暂保留兼容。
3. ✅ 建立首版应用壳、共享 API/导航/状态样式；完整 Neutral Modern 迁移仍随页面迁移继续。
4. ✅ 交付 Draft A–D 灰盒：`index.html`、`materials.html`、`material-detail.html`、`qa.html`。
5. 迁移导入、搜索、索引、thread、citation、定位、导出和窄屏/键盘行为。
6. 完成 focused Chromium + keyboard + privacy + narrow gates。

**A3 完成定义**：用户能从今天 → 资料 → 详情 → Q&A → citation 定位完整往返；旧 UI 不再是正式产品入口，或有明确兼容重定向。

### A4：Provider 设置与课堂采集边界（按权威路线图）

1. `settings.html` / `settings-provider.html`：先接入 capabilities、readiness、diagnostics 和当前任务状态；只有后端形成安全的配置写入/验证契约后，才开放对应配置动作。密钥不回显、不持久化到浏览器。
2. `capture.html`：接入 Phase 9D 已验证的 deterministic fake/loopback 上传、草稿编辑、确认/拒绝/归档和 source lifecycle；真实转写动作由能力状态与 B1 门禁共同控制，未通过时只显示阻塞原因。
3. `tasks.html`（如 A0 静态资源与路由契约确认后需要独立入口）：仅展示后端明确批准的 `embedding_index` enqueue/read/retry/cancel；其它操作显示“尚未接入任务运行器”。

**A4 完成定义**：Provider/采集页面能如实表达已验证范围、失败和禁用边界；已验证的 fake/loopback 路径可操作，未验证的真实动作不可执行。不以页面存在宣称真实 ASR、通用 Provider 或 live delivery 已完成。

### 学习产品页面的增量迁移切片（不新增 roadmap 阶段）

`plans.html`、`plan-detail.html`、`notes.html`、`note-detail.html`、`practice.html`、`practice-session.html`、`practice-result.html`、`review.html` 和“今天”聚合入口，作为已验证 Phase 8/9A/9B/9C 能力的前端迁移切片：

- 可在 A3/A4 壳和契约确认后逐页迁移，不改变 `ROADMAP_CAPABILITIES.md` 的 A3/A4/B0-B4/D0-D1 顺序。
- 每个页面直接消费已冻结 API，保留 draft、pending_review、source status、append-only progress 和失败重试语义。
- 后端 endpoint 或字段未形成稳定契约时，先保留界面状态和 TODO，不在浏览器猜字段或伪造数据。
- 页面完成不等于对应后端能力扩大为 real-pass；仍按 Phase 8/9A/9B/9C 的精确证据范围显示。

### B0：能力组件证据与前端状态准备

为 ASR、OCR、报告和外发候选准备统一的 capability 状态、错误码、禁用原因、loading/failed/retry 和隐私展示合同；未完成 Composer smoke 的候选只能显示为研究中或不可用，不进入成功路径。

### B1：真实 ASR

- 在 C0-C6 全部通过前，`capture.html` 只开放已验证 fake/loopback 流程，真实 ASR 控件保持禁用并说明原因。
- C6 收口后才将真实 ASR 显示为可执行能力；仍按精确工具、模型、环境和输入范围标注，不外推为通用可用。

### B2：真实 OCR

- 在 C0-C6 全部通过前，材料/采集相关页面只预留图片上传、OCR draft、`uncertain`/confidence 和用户确认状态；不得把图片上传显示为 OCR 成功。
- 通过后才开放真实 OCR，并要求 draft-first、citation/source lifecycle 和失败恢复路径。

### B3：本地脱敏报告

- `reports.html` 接入本地 report projection、daily/weekly/monthly/exam_alert 快照、脱敏预览、JSON/Markdown/PDF-safe 导出和来源降级。
- 报告完成不自动批准外发；`delivery=off` 与 allowlisted dry-run 审计必须持续可见。

### B4：真实外发

- 在 B3 scoped closeout 与 B4 C0-C6 通过前，页面只提供 delivery off、dry-run 和 append-only audit；不显示“已发送”。
- 通过后仍需运行时启用、allowlist、逐次确认、幂等、审计和安全失败；精确渠道证据不能外推为所有 SMTP/Webhook 可用。

### D0-D1：桌面验证

- D0 只验证 Tauri shell、FastAPI sidecar、单实例、data root、端口、升级和日志边界；不改变浏览器前端的 local v1 支持声明。
- D1 只在 Windows 隔离环境验证最小安装包；未通过前继续以 Web/loopback 作为正式前端交付边界，不宣称桌面应用已交付。

## 9. 视觉系统与 draft 到高保真转换

项目激活设计系统为 **Neutral Modern**，本计划不再使用旧文档中的 Apple 设计系统表述。

- 背景 `#FAFAFA`，surface `#FFFFFF`，前景 `#111111`，muted `#6B6B6B`，border `#E5E5E5`，accent `#2F6FEB`；实现时复制完整 token 合约，不在组件中散落 raw hex。
- Inter 作为 display/body，mono 用于 ID、状态、时间和数值；正文 16px 起步，移动端触控命中区至少 44px。
- 12 列桌面、8 列平板、4 列手机；卡片白底 1px 边框、12px 圆角、无默认阴影；主操作只使用 cobalt。
- 每屏最多一个主要 accent 焦点和一个主要 CTA；不用紫色渐变、emoji 功能图标、虚构统计、暖米色背景和设计过程面板。
- 高保真之前完成两轮 draft 评审：第一轮审信息架构与状态；第二轮审响应式重排与交互反馈。

## 10. 测试与验收证据

### 必须通过

- 静态资源 mount、页面路由和旧入口兼容测试。
- 每一页的 loading/empty/ready/error/retry 断言。
- 材料导入 → extraction → indexing → Q&A → citation → 导出。
- plan/item/progress/rhythm；note draft/confirm；card/exercise/attempt；mistake/redo；cram session。
- capture 上传/转写 draft/编辑/确认门；报告 preview/export；delivery off/dry-run 审计。
- 重复点击、幂等、过期响应、来源 delete/restore/purge/revision、任务 retry/cancel。
- 360–1920 指定宽度无非预期横向滚动；键盘焦点可见；dialog/drawer/status/alert 语义正确。
- DOM、URL、错误记录和诊断不出现 secret、绝对路径、SQL、traceback、raw provider response、答案 key 或不应公开正文。
- 运行 `C:\miniconda\py310\python.exe -m pytest backend/tests/`，并运行 `python backend/scripts/check-source-size.py`。

### 必须诚实标注

- `implemented` ≠ `real-pass`。
- fake/loopback pass、精确 Provider smoke、真实环境 smoke 必须分开记录。
- 当前真实 OCR/ASR、live delivery、全局多 Provider、多用户、系统级 screen reader、极端长内容和无界长时负载均不能从现有状态推导为已验证。

## 11. 开放 TODO（实施前可编辑）

- [x] **正式 static root / mount**：已确认 `backend/app/static/` 挂载到 `/app`；已完成 HTTP 冒烟验证。仍待补充正式 Chromium 路由/窄屏/键盘证据。
- [ ] **缓存与刷新策略**：当前未设置正式 cache-control/version manifest；确定发布时的刷新策略。
- [ ] **旧 `/` 入口**：当前保留完整单页兼容入口；待 Draft A–D 各自通过回归后决定重定向或逐页切换。
- [ ] **首页聚合 API**：允许多 API 组合，还是新增一个安全聚合 endpoint？
- [ ] **Provider 配置**：后端是否批准配置写入和 connection-test？若没有，设置页只做状态说明。
- [ ] **Today 的默认主行动**：按“计划任务 > 待审草稿 > 导入材料 > Provider 状态说明”还是其它优先级？Provider 配置仅在正式写入契约获批后才可作为可执行动作。
- [ ] **导航显示策略**：报告、课堂采集在未满足真实能力门禁时显示“不可用说明”还是进入更多菜单？
- [ ] **capture 入口**：确认 transcript 后的 material/revision 命名与用户可见文案。
- [ ] **报告用户**：只服务本人，还是需要后续家长/教育者查看权限模型？当前不假设多用户。
- [ ] **真实 ASR 资料**：补充 W0 所需入口、参数、模型、输出和失败证据；没有证据就保持禁用。
- [ ] **draft 评审方式**：先评审 ASCII 草图，还是先做可点击灰盒页面？

## 12. 下一步

当前产物的可用行为先作为迁移回归基线；下一次前端实现不得以“重写单页”为代价删除这些行为。请直接编辑本文件，优先确认以下四项：

1. **页面范围**：是否同意将“今天、计划、资料、问答、笔记、练习、复盘、课堂采集、报告、系统设置”作为目标产品信息架构？
2. **A3 起点**：是否先做正式 static root + 应用壳 + 今天/资料/Q&A，而不是继续扩展旧单页？
3. **首页主行动优先级**：计划任务、待审草稿、导入材料、Provider 状态说明的顺序是否符合你的使用方式？
4. **草图评审**：请在 Draft A–H 下方标注“保留 / 删除 / 合并 / 需要补充”的页面或模块。

A3-1 已完成：已核实 static mount 与现有浏览器入口，并将 Draft A–D 转为 `/app/` 下的可点击灰盒；没有开放或宣称任何未验证 Provider、ASR/OCR 或 live delivery 能力。下一步进入 A3-2：为四页补正式 Chromium 路由、窄屏、键盘、隐私和旧入口兼容回归，再逐页迁移真实操作。

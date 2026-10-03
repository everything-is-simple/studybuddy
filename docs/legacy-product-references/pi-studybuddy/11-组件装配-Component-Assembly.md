# 11 组件装配

**版本**：v0.1.1
**日期**：2026-08-15
**状态**：✅ 已审查批准；T-M5-011 执行中
**上游**：[AGENTS.md §6](../AGENTS.md)、[01-TRD §2](./01-TRD-技术需求-Technical-Requirements.md)、[03-Architecture §3/§9](./03-架构设计-Architecture-Design.md)、[04-Todo §3.3/§4](./04-任务清单-Todo-List.md)
**用途**：pi-studybuddy "先分解，再组合"的单一事实来源（SoT）——组件从识别到装配的标准化流程

---

## T-M5-011 当前装配口径

组件装配的最终判断不是能力卡或 mock 通过，而是组件在当前开发机被装入系统后，能支持真实用户主路径。先固定开发机运行资源并跑通；之后才复制同一资源拓扑到使用机。WPS/OCR/whisper 仍按该口径重新核验。

## 1. 概述

### 1.1 核心原则：先分解，再组合

pi-studybuddy 的系统能力来自成熟组件的组合，**而不是从零造轮子**。

> 系统开发不是先写完整业务，再找组件；而是**先把成熟组件一个个调通，再通过 Adapter 组合成系统能力**。

这一原则源自用户宗旨"拆分，复杂问题简单化，完善好各个小组件，再组合"，是 pi-studybuddy 工程范式的第一原则。

### 1.2 三层架构边界（01-TRD §2.3 + 03-Arch §1）

```
┌─────────────────────────────────────────────┐
│  桌面壳层（pi-desktop 架构自建）              │
│  main + preload + renderer + agent-host     │
│  + contract + 安全 + toolchain + vault       │
├─────────────────────────────────────────────┤
│  pi 扩展层（studybuddy-extension）           │
│  registerTool + pi.on 钩子 + pi-ai provider │
├─────────────────────────────────────────────┤
│  业务 Adapter 层（S1-S7 + TTS + 备份恢复）   │
│  工具实现 + 外部桥 + 数据层                  │
└─────────────────────────────────────────────┘
```

每层内部的组件**独立调通**后，再通过契约装配到上一层。

### 1.3 与其他文档的关系

```
AGENTS.md §6（拆分→小组件→组合宗旨）
    ↓ 细化为流程
docs/11-组件装配（本文件）
    ↓ 指导执行
docs/04-Todo §4（组件治理状态看板）+ docs/03-Arch §9（五阶段×组件）
    ↓ 产出
试炼场（H:\pi-studybuddy-composer）+ 主仓 src/ + 能力卡
```

---

## 2. 组件识别

### 2.1 组件清单（从 01-TRD §2 + 03-Arch §3 推导）

#### 参考仓库组件（阶段 1 已完成下载）

| 组件 | 来源 | 路径 | 用途 |
|---|---|---|---|
| pi | `@earendil-works/pi-coding-agent` | `H:\pi-references\pi` | AI 底座（不修改内核） |
| pi-skills | badlogic/pi-skills | `H:\pi-references\pi-skills` | transcribe / browser-tools / youtube-transcript |
| pi-desktop | DLYZZT/pi-desktop | `H:\pi-references\pi-desktop` | 五件骨架范本（contract/host-manager/credential-vault/toolchain/file-watch） |
| inno-agent | hhyqhh/inno-agent | `H:\pi-references\inno-agent` | 架构范本（不装配，仅参考） |
| OCR venv | ai-studybuddy 迁移 | 待建 | onnxruntime/PIL 全图片格式 |
| whisper.cpp | S7-MVP 底座迁移 | 待下载 | PCM WAV 转写 |

#### 自建组件（需走五阶段）

| 组件 | 分类 | 子系统 | 五阶段 |
|---|---|---|---|
| 桌面壳五件 | 壳层 | 壳 | 阶段 2-5 |
| studybuddy-extension | 扩展层 | 跨切 | 阶段 3-5 |
| S1 学习节奏工具（约 5 个） | 业务 Adapter | S1 | 阶段 2-5 |
| S2 资料笔记工具（约 6 个） | 业务 Adapter | S2 | 阶段 2-5 |
| S3 限时练习工具（约 4 个） | 业务 Adapter | S3 | 阶段 2-5 |
| S4 错题改错工具（约 5 个） | 业务 Adapter | S4 | 阶段 2-5 |
| S5 期末冲刺工具（约 6 个） | 业务 Adapter | S5 | 阶段 2-5 |
| S6 家长报告工具（约 6 个） | 业务 Adapter | S6 | 阶段 2-5 |
| S7 课堂采集工具（约 2 个） | 业务 Adapter | S7 | 阶段 2-5 |
| TTS skill（SAPI + edge-tts） | 业务 Adapter | TTS | 阶段 2-5 |
| 备份恢复（zip + content_hash + 恢复 + 调度） | 业务 Adapter | 备份 | 阶段 2-5 |
| WPS COM 桥（pywin32 子进程） | 外部桥 | S2 | 阶段 2-3 |
| whisper.cpp Adapter | 外部桥 | S7 | 阶段 2-3 |
| OCR venv Adapter | 外部桥 | S1/S2 | 阶段 2-3 |
| workspace-path-guard | 安全 | 跨切 | 阶段 2-5 |
| check-desktop-security.mjs | 安全脚本 | 跨切 | 阶段 5 |

### 2.2 组件粒度原则

| 粒度 | 适用 | 示例 |
|---|---|---|
| **直接套库** | 成熟开源组件 | SQLite（better-sqlite3）、Electron、React |
| **套组件配薄胶水** | 开源组件 + 薄 Adapter | OCR venv + Adapter、whisper.cpp + Adapter |
| **主要自研但薄** | 业务逻辑 | S5 组卷规则、S6 报告规则聚合 |
| **禁止过度工程化** | 不提前设计 | 不为"将来可能需要"加抽象层 |

---

## 3. 试炼场（H:\pi-studybuddy-composer）

### 3.1 试炼场定位

试炼场是组件**独立调通**的专用空间，与主仓库物理隔离。

```
H:\pi-studybuddy-composer\          ← 试炼场（独立调通组件）
├── <component-name>/               ← 每个组件一个目录
│   ├── COMPONENT-CARD.md           ← 能力卡（见 §4）
│   ├── smoke-test.mjs / .py        ← 最小冒烟测试
│   ├── fixtures/                   ← 测试夹具
│   └── README.md                   ← 组件说明
└── README.md                       ← 试炼场总览
```

### 3.2 试炼场规则

1. **独立调通**：每个组件在试炼场独立运行，不依赖主仓代码
2. **最小冒烟**：每个组件有最小冒烟测试，验证核心能力可用
3. **不 import 主仓**：试炼场代码不得 `import` 主仓 `src/`
4. **主仓不复制试炼场**：主仓 `src/` 必须独立重新实现 Adapter，不复制试炼场样例
5. **运行数据不进 Git**：试炼场运行产物不提交
6. **试炼场不变成主系统**：试炼场只验证组件能力，不承载业务流程

### 3.3 试炼场创建时机

试炼场目录在 M0 启动时创建（当前阶段待创建）。

---

## 4. 能力卡（COMPONENT-CARD.md）

### 4.1 能力卡定位

能力卡是每个组件的**能力与边界**记录，是组件从试炼场进入主仓装配的凭证。

### 4.2 能力卡格式

每个组件在试炼场目录下创建 `COMPONENT-CARD.md`：

```markdown
# COMPONENT CARD: <组件名>

## 基本信息
- 组件名：<name>
- 分类：壳层 / 扩展层 / 业务 Adapter / 外部桥 / 安全
- 子系统：S1-S7 / TTS / 备份 / 对话 / 壳 / 跨切
- 来源：自建 / 迁移（ai-studybuddy）/ 开源（名称+版本）
- 依赖：列出依赖的外部组件/库

## 能力描述
- 核心能力：<一句话描述>
- 输入：<接受什么>
- 输出：<产出什么>
- 边界：<不做什么>

## 公开 API
- 方法/函数签名：<列出>
- 参数：<类型+约束>
- 返回：<类型+约束>
- 错误码：<可能抛出的 ErrorCode>

## 冒烟测试
- 测试文件：<路径>
- 通过标准：<断言什么>
- 夹具：<fixtures 路径>

## 五阶段状态
- [x] 阶段 1：下载储存（日期）
- [x] 阶段 2：单件测试（日期）
- [ ] 阶段 3：集成测试
- [ ] 阶段 4：系统组装
- [ ] 阶段 5：冒烟 + E2E

## 装配记录
- 装配到主仓：<日期 + commit + Adapter 路径>
- 装配门禁：<通过/未通过 + 原因>

## 许可证
- 许可证：<名称>
- 是否可接受：<是/否 + 理由>
```

### 4.3 能力卡触发条件

- 阶段 2 单件测试通过后 → 创建能力卡
- 阶段 4 装配到主仓后 → 更新装配记录
- 能力卡是阶段 3→4 的前置条件（无能力卡不装配）

---

## 5. Adapter 封装

### 5.1 Adapter 定位

Adapter 是主仓 `src/` 中对试炼场组件能力的**重新实现**，不是试炼场代码的副本。

```
试炼场组件（调通）  →  Adapter（主仓 src/ 重新实现）  →  装配到系统
    ↑                          ↑                           ↑
    独立调通                   契约化封装                  contract RPC
    最小冒烟                   类型安全                    系统集成
```

### 5.2 Adapter 封装规则

1. **契约优先**：Adapter 必须实现 06-API 契约定义的方法签名
2. **类型安全**：TS strict，禁 `any`
3. **错误码统一**：Adapter 内部错误转为 5 个统一错误码（06-API §2.2）
4. **日志脱敏**：Adapter 日志遵循 allowlist（AGENTS.md §9.3）
5. **不泄漏实现**：Adapter 对上层只暴露公开 API，不暴露内部实现

### 5.3 外部桥 Adapter（特殊规则）

WPS COM / whisper.cpp / OCR venv 三类外部桥 Adapter 额外规则：

1. **子进程隔离**：外部程序崩溃不影响主进程（03-Arch §3.3）
2. **路径只来自配置**：CLI/模型路径不硬编码，不猜路径（08-Test §3.3.2）
3. **JSON 协议**：stdin/stdout 严格 JSON，无额外输出污染（08-Test §3.3.1）
4. **受控输入**：文件头验证（如 PCM WAV），拒绝非受控格式

---

## 6. 主仓装配

### 6.1 装配方式

主仓通过 **contract 类型化 IPC + RPC** 装配组件（借鉴 pi-desktop）：

```
renderer (React)  ←PiBridge→  main (Electron)  ←RPC→  agent-host (utilityProcess)
     │                              │                          │
     └ contextBridge 受控桥接       └ MessageChannelMain        └ createRpcServer()
                                                                   │
                                                                   ├ pi 扩展层（registerTool 工具）
                                                                   └ 业务 Adapter
```

### 6.2 装配契约校验

装配时必须通过 `scripts/check-contract-coverage.mjs`（待创建）AST 级校验：

1. **Api ↔ handlers 一致**：每个 `contract/api.ts` 的方法都有 handler 实现
2. **无 missing**：Api 方法无遗漏 handler
3. **无 duplicates**：handler 无重复注册
4. **无 unknown**：handler 必须在 Api 契约中存在
5. **Browser 桥接一致**：PiBridge 方法 → preload 暴露 → IPC 通道 → main handler 全链一致

---

## 7. 装配门禁

### 7.1 装配门禁四项（组件进入主仓的必要条件）

| # | 门禁项 | 通过标准 |
|---|---|---|
| 1 | 组件测试全绿 | 试炼场冒烟 + 单件测试全通过 |
| 2 | 工作区干净 | 试炼场 git status 无 unstaged 改动 |
| 3 | 公开 API 有文档 | 能力卡完整 + 06-API 契约已登记 |
| 4 | 无越权行为 | 不写业务数据根外路径 / 不连真实外部服务 / 不泄漏密钥 |

### 7.2 装配门禁失败处理

任一门禁未通过 → **不装配** → 退回试炼场修复 → 重走门禁

### 7.3 装配记录

装配通过后：
1. 更新能力卡"装配记录"章节
2. 在 04-Todo §4 组件治理看板标记该组件阶段 4 完成
3. 提交到主仓 `src/` 的 Adapter 代码

---

## 8. 组件化装配流程（完整 6 步）

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. 组件识别                                                          │
│    从 01-TRD §2 + 03-Arch §3 识别所需组件                            │
│    → 登记到 04-Todo §4 组件治理看板                                  │
├──────────────────────────────────────────────────────────────────────┤
│ 2. 试炼场单件                                                        │
│    在 H:\pi-studybuddy-composer\<component>\ 独立调通                │
│    → 编写最小冒烟测试 + 夹具                                         │
│    → 阶段 2 单件测试通过                                             │
├──────────────────────────────────────────────────────────────────────┤
│ 3. 能力卡沉淀                                                        │
│    创建 COMPONENT-CARD.md 记录组件能力与边界                         │
│    → 公开 API + 冒烟测试 + 五阶段状态                                │
├──────────────────────────────────────────────────────────────────────┤
│ 4. Adapter 封装                                                      │
│    在主仓 src/ 重新实现 Adapter（不复制试炼场代码）                  │
│    → 契约化封装 + 类型安全 + 错误码统一 + 日志脱敏                   │
├──────────────────────────────────────────────────────────────────────┤
│ 5. 主仓装配                                                          │
│    通过 contract RPC 装配进系统                                      │
│    → check-contract-coverage.mjs AST 校验通过                        │
├──────────────────────────────────────────────────────────────────────┤
│ 6. 装配门禁                                                          │
│    组件测试全绿 + 工作区干净 + 公开 API 有文档 + 无越权行为          │
│    → 更新能力卡 + 04-Todo 看板                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. 组件治理状态看板（04-Todo §4 对齐）

### 9.1 看板格式

| 组件 | 阶段1 下载 | 阶段2 单件 | 阶段3 集成 | 阶段4 组装 | 阶段5 冒烟E2E | 状态 |
|---|---|---|---|---|---|---|
| `pi`（npm peerDeps） | ✅ | — | — | — | — | 已下载 |
| `pi-skills`（git clone） | ✅ | — | — | — | — | 已下载 |
| `pi-desktop` 骨架 | ✅ | — | — | — | — | 已下载 |
| `inno-agent` 范本 | ✅ | — | — | — | — | 已下载（仅参考） |
| OCR venv | ✅ | — | — | — | — | 已下载 |
| whisper.cpp | ✅ | — | — | — | — | 已下载 |
| 桌面壳五件 | — | — | — | — | — | 待启动 |
| studybuddy-extension | — | — | — | — | — | 待启动 |
| S1-S7 工具（约 30 个） | — | — | — | — | — | 待启动 |
| TTS skill | — | — | — | — | — | 待启动 |
| 备份恢复 | — | — | — | — | — | 待启动 |
| WPS COM 桥 | — | — | — | — | — | 待启动 |
| whisper.cpp Adapter | — | — | — | — | — | 待启动 |
| OCR venv Adapter | — | — | — | — | — | 待启动 |
| workspace-path-guard | — | — | — | — | — | 待启动 |
| check-desktop-security.mjs | — | — | — | — | — | 待启动 |

> 阶段标记：✅ 通过 / ⏳ 进行中 / ❌ 失败待修复 / — 未进入 / ⏭️ 跳过（不适用）

### 9.2 看板更新规则

- 每个组件阶段变更同步到 04-Todo §4
- 看板是组件治理的实时快照，不只存在于聊天
- 装配门禁通过后阶段 4 标 ✅

---

## 10. 装配顺序（03-Arch §9.2）

```
第一批：壳层（M0）
  ├─ contract 类型化 IPC + RPC 层
  ├─ main + preload + renderer + agent-host 四进程骨架
  ├─ 安全沙箱（sandbox:true + CSP + preload 受控桥接）
  ├─ toolchain 发现
  ├─ credential-vault
  └─ file-watch

第二批：公用零件（M0-M1 过渡）
  ├─ 数据层 schema（global.db + semester.db + 三层记忆）
  └─ pi 扩展层空壳（createStudyBuddyExtension 可 setup 无工具）

第三批：业务模块（M1-M3）
  ├─ M1: S1-S4 工具 + WPS COM + OCR venv Adapter
  ├─ M2: S5-S7 + TTS + 备份恢复 + whisper.cpp Adapter
  └─ M3: 💬 对话 Tab + 打磨
```

**铁律**：禁止在壳层未就绪时开发业务模块（AGENTS.md §4.3）。

---

## 11. 组件安全（01-TRD §5 + AGENTS.md §9.4）

### 11.1 组件安全检查清单

每个组件装配前检查：

- [ ] zip 炸弹防护（条目/解压比限制）——如涉及压缩
- [ ] MIME 严格匹配——如涉及文件上传
- [ ] 不执行嵌入代码——如涉及文档解析
- [ ] 符号链接逃逸防护——如涉及文件路径
- [ ] 路径只来自配置——如外部桥
- [ ] 子进程隔离——如外部桥
- [ ] JSON 协议——如外部桥
- [ ] 受控输入——如外部桥

### 11.2 越权行为检测

装配门禁第 4 项"无越权行为"检查：

- 不写业务数据根外路径（`%LOCALAPPDATA%\PiStudyBuddy` 之外）
- 不连真实外部服务（除冒烟/E2E 受控夹具）
- 不泄漏密钥（日志 allowlist）
- 不侵入 `~/.pi`（pi 会话目录由 pi 自管）

---

## 12. 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1.0 | 2026-08-07 | 初始草案：先分解再组合 SoT。12 章：核心原则 + 三层架构边界 + 组件识别（参考仓库 + 自建清单）+ 试炼场规则 + 能力卡格式 + Adapter 封装规则（含外部桥特殊规则）+ 主仓装配（contract RPC + AST 校验）+ 装配门禁四项 + 完整 6 步流程 + 组件治理看板 + 装配顺序 + 组件安全检查。参考 ai-studybuddy docs/05（先分解再组合）+ ai-malf-riskbench 装配.md（装配门禁）+ pi-desktop check-contract-coverage.mjs（AST 校验）+ AGENTS.md §6（拆分组合宗旨） |

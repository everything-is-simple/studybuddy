# AI StudyBuddy Code Wiki

**版本**：v2.0
**生成日期**：2026-07-30
**适用范围**：AI StudyBuddy 全系统代码百科，覆盖主仓库、部署仓库与关联仓库。v2.0 新增关键发现与现状评估。

---

## 目录

1. [项目整体概述](#1-项目整体概述)
2. [仓库拓扑与边界](#2-仓库拓扑与边界)
3. [系统架构](#3-系统架构)
4. [目录结构](#4-目录结构)
5. [技术栈与依赖](#5-技术栈与依赖)
6. [核心模块详解](#6-核心模块详解)
7. [关键类与函数](#7-关键类与函数)
8. [数据模型](#8-数据模型)
9. [API 接口说明](#9-api-接口说明)
10. [前端路由与页面](#10-前端路由与页面)
11. [项目运行方式](#11-项目运行方式)
12. [部署方式](#12-部署方式)
13. [子系统依赖关系](#13-子系统依赖关系)
14. [附录 D：现状评估与关键发现](#附录-d现状评估与关键发现)

---

## 1. 项目整体概述

### 1.1 项目定位

**AI StudyBuddy** 是一款面向大学生的 Windows 本机学习助手。系统将课程、考试目标、学习节奏、资料笔记、限时练习、错题复盘和考前冲刺连接成一个可持续的学习闭环。学生是唯一操作者，家长通过异步脱敏报告了解学习状态。

### 1.2 产品形态

- **运行环境**：Windows 11 本机，Express 只监听 `127.0.0.1`
- **用户入口**：本机浏览器访问 `http://127.0.0.1:3000`
- **数据存储**：SQLite（全局索引库 + 每学期一个业务库）
- **家长通道**：QQ SMTP 邮件 + 飞书 Webhook 异步报告
- **无公网入口**：不提供远程登录、家长 Web 面板或云端服务

### 1.3 子系统划分

系统由 **1 个共同底座 + 7 个场景子系统** 组成：

| 编号 | 子系统         | 英文代号       | 当前状态              |
| ---- | -------------- | -------------- | --------------------- |
| S1   | 学习节奏子系统 | StudyRhythm    | 已完成主线复验        |
| S2   | 资料笔记子系统 | NoteBuilder    | 已完成主线复验        |
| S3   | 限时练习子系统 | PracticeRunner | 已完成主线复验        |
| S4   | 错题改错子系统 | ErrorFixer     | 已完成主线复验        |
| S5   | 期末冲刺子系统 | ExamCrammer    | 已完成主线复验        |
| S6   | 家长观察子系统 | ParentReport   | 已完成主线复验        |
| S7   | 课堂采集子系统 | ClassCapture   | S7-MVP 已完成主线复验 |

### 1.4 开发阶段总览

- Phase 0.5/0.7/0.8：底座搭建、S1/S2 MVP
- Phase 1：S1-S4 + S6 简版闭环（已完成）
- Phase 1.5：S7-MVP 课堂录音（已完成）
- Phase 2：S5 期末冲刺（已完成）
- Phase 3：安全、性能与运维增强（仅高权重必做项恢复规划中）

---

## 2. 仓库拓扑与边界

### 2.1 仓库列表

| 仓库路径                     | 用途                   | 角色                           |
| ---------------------------- | ---------------------- | ------------------------------ |
| `h:\ai-studybuddy`           | **主系统 Git 仓库**    | 源码、文档、测试、计划         |
| `h:\StudyBuddy`              | **Windows 部署包仓库** | 编译后产物、部署脚本、用户文档 |
| `h:\ai-studybuddy-composer`  | 组件试炼场             | 独立验证开源组件，不进入主仓库 |
| `h:\ai-studybuddy-tmp`       | 隔离验证目录           | 临时运行数据、测试隔离根       |
| `h:\ai-studybuddy-worktrees` | 并行任务 worktree 根   | 唯一合法的任务 worktree 目录   |
| `h:\ai-studybuddy-backup`    | 历史备份               | 旧归档、草稿、外部参考         |
| `h:\KaoBuddy-Windows`        | 外部参考               | 只读参考，不复制源码           |

### 2.2 仓库边界规则

- **主仓库** (`ai-studybuddy`)：只保存正式产品设计、源码实现和审计结论
- **部署仓库** (`StudyBuddy`)：只包含编译后的后端/前端、共享资产、部署脚本和用户文档，不携带 `.git`、`node_modules`、真实密钥
- **试炼场** (`ai-studybuddy-composer`)：禁止被主仓库 `import`；组件进入产品必须通过 Adapter 边界重新实现
- **验证目录**：`ai-studybuddy-tmp/runs/<task-id>` 用于隔离验证，不复用正式数据

---

## 3. 系统架构

### 3.1 整体架构图

```text
┌──────────────────────────────────────────────────────────────┐
│                    学生 Windows 本机浏览器                      │
│                   http://127.0.0.1:3000                       │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    Express 本地服务 (app.ts)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ API 路由层   │  │ 中间件层      │  │ 静态文件服务 (SPA)  │  │
│  │ /api/*       │  │ Origin策略    │  │ public/ + fallback  │  │
│  │ 13 个路由模块 │  │ 错误处理      │  │                    │  │
│  └──────┬───────┘  └──────────────┘  └────────────────────┘  │
│         │                                                      │
│  ┌──────▼──────────────────────────────────────────────────┐  │
│  │                    Service 层 (17 个服务)                 │  │
│  │  StudyRhythm / NoteBuilder / PracticeRunner /           │  │
│  │  ErrorFixer / ExamCrammer / ParentReport /              │  │
│  │  ClassCapture / DailyStudyHome / SemesterSelector /     │  │
│  │  FeedbackRules / CramPlan / MaterialJobWorker ...       │  │
│  └──────┬──────────────────────────────────────────────────┘  │
│         │                                                      │
│  ┌──────▼──────────────────────────────────────────────────┐  │
│  │                    Adapter 层                            │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │  │
│  │  │ AI Router│ │Converter │ │ Storage  │ │ Aural     │  │  │
│  │  │ Provider │ │ PDF/OCR  │ │ Adapter  │ │ whisper   │  │  │
│  │  │ 熔断/冷却 │ │ DOCX/PPTX│ │ 本地文件  │ │ .cpp      │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │  │
│  └──────┬──────────────────────────────────────────────────┘  │
│         │                                                      │
│  ┌──────▼──────────────────────────────────────────────────┐  │
│  │                    数据层 (db/)                           │  │
│  │  ┌────────────────┐  ┌──────────────────────────────┐   │  │
│  │  │ 全局索引库      │  │ 学期业务库 (每学期一个)        │   │  │
│  │  │ studybuddy.db  │  │ semester.db (WAL + FK)       │   │  │
│  │  │ 配置/学期目录   │  │ 课程/考试/任务/事件/资料...   │   │  │
│  │  └────────────────┘  └──────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                    配置层 (config/)                       │ │
│  │  env.ts → ConfigurationService → DPAPI 加密存储           │ │
│  │  运行时配置优先级：DPAPI active > 环境变量 fallback        │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                     外部子系统 (独立进程)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ RapidOCR     │  │ whisper.cpp  │  │ Windows 任务计划    │  │
│  │ Python 子进程 │  │ 本机 CLI     │  │ 22:30 家长报告      │  │
│  └──────────────┘  └──────────────┘  └────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                           │
│  │ AI Provider  │  │ QQ SMTP/飞书  │                           │
│  │ GPT/Claude   │  │ 出站发送      │                           │
│  └──────────────┘  └──────────────┘                           │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```text
用户上传资料 → StorageAdapter → Converter(OCR/PDF) → 纯文本
  → AI Router → 结构化笔记/导图/知识模块 → 前端 Markdown 渲染

学生发起练习 → PracticeRunnerService → 题库生成 → 限时作答
  → 提交批改 → 客观题规则引擎/主观题 AI → 练习记录 → 错题回流 S4

Web 前端 ← API 信封 {success, data, error} ← Express 路由 ← Service ← Adapter/DB
```

### 3.3 架构原则

- **本机优先**：所有数据和计算在本地完成
- **按需运行**：OCR、AI、报告 Worker 按 Job 运行后退出，不常驻
- **单写进程**：单 Node 进程写入 SQLite，避免并发冲突
- **Adapter 隔离**：业务代码不直接依赖 Python 命令、绝对路径、SMTP 授权码
- **分级 fallback**：PDF→OCR→视觉AI→手工；AI→备选→pending_quality_check→学生核对

---

## 4. 目录结构

### 4.1 主仓库 (`h:\ai-studybuddy`)

```text
ai-studybuddy/
├── packages/
│   ├── backend/                     # 后端 Express 服务
│   │   ├── src/
│   │   │   ├── adapters/            # Adapter 实现
│   │   │   │   ├── ai/              # AI Provider Router
│   │   │   │   │   ├── router.ts          # 多 Provider 路由 + 熔断
│   │   │   │   │   ├── openai-provider.ts # OpenAI 兼容 Provider
│   │   │   │   │   └── provider.ts        # Provider 接口定义
│   │   │   │   ├── aural/           # 音频转写
│   │   │   │   │   └── whispercpp-aural-converter.ts
│   │   │   │   ├── converter.ts     # 格式转换统一接口
│   │   │   │   ├── docx-converter.ts
│   │   │   │   ├── pptx-converter.ts
│   │   │   │   ├── storage.ts       # 本地文件存储
│   │   │   │   └── url-fetcher.ts
│   │   │   ├── api/                 # Express 路由模块 (13 个)
│   │   │   │   ├── study-rhythm.ts
│   │   │   │   ├── note-builder.ts
│   │   │   │   ├── practice-runner.ts
│   │   │   │   ├── error-fixer.ts
│   │   │   │   ├── exam-crammer.ts
│   │   │   │   ├── class-capture.ts
│   │   │   │   ├── daily-study-home.ts
│   │   │   │   ├── semester-selector.ts
│   │   │   │   └── dev-*.ts (开发路由)
│   │   │   ├── config/              # 配置管理
│   │   │   │   ├── env.ts                 # 环境变量集中读取
│   │   │   │   ├── configuration-service.ts # 配置中心核心
│   │   │   │   ├── configuration-types.ts
│   │   │   │   ├── connection-tester.ts    # 连接测试
│   │   │   │   ├── dpapi-protector.ts      # Windows DPAPI 加密
│   │   │   │   ├── secure-store.ts         # 安全存储抽象
│   │   │   │   ├── config-registry.ts      # 运行时配置注册表
│   │   │   │   └── runtime-configuration.ts
│   │   │   ├── db/                  # 数据库层
│   │   │   │   ├── connection.ts          # 连接管理 (WAL/FK/checkpoint)
│   │   │   │   ├── paths.ts               # 路径安全生成 (逃逸防护)
│   │   │   │   ├── migrations.ts          # Migration 执行器
│   │   │   │   ├── semester-initializer.ts # 学期初始化
│   │   │   │   ├── backups.ts             # 备份工具
│   │   │   │   └── sql/                   # Schema 与 Migration SQL
│   │   │   │       ├── schema-global.ts
│   │   │   │       ├── schema-semester.ts
│   │   │   │       └── migration-*.ts     # v2-v11
│   │   │   ├── middleware/           # Express 中间件
│   │   │   │   ├── api-origin-policy.ts
│   │   │   │   └── api-error-handler.ts
│   │   │   ├── routes/              # 配置路由
│   │   │   │   └── config-routes.ts
│   │   │   ├── scripts/             # 独立脚本
│   │   │   │   ├── ocr-worker.py          # OCR Python Worker
│   │   │   │   └── parent-report-runner.ts # 家长报告 Runner
│   │   │   ├── services/            # 业务服务 (17 个)
│   │   │   │   ├── study-rhythm-service.ts
│   │   │   │   ├── note-builder-service.ts
│   │   │   │   ├── practice-runner-service.ts
│   │   │   │   ├── error-fixer-service.ts
│   │   │   │   ├── error-fixer-query-service.ts
│   │   │   │   ├── exam-crammer-service.ts
│   │   │   │   ├── cram-plan-service.ts
│   │   │   │   ├── class-capture-service.ts
│   │   │   │   ├── daily-study-home-service.ts
│   │   │   │   ├── parent-report-service.ts
│   │   │   │   ├── parent-report-delivery-service.ts
│   │   │   │   ├── semester-selector-service.ts
│   │   │   │   ├── semester-access-service.ts
│   │   │   │   ├── feedback-rules-service.ts
│   │   │   │   └── material-job-worker.ts
│   │   │   ├── utils/               # 工具
│   │   │   │   ├── ai-logger.ts
│   │   │   │   └── runtime-log-boundary.ts
│   │   │   ├── app.ts               # Express 应用组装
│   │   │   ├── bootstrap.ts         # 启动引导
│   │   │   └── server.ts            # 入口文件
│   │   ├── test/                    # 后端测试 (~70 个测试文件)
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── frontend/                    # 前端 React 应用
│   │   ├── src/
│   │   │   ├── api/                 # API 客户端封装 (11 个)
│   │   │   ├── components/          # 可复用组件 (13 个)
│   │   │   ├── hooks/               # 自定义 Hooks (6 个)
│   │   │   ├── pages/               # 页面组件 (20 个)
│   │   │   ├── styles/              # 全局样式
│   │   │   ├── types/               # 前端视图模型
│   │   │   ├── app.tsx              # 路由壳 + 全局状态
│   │   │   └── main.tsx             # React 入口
│   │   ├── test/                    # 前端测试 (~26 个测试文件)
│   │   ├── vite.config.ts
│   │   └── package.json
│   └── shared/                      # 共享类型定义
│       ├── src/
│       │   ├── index.ts             # 导出入口
│       │   └── types.ts             # 所有 DTO/类型 (~900 行)
│       └── package.json
├── docs/                            # 设计文档 (15+ 份)
├── e2e/                             # Playwright E2E 测试 (15 个 spec)
├── scripts/                         # 部署/运维脚本 (20+ 个)
├── .plans/                          # 任务计划文件
├── package.json                     # Monorepo 根配置
├── pnpm-workspace.yaml
└── playwright.config.ts
```

### 4.2 部署仓库 (`h:\StudyBuddy`)

```text
StudyBuddy/
├── app/
│   ├── backend/                     # 编译后后端 (dist/)
│   │   ├── adapters/                # 编译后 Adapter
│   │   ├── api/                     # 编译后路由
│   │   ├── config/                  # 编译后配置
│   │   ├── db/                      # 编译后数据库层
│   │   ├── middleware/
│   │   ├── public/                  # 编译后前端静态资源
│   │   │   ├── assets/              # KaTeX 字体 + JS chunks
│   │   │   └── index.html
│   │   ├── routes/
│   │   ├── scripts/
│   │   │   ├── ocr-worker.py
│   │   │   └── parent-report-runner.js
│   │   ├── services/
│   │   ├── utils/
│   │   ├── server.js
│   │   └── package.json
│   ├── shared/                      # 编译后共享类型
│   └── requirements-ocr.txt
├── docs/                            # 部署文档 (6 份)
├── scripts/                         # 部署脚本 (13 个)
│   ├── lib/                         # 脚本库
│   ├── bootstrap-runtime.ps1        # 全新安装
│   ├── start-production.ps1         # 启动
│   ├── stop-production.ps1          # 停止
│   ├── check-installation.ps1       # 安装检查
│   ├── backup-data.ps1              # 备份
│   ├── restore-data.ps1             # 恢复
│   └── ...
├── deployment/                      # 部署配置
├── deployment-manifest.json
└── README-Windows.md
```

---

## 5. 技术栈与依赖

### 5.1 运行时环境

| 组件   | 选型             | 版本                          |
| ------ | ---------------- | ----------------------------- |
| 运行时 | Node.js          | 24 LTS（已验证基线；部署脚本仅接受 major 24，Node 25 不支持） |
| 包管理 | pnpm             | workspace monorepo            |
| 语言   | TypeScript       | 5.3+                          |
| Python | Python 3.10+ x64 | OCR 子进程                    |

### 5.2 后端核心依赖

| 包名                   | 用途               | 版本     |
| ---------------------- | ------------------ | -------- |
| `express`              | Web 框架           | ^4.18.2  |
| `better-sqlite3`       | SQLite 数据库      | ^12.11.1 |
| `openai`               | AI Provider SDK    | ^6.46.0  |
| `pdf-parse`            | PDF 文本提取       | 2.4.5    |
| `mammoth`              | DOCX 转换          | ^1.12.0  |
| `jszip`                | PPTX/OOXML 解析    | ^3.10.1  |
| `jsdom`                | HTML 解析          | ^29.1.1  |
| `@mozilla/readability` | 网页正文提取       | ^0.6.0   |
| `undici`               | HTTP 客户端        | ^8.7.0   |
| `nodemailer`           | SMTP 邮件          | ^7.0.13  |
| `multer`               | 文件上传           | ^2.2.0   |
| `dotenv`               | 环境变量加载       | ^16.3.1  |
| `@primno/dpapi`        | Windows DPAPI 加密 | 2.0.1    |

### 5.3 前端核心依赖

| 包名                  | 用途          | 版本     |
| --------------------- | ------------- | -------- |
| `react` / `react-dom` | UI 框架       | ^18.3.1  |
| `react-router-dom`    | 路由          | ^6.24.1  |
| `react-markdown`      | Markdown 渲染 | ^9.0.1   |
| `remark-gfm`          | GFM 扩展      | ^4.0.0   |
| `remark-math`         | 数学公式解析  | ^6.0.0   |
| `rehype-katex`        | KaTeX 渲染    | ^7.0.1   |
| `katex`               | 数学公式样式  | ^0.16.11 |
| `markmap-lib`         | 思维导图数据  | ^0.18.9  |
| `markmap-view`        | 思维导图渲染  | ^0.18.9  |
| `vite`                | 构建工具      | ^5.3.3   |
| `vitest`              | 测试框架      | ^2.0.2   |

### 5.4 外部组件

| 组件              | 用途             | 调用方式                 |
| ----------------- | ---------------- | ------------------------ |
| RapidOCR          | 图片 OCR 识别    | Python 子进程 (用完退出) |
| whisper.cpp       | 本机语音转文字   | 配置化 CLI 子进程        |
| GPT/Claude (中转) | 默认 AI Provider | OpenAI-compatible API    |
| QQ SMTP           | 家长报告邮件     | nodemailer 出站          |
| 飞书 Webhook      | 家长报告卡片     | HTTP POST                |

---

## 6. 核心模块详解

### 6.1 后端模块

#### 6.1.1 入口与启动 (`server.ts` / `bootstrap.ts` / `app.ts`)

启动流程：

1. `server.ts` 调用 `bootstrapBackend()`
2. `bootstrap.ts` 初始化配置 → 创建 Express App → 启动 MaterialJobWorker → 监听端口
3. `app.ts` 组装中间件 (Origin 策略 → JSON 解析 → 路由 → 静态文件 → 错误处理)

```typescript
// 启动顺序
initializeConfiguration()  // 读取配置
  → SemesterSelectorService.migrateReadySemesters()  // 迁移就绪学期
  → createApplication()     // 组装 Express
  → worker.startPolling()   // 启动后台 Job Worker
  → app.listen()            // 监听端口
```

#### 6.1.2 环境变量管理 (`config/env.ts`)

- 所有环境变量通过 `config` 对象集中导出
- 业务代码禁止直接访问 `process.env`
- 支持 `.env.local` 自动加载（多路径候选）
- 启动时校验 `APP_DATA_ROOT` 必须存在且可写
- `BACKEND_HOST` 强制锁定为 `127.0.0.1`

#### 6.1.3 配置中心 (`config/configuration-service.ts`)

- 普通设置与秘密分离
- 秘密通过 Windows DPAPI 加密存储
- 运行时 Adapter 只读取不可变配置快照
- 配置状态独立：AI / SMTP / 飞书 各自 `unconfigured | verified_pass | environment_fallback`
- 测试成功后原子激活，失败不写入磁盘

#### 6.1.4 数据库层 (`db/`)

**双库模型**：

- `studybuddy.db`（全局库）：配置、学期索引、备份记录
- `semester.db`（学期库）：课程实例、考试、任务、事件、资料等

**连接管理** (`connection.ts`)：

- `openDbAtPath()` — 打开并启用 WAL + foreign_keys
- `openExistingDbAtPath()` — 仅打开已存在库
- `openReadOnlyExistingDbAtPath()` — 只读打开
- `checkpointAndClose()` — WAL checkpoint + 关闭
- `runIntegrityCheck()` — 完整性检查
- `backupDb()` — 备份

**路径安全** (`paths.ts`)：

- `resolveAppDataPath()` — 校验路径必须在 `APP_DATA_ROOT` 内，拒绝 `..` 逃逸
- `resolveStorageKeyToPath()` — 解析 `storage_key` 为物理路径，强校验格式

**Migration 系统** (`migrations.ts`)：

- `schema_migrations` 表记录已执行版本
- 版本连续递增，缺口必须失败
- Migration SQL 与其版本记录在同一事务内提交
- 当前学期库 migration 版本：v1-v11（全局库 v1-v2）

#### 6.1.5 AI Provider Router (`adapters/ai/router.ts`)

核心类：`AiProviderRouter`

- 按 `priority` 升序尝试 Provider
- 连续失败 5 次 → 冷却 10 分钟
- 冷却到期 → 恢复探测（成功清零，失败重新冷却）
- 全部冷却 → `AllProvidersCoolingDownError`
- 全部失败 → `AllProvidersFailedError`
- 未配置 → `AI_NOT_CONFIGURED`
- 日志只记录 Provider 名称、model、token、耗时、fallback，不记录 Key/正文

#### 6.1.6 格式转换 Adapter

| Adapter                    | 输入     | 输出                   | 实现                   |
| -------------------------- | -------- | ---------------------- | ---------------------- |
| `PdfConverter`             | PDF      | `{ok, text, metadata}` | pdf-parse              |
| `OcrConverter`             | 图片     | `{ok, text, warnings}` | RapidOCR Python 子进程 |
| `DocxConverter`            | DOCX     | `{ok, text, metadata}` | mammoth.js             |
| `PptxConverter`            | PPTX     | `{ok, text, metadata}` | JSZip + OOXML          |
| `UrlFetcher`               | URL/HTML | `{ok, text, metadata}` | undici + Readability   |
| `WhisperCppAuralConverter` | PCM WAV  | `{ok, text}`           | whisper.cpp CLI        |

统一输出：`ConverterResult { ok, sourceType, text, metadata, warnings, error }`

#### 6.1.7 中间件

- `api-origin-policy.ts`：loopback Origin 校验，默认允许 `5173`/`4173`，拒绝远程 Origin
- `api-error-handler.ts`：统一错误处理，返回 `{success:false, error:{code, message}}`

### 6.2 前端模块

#### 6.2.1 路由结构 (`app.tsx`)

22 个路由，按学期上下文分组：

| 路由                                                    | 页面             | 子系统 |
| ------------------------------------------------------- | ---------------- | ------ |
| `/`                                                     | 每日学习首页     | S1     |
| `/courses`                                              | 课程与考试目标   | S1     |
| `/materials`                                            | 资料上传         | S2     |
| `/notes/:noteId`                                        | 笔记详情         | S2     |
| `/exams/:examId`                                        | 考试工作台       | S1/S5  |
| `/exams/:examId/practice`                               | 练习发起         | S3     |
| `/practice-sessions/:sessionId`                         | 练习作答         | S3     |
| `/practice-sessions/:sessionId/result`                  | 练习结果         | S3     |
| `/semesters/:semesterId/practice-history`               | 练习历史         | S3     |
| `/semesters/:semesterId/practice-history/:sessionId`    | 练习历史详情     | S3     |
| `/exams/:examId/mistakes`                               | 错题列表         | S4     |
| `/mistakes`                                             | 错题列表（全部） | S4     |
| `/mistakes/:mistakeId`                                  | 错题详情         | S4     |
| `/exams/:examId/mock-exam`                              | 模拟考入口       | S5     |
| `/mock-exam-papers/:paperId`                            | 模拟卷详情       | S5     |
| `/mock-exam-attempts/:attemptId`                        | 模拟考作答       | S5     |
| `/mock-exam-attempts/:attemptId/result`                 | 模拟考结果       | S5     |
| `/exams/:examId/cram`                                   | 临考速背         | S5     |
| `/exams/:examId/cram-plan`                              | 冲刺计划         | S5     |
| `/semesters`                                            | 学期管理         | 共同   |
| `/settings`                                             | 配置中心         | 共同   |

#### 6.2.2 核心组件

| 组件                      | 功能                          |
| ------------------------- | ----------------------------- |
| `AppNavigation`           | 全局导航                      |
| `ExamContextNav`          | 考试上下文导航                |
| `PageState`               | 统一 loading/empty/error 状态 |
| `MarkdownNote`            | Markdown + KaTeX 安全渲染     |
| `LazyMindMap` / `MindMap` | Markmap 思维导图（按需加载）  |
| `FileDropzone`            | 文件拖拽上传                  |
| `MaterialStatus`          | 资料处理状态                  |
| `PracticeQuestion`        | 练习题目展示                  |
| `MockExamQuestion`        | 模拟考题目展示                |
| `FeedbackMessage`         | 操作反馈                      |

#### 6.2.3 自定义 Hooks

| Hook                 | 功能                           |
| -------------------- | ------------------------------ |
| `useApiRequest`      | 可取消请求、loading/error 状态 |
| `useMaterialPolling` | 资料处理状态轮询（指数退避）   |
| `usePracticeTimer`   | 练习计时器                     |
| `usePracticeDraft`   | 练习作答草稿                   |
| `useMockExamDraft`   | 模拟考作答草稿                 |
| `useCramSession`     | 冲刺会话状态                   |

### 6.3 共享类型 (`packages/shared`)

`types.ts` 是系统的类型单一事实来源，定义了所有跨端 DTO、接口和枚举，包括：

- 用户与角色：`User`, `UserRole`
- S1 学习节奏：`CourseInstanceDto`, `AssessmentAttemptDto`, `StudyTaskDto`, `StudyEventDto`
- S2 资料笔记：`Material`, `KnowledgeModule`, `StructuredNote`, `MaterialDto`
- S3 练习：`PracticeSessionRecord`, `PracticeQuestionRecord`, `PracticeAnswerRecord`
- S4 错题：`MistakeRecord`, `MistakeEvidenceRecord`, `WeakPointRecord`
- S5 冲刺：`MockExamPaperDetailDto`, `CramFlashcardDto`, `CramPlanResponseDto`
- S7 课堂：`ClassCaptureTranscriptDto`
- API 信封：`ApiSuccess<T>`, `ApiError`, `ApiResponse<T>`
- Adapter：`ConverterResult`, `AiRequest`, `AiResponse`

---

## 7. 关键类与函数

### 7.1 后端核心类

#### `AiProviderRouter` (`adapters/ai/router.ts`)

```typescript
class AiProviderRouter implements AiProvider {
  name = 'router';
  private providers: AiProvider[];
  private health: Map<AiProvider, ProviderHealthState>;

  constructor(options?: AiProviderRouterOptions);
  async generate(request: AiRequest): Promise<AiResponse>;
  // 失败阈值: 5 次，冷却时间: 10 分钟
  // 错误类型: AI_NOT_CONFIGURED / AI_ALL_PROVIDERS_FAILED / AI_ALL_PROVIDERS_COOLING_DOWN
}
```

#### `ConfigurationService` (`config/configuration-service.ts`)

```typescript
class ConfigurationService {
  getStatus(): ConfigurationStatus;
  testAndActivate(channel, config): Promise<TestAndActivateResult>;
  getActiveSnapshot(): ChannelConfigMap;
  // 测试成功才写入 DPAPI 加密存储
  // 运行时消费者只读取不可变快照
}
```

#### `MaterialJobWorker` (`services/material-job-worker.ts`)

```typescript
class MaterialJobWorker {
  startPolling(intervalMs: number): NodeJS.Timeout;
  stopPolling(timer: NodeJS.Timeout): void;
  // 从 jobs 表拉取 pending 任务，串行执行
  // 恢复超时 running 任务为 pending
  // 有限重试，达到上限标记 failed
}
```

#### 数据库连接函数 (`db/connection.ts`)

```typescript
function openDbAtPath(dbPath: string): DatabaseType; // 创建/打开 + WAL + FK
function openExistingDbAtPath(dbPath: string): DatabaseType; // 仅打开已存在
function openReadOnlyExistingDbAtPath(dbPath: string): DatabaseType; // 只读
function openGlobalDb(): DatabaseType; // 打开全局库
function openSemesterDb(semesterId: string): DatabaseType; // 打开学期库
function runIntegrityCheck(db: DatabaseType): string; // PRAGMA integrity_check
function checkpointAndClose(db: DatabaseType): void; // WAL checkpoint + 关闭
function backupDb(db: DatabaseType, destination: string): void; // 备份
```

#### 路径生成函数 (`db/paths.ts`)

```typescript
function getGlobalDbPath(): string;
function getSemesterDbPath(semesterId: string): string;
function getSemesterFilesDir(semesterId: string): string;
function getSemesterTmpDir(semesterId: string): string;
function resolveStorageKeyToPath(storageKey: string): string; // 强校验格式
function getClassCaptureTmpDir(): string; // S7 临时音频
function getConfigDir(): string; // DPAPI 加密配置
```

### 7.2 前端核心类/函数

#### `App` 组件 (`app.tsx`)

```typescript
function App() {
  // 学期状态管理: loading → ready / none / error
  // 配置状态检查: 首次使用引导
  // 路由守卫: 无当前学期时重定向到 /semesters
  // 路由分发: 20 个路由，按需懒加载
}
```

#### API 客户端 (`api/api-client.ts`)

```typescript
// 统一处理 API 信封
// 返回解包后的 data
// 支持 AbortSignal
// 网络失败/非 JSON 响应/超时 → 统一兜底错误
```

#### 轮询 Hook (`hooks/use-material-polling.ts`)

```typescript
function useMaterialPolling(materials) {
  // 指数退避: 2s → 4s → 8s → 16s → 30s (上限)
  // 状态变化/手动刷新/页面重新可见 → 重置为 2s
  // 页面隐藏/离开/全部终态 → 停止轮询
}
```

### 7.3 共享类型关键接口

```typescript
// API 信封
interface ApiSuccess<T> { success: true; data: T; meta?: {...} }
interface ApiError { success: false; error: { code: string; message: string } }

// 共同业务对象
interface CourseInstanceDto { id, semesterId, name, retakeOfCourseInstanceId? }
interface AssessmentAttemptDto { id, courseInstanceId, attemptType, examAt, confirmationStatus }
interface StudyTaskDto { id, type, status, deadlineAt?, derivedOverdue, priorityBucket }
interface KnowledgeModuleDto { id, title, importance, difficulty, examRelevance?, learnStatus }
interface MaterialDto { id, fileType, status, hasNote?, noteId? }

// Converter 统一输出
interface ConverterResult { ok, sourceType, text?, metadata?, warnings?, error? }
```

---

## 8. 数据模型

### 8.1 存储拓扑

```text
APP_DATA_ROOT/
├── studybuddy.db                    # 全局索引库
│   ├── schema_migrations
│   ├── app_meta
│   ├── students
│   ├── parent_report_targets
│   ├── semesters                    # 学期目录
│   └── backup_records
├── config/
│   ├── ai.active.enc               # DPAPI 加密 AI 配置
│   ├── smtp.active.enc
│   ├── feishu.active.enc
│   └── state.json                   # 非秘密状态元数据
├── semesters/<semester-id>/
│   ├── semester.db                  # 学期业务库
│   │   ├── schema_migrations
│   │   ├── course_instances
│   │   ├── schedule_entries
│   │   ├── assessment_attempts
│   │   ├── assessment_date_changes
│   │   ├── study_tasks
│   │   ├── study_events
│   │   ├── materials
│   │   ├── normalized_texts
│   │   ├── structured_notes
│   │   ├── mind_maps
│   │   ├── knowledge_modules
│   │   ├── questions
│   │   ├── practice_sessions
│   │   ├── practice_answers
│   │   ├── mistakes
│   │   ├── mistake_evidence
│   │   ├── weak_points
│   │   ├── parent_reports
│   │   ├── report_deliveries
│   │   ├── mock_exam_papers
│   │   ├── mock_exam_questions
│   │   ├── mock_exam_attempts
│   │   ├── mock_exam_answers
│   │   ├── mock_exam_module_analyses
│   │   ├── material_chunks
│   │   ├── jobs
│   │   └── report_deliveries
│   ├── files/                       # 资料文件
│   ├── tmp/                         # 临时处理文件
│   └── parent-reports/              # 家长报告留档
├── tmp/
├── backups/
└── models/
```

### 8.2 学期状态机

```text
active → ready（staging 创建流程；current 由全局 app_meta 指定）
active → archived（显式归档，仅非当前学期）
```

- `status`：学期库记录当前为 `active`；`ready` 标记是否完成初始化（staging/ready/promote/current 流程，T09A 实现）。
- `archived_at`：非当前学期可归档，归档学期只读。
- 产品概念中的 `ACTIVE → TEACHING_ENDED → FOLLOW_UP → ARCHIVED` 是早期领域草案，不作为当前代码状态枚举。

### 8.3 Job 状态机

```text
pending → running → completed
pending → running → pending  (可重试)
pending → running → failed   (达到 max_attempts)
```

### 8.4 资料处理状态（S2 材料）

```text
pending → converting → note_generating → completed
pending → conversion_failed（可重试/人工补文）
note_generating → pending_quality_check（AI 不可用降级，可补文）
```

- `conversion_failed` 与 `pending_quality_check` 是恢复态：可触发重试或人工补文（`replace-text`）。
- 学习任务状态独立为 `todo → doing → pending_quality_check → done / skipped`（S1）。

### 8.5 考试尝试确认状态

```text
pending → confirmed / rejected / superseded
```

只有 `confirmed` 的考试才能驱动倒计时、计划和考前提醒。

---

## 9. API 接口说明

### 9.1 通用约定

- **基地址**：`http://127.0.0.1:3000/api`
- **请求格式**：JSON（上传使用 `multipart/form-data`）
- **响应信封**：`{ success: true, data: T }` 或 `{ success: false, error: { code, message } }`
- **分页**：`{ success: true, data: T[], meta: { page, pageSize, total } }`
- **错误码**：大写蛇形命名（如 `SEMESTER_NOT_FOUND`、`AI_NOT_CONFIGURED`）

### 9.2 核心 API 端点

#### 健康检查

```
GET /api/health → { version, timestamp }
```

#### 学习节奏 (S1)

```
POST   /api/courses                    创建课程
GET    /api/courses                    课程列表
PATCH  /api/courses/:id                更新课程
DELETE /api/courses/:id                删除课程
GET    /api/schedule-entries           课表条目列表
POST   /api/schedule-entries           新增课表条目
PATCH  /api/schedule-entries/:id       编辑课表条目
DELETE /api/schedule-entries/:id       移除课表条目
POST   /api/exams                      创建考试目标
GET    /api/exams                      考试列表
GET    /api/exams/:id                  考试详情（单考试查询）
PATCH  /api/exams/:id                  更新考试（名称/日期/目标）
PATCH  /api/exams/:id/confirmation     确认考试（pending 首次确认，幂等）
POST   /api/study-tasks                创建学习任务
GET    /api/study-tasks                任务列表
PATCH  /api/study-tasks/:id/status     更新任务状态
POST   /api/study-events               写入时间线事件
GET    /api/timeline                   学习时间线（支持 eventType 重复过滤）
```

#### 每日首页 (S1)

```
GET /api/daily-study-home?semesterId=...   每日学习首页数据
```

#### 资料笔记 (S2)

```
POST   /api/materials/upload                 上传资料
GET    /api/materials                        资料列表
GET    /api/materials/:id                    资料详情
GET    /api/materials/:id/original-pdf       原始 PDF 下载
POST   /api/materials/:id/retry-conversion   重试转换
POST   /api/materials/:id/retry-ai-generation 重试 AI 生成笔记
POST   /api/materials/:id/generate-note      生成笔记
POST   /api/materials/:id/replace-text       人工补文（恢复替换正文）
GET    /api/notes/:id                        获取笔记
PATCH  /api/notes/:id                        更新笔记
GET    /api/knowledge-modules                知识模块列表
PATCH  /api/knowledge-modules/:id            更新知识模块状态
```

#### 限时练习 (S3)

```
POST   /api/practice-sessions                  创建练习（AI 生成题目入库）
GET    /api/practice-sessions/history          练习历史列表（分页、按时间倒序）
GET    /api/practice-sessions/:id              获取练习详情（作答前不含答案）
GET    /api/practice-sessions/:id/history-result 练习历史结果（逐题对错）
POST   /api/practice-sessions/:id/submit       提交作答并批改
```

#### 错题改错 (S4)

```
GET    /api/mistakes                  错题列表
GET    /api/mistakes/:id              错题详情
PATCH  /api/mistakes/:id/error-cause  确认错因
PATCH  /api/mistakes/:id/status       更新掌握状态
POST   /api/mistakes/:id/redo         创建重做练习
GET    /api/weak-points               薄弱点列表
```

#### 期末冲刺 (S5)

```
POST   /api/mock-exam-papers              生成模拟卷
GET    /api/mock-exam-papers/:id          获取模拟卷（作答前不含答案）
POST   /api/mock-exam-papers/:id/attempts 开始模拟考尝试
GET    /api/mock-exam-attempts/:id        获取模拟考作答与结果
POST   /api/mock-exam-attempts/:id/submit 提交模拟考
GET    /api/assessment-attempts/:id/cram-cards  临考速背卡（确定性只读）
GET    /api/assessment-attempts/:id/cram-plan   冲刺计划（确定性只读）
```

#### 学期管理

```
POST   /api/semesters/preview      课表预览（OCR/手工确认）
POST   /api/semesters              创建学期（staging → ready → current）
GET    /api/semesters              学期列表
GET    /api/semesters/current      当前学期
PUT    /api/semesters/current      切换当前学期
GET    /api/semesters/archived     已归档学期列表
POST   /api/semesters/:id/archive  归档非当前学期
```

#### 课堂采集 (S7)

```
POST   /api/class-captures/transcribe   上传受控 PCM WAV 并同步转写
POST   /api/class-captures/save-to-notes 将可编辑转写保存为 S2 文本资料
```

#### 配置中心

```
GET    /api/config/status                     配置状态
GET    /api/config/presets                    Provider 官方预设目录
POST   /api/config/ai/test-provider           测试 AI Provider
POST   /api/config/:channel/test-and-activate 测试并激活配置
POST   /api/config/:channel/retest            重新测试
```

#### 开发用端点（`/api/dev`，仅开发/测试模式挂载，生产禁用）

```
POST   /api/dev/init-semester        初始化学期（开发）
GET    /api/dev/db-health            数据库健康（开发）
POST   /api/dev/ai/generate          AI 生成（开发）
POST   /api/dev/storage/upload       存储上传（开发）
GET    /api/dev/storage/download     存储下载（开发）
DELETE /api/dev/storage/delete       存储删除（开发）
GET    /api/dev/storage/exists       存储存在检查（开发）
POST   /api/dev/converter/pdf        转换 PDF（开发）
POST   /api/dev/converter/image      转换图片/OCR（开发）
POST   /api/dev/converter/text       转换文本（开发）
POST   /api/dev/converter/docx       转换 DOCX（开发）
POST   /api/dev/converter/pptx       转换 PPTX（开发）
POST   /api/dev/converter/url        抓取 URL（开发）
```

#### 限时练习 (S3)

```
POST   /api/practice-sessions                  创建练习（AI 生成题目入库）
GET    /api/practice-sessions/history          练习历史列表（分页、按时间倒序）
GET    /api/practice-sessions/:id              获取练习详情（作答前不含答案）
GET    /api/practice-sessions/:id/history-result 练习历史结果（逐题对错）
POST   /api/practice-sessions/:id/submit       提交作答并批改
```

#### 错题改错 (S4)

```
GET    /api/mistakes                  错题列表
GET    /api/mistakes/:id              错题详情
PATCH  /api/mistakes/:id/error-cause  确认错因
PATCH  /api/mistakes/:id/status       更新掌握状态
POST   /api/mistakes/:id/redo         创建重做练习
GET    /api/weak-points               薄弱点列表
```

#### 期末冲刺 (S5)

```
POST   /api/mock-exam-papers              生成模拟卷
GET    /api/mock-exam-papers/:id          获取模拟卷（作答前不含答案）
POST   /api/mock-exam-papers/:id/attempts 开始模拟考尝试
GET    /api/mock-exam-attempts/:id        获取模拟考作答与结果
POST   /api/mock-exam-attempts/:id/submit 提交模拟考
GET    /api/assessment-attempts/:id/cram-cards  临考速背卡（确定性只读）
GET    /api/assessment-attempts/:id/cram-plan   冲刺计划（确定性只读）
```

#### 学期管理

```
POST   /api/semesters/preview      课表预览（OCR/手工确认）
POST   /api/semesters              创建学期（staging → ready → current）
GET    /api/semesters              学期列表
GET    /api/semesters/current      当前学期
PUT    /api/semesters/current      切换当前学期
GET    /api/semesters/archived     已归档学期列表
POST   /api/semesters/:id/archive  归档非当前学期
```

#### 课堂采集 (S7)

```
POST   /api/class-captures/transcribe   上传受控 PCM WAV 并同步转写
POST   /api/class-captures/save-to-notes 将可编辑转写保存为 S2 文本资料
```

#### 配置中心

```
GET    /api/config/status                     配置状态
GET    /api/config/presets                    Provider 官方预设目录
POST   /api/config/ai/test-provider           测试 AI Provider
POST   /api/config/:channel/test-and-activate 测试并激活配置
POST   /api/config/:channel/retest            重新测试
```

#### 开发用端点（`/api/dev`，仅开发/测试模式挂载，生产禁用）

```
POST   /api/dev/init-semester        初始化学期（开发）
GET    /api/dev/db-health            数据库健康（开发）
POST   /api/dev/ai/generate          AI 生成（开发）
POST   /api/dev/storage/upload       存储上传（开发）
GET    /api/dev/storage/download     存储下载（开发）
DELETE /api/dev/storage/delete       存储删除（开发）
GET    /api/dev/storage/exists       存储存在检查（开发）
POST   /api/dev/converter/pdf        转换 PDF（开发）
POST   /api/dev/converter/image      转换图片/OCR（开发）
POST   /api/dev/converter/text       转换文本（开发）
POST   /api/dev/converter/docx       转换 DOCX（开发）
POST   /api/dev/converter/pptx       转换 PPTX（开发）
POST   /api/dev/converter/url        抓取 URL（开发）
```

---

## 10. 前端路由与页面

### 10.1 完整路由表

| 路由                                                 | 页面组件                    | 子系统 | 加载方式 |
| ---------------------------------------------------- | --------------------------- | ------ | -------- |
| `/`                                                  | `DailyStudyHomePage`        | S1     | 同步     |
| `/courses`                                           | `CoursePage`                | S1     | 同步     |
| `/materials`                                         | `MaterialUploadPage`        | S2     | 同步     |
| `/notes/:noteId`                                     | `NotePage`                  | S2     | 懒加载   |
| `/exams/:examId`                                     | `ExamWorkbenchPage`         | S1/S5  | 懒加载   |
| `/exams/:examId/practice`                            | `PracticeStartPage`         | S3     | 懒加载   |
| `/practice-sessions/:sessionId`                      | `PracticeSessionPage`       | S3     | 懒加载   |
| `/practice-sessions/:sessionId/result`               | `PracticeResultPage`        | S3     | 懒加载   |
| `/semesters/:semesterId/practice-history`            | `PracticeHistoryPage`       | S3     | 懒加载   |
| `/semesters/:semesterId/practice-history/:sessionId` | `PracticeHistoryResultPage` | S3     | 懒加载   |
| `/exams/:examId/mistakes`                            | `MistakeListPage`           | S4     | 懒加载   |
| `/mistakes`                                          | `MistakeListPage`           | S4     | 懒加载   |
| `/mistakes/:mistakeId`                               | `MistakeDetailPage`         | S4     | 懒加载   |
| `/exams/:examId/mock-exam`                           | `MockExamStartPage`         | S5     | 懒加载   |
| `/mock-exam-papers/:paperId`                         | `MockExamPaperPage`         | S5     | 懒加载   |
| `/mock-exam-attempts/:attemptId`                     | `MockExamSessionPage`       | S5     | 懒加载   |
| `/mock-exam-attempts/:attemptId/result`              | `MockExamResultPage`        | S5     | 懒加载   |
| `/exams/:examId/cram`                                | `CramCardsPage`             | S5     | 懒加载   |
| `/exams/:examId/cram-plan`                           | `CramPlanPage`              | S5     | 懒加载   |
| `/semesters`                                         | `SemesterPage`              | 共同   | 同步     |
| `/settings`                                          | `SettingsPage`              | 共同   | 懒加载   |

### 10.2 页面加载策略

- 核心页面（首页、课程、资料、学期）同步加载，确保首屏可用
- 二级页面（笔记、练习、错题、冲刺）懒加载，减少首屏体积
- 使用 `Suspense` + `PageState` 提供加载过渡

---

## 11. 项目运行方式

### 11.1 开发环境

**前置条件**：

- Windows 10/11
- Node.js 20/22/24 LTS
- pnpm
- Python 3.10+ x64（用于 OCR）

**启动步骤**：

```powershell
# 1. 安装依赖
cd h:\ai-studybuddy
pnpm install

# 2. 创建 .env.local（在仓库根目录）
# 必须包含 APP_DATA_ROOT
$env:APP_DATA_ROOT = 'H:\ai-studybuddy-tmp\runs\dev-001'
# 可选配置 AI Provider、SMTP、飞书等

# 3. 同时启动前后端
pnpm dev

# 4. 浏览器访问
# http://localhost:5173 (Vite 开发服务器)
# 后端 API: http://localhost:3000/api
```

### 11.2 类型检查与构建

```powershell
pnpm type-check                          # 全量类型检查
pnpm -r --filter backend run build      # 后端构建
pnpm -r --filter @ai-studybuddy/frontend run build  # 前端构建
pnpm build                               # 全量构建
```

### 11.3 测试

```powershell
pnpm test                                # 全量测试（先 build 再 test）
pnpm -r --filter @ai-studybuddy/backend run test   # 仅后端测试
pnpm -r --filter @ai-studybuddy/frontend run test  # 仅前端测试
pnpm test:e2e                            # Playwright E2E 测试
```

### 11.4 隔离数据运行

```powershell
# 设置隔离数据根，避免污染正式数据
$env:APP_DATA_ROOT = 'H:\ai-studybuddy-tmp\runs\<task-id>'
pnpm -r --filter backend run dev
```

### 11.5 代码治理

```powershell
# 文档治理检查
powershell -ExecutionPolicy Bypass -File scripts/check-docs-governance.ps1

# 空白行检查
git diff --check
```

---

## 12. 部署方式

### 12.1 部署形态

AI StudyBuddy 以 Windows 本地应用方式部署，不使用 Docker、WSL2 或云端服务。

### 12.2 部署包构建与一键打包 ZIP

```powershell
# 在 ai-studybuddy 仓库执行

# 方式一：仅构建产物（编译后端 + 前端）
pnpm run build:production

# 方式二：完整构建 + 打包为 ZIP（一键打包）
powershell -ExecutionPolicy Bypass -File scripts/build-deployment-package.ps1 -OutputRoot <输出目录>

# 输出：
#   <输出目录>/          ← 解压即用的部署包目录
#   <输出目录>.zip        ← 分发的 ZIP 压缩包
```

ZIP 包内容：`app/backend/`（编译后后端含 SPA 前端）、`app/shared/`、`scripts/`（部署脚本）、`deployment/`（运行时兼容性配置）、`deployment-manifest.json`、`README-Windows.md`。

排除项：`.git`、`node_modules`、`.env.local`、真实数据、密钥、日志、缓存、模型、WSL venv、Playwright 证据。

### 12.3 一键解压安装（目标机器）

```powershell
# 1. 解压 ZIP 到任意目录
# 2. 进入解压目录，运行引导安装
$installRoot = Join-Path $env:LOCALAPPDATA 'AIStudyBuddy'
.\scripts\bootstrap-runtime.ps1 -InstallRoot $installRoot -AppSource .\app -PythonPath 'C:\Path\To\python.exe'

# 3. 安装检查
.\scripts\check-installation.ps1 -InstallRoot $installRoot

# 4. 启动
.\scripts\start-production.ps1 -InstallRoot $installRoot

# 5. 浏览器打开 http://127.0.0.1:3000/
```

**注意**：当前安装仍需用户手动安装 Node.js 24 LTS 和 Python 3.10-3.12 x64 两个前置运行时。`bootstrap-runtime.ps1` 自动完成 npm ci、Python venv 创建和 OCR 依赖安装，但不会自动安装 Node.js 或 Python 本身。

### 12.4 日常运维

```powershell
.\scripts\start-production.ps1 -InstallRoot $installRoot   # 启动
.\scripts\stop-production.ps1 -InstallRoot $installRoot    # 停止
.\scripts\check-installation.ps1 -InstallRoot $installRoot # 检查
```

### 12.5 家长报告任务计划

```powershell
# 注册（配置 SMTP/飞书后）
.\scripts\register-parent-report-task.ps1 -InstallRoot $installRoot

# 注销
.\scripts\unregister-parent-report-task.ps1 -InstallRoot $installRoot
```

### 12.6 安装后目录结构

```text
%LOCALAPPDATA%\AIStudyBuddy\
├── app\              # 编译后应用
├── config\           # production.env + DPAPI 加密配置
├── data\             # SQLite + materials/
├── logs\             # 脱敏运行日志
├── tmp\              # 可清理临时文件
├── models\           # OCR/ASR 模型缓存
├── backups\          # 备份点
└── runtime\venv\     # OCR Python 虚拟环境
```

---

## 13. 子系统依赖关系

### 13.1 依赖图

```text
共同底座 (Shared Foundation)
  ├── S1 学习节奏 ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
  ├── S2 资料笔记 ← ─ S7 课堂采集 ─ ─ ─ ─ ─ ┤
  │     ↓                                    │
  ├── S3 限时练习                             │
  │     ↓                                    │
  ├── S4 错题改错 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
  │     ↓
  ├── S5 期末冲刺 (依赖 S3/S4 数据)
  ├── S6 家长观察 (聚合 S1-S4 脱敏数据)
  └── S7 课堂采集 (输出到 S2 资料管道)
```

### 13.2 跨子系统共享对象

| 对象                | 创建者      | 消费者      |
| ------------------- | ----------- | ----------- |
| `CourseInstance`    | S1          | S1-S6       |
| `AssessmentAttempt` | S1          | S1/S5/S6    |
| `KnowledgeModule`   | S2          | S1/S3/S4/S5 |
| `StudyTask`         | S1          | S1/S6       |
| `StudyEvent`        | S1/S2/S3/S4 | S1/S6       |
| `Material`          | S2/S7       | S2          |
| `Question`          | S3          | S3/S4/S5    |
| `PracticeSession`   | S3          | S3/S4/S6    |
| `Mistake`           | S4          | S4/S5/S6    |
| `WeakPoint`         | S4          | S4/S5       |

### 13.3 开发顺序

```text
Phase 0:   共同底座
Phase 0.8: S1 + S2 (最小闭环)
Phase 1:   S3 + S4 + S6 简版 (完整学习闭环)
Phase 1.5: S7-MVP (课堂录音)
Phase 2:   S5 (期末冲刺)
Phase 3:   安全、性能与运维增强 (进行中)
```

---

## 附录 A：关键文件索引

### 必读文档

| 文档       | 路径                                             | 用途           |
| ---------- | ------------------------------------------------ | -------------- |
| 文档索引   | `docs/00-文档索引-Index.md`                      | 文档导航与门禁 |
| 总 PRD     | `docs/01-总PRD-产品需求-Product-Requirements.md` | 产品目标与边界 |
| 子系统地图 | `docs/02-七子系统地图-Scenario-Systems.md`       | 七个子系统边界 |
| 架构文档   | `docs/08-共同底座架构-Architecture.md`           | 共同底座设计   |
| 任务清单   | `docs/04-开发任务清单-Todo-List.md`              | 开发任务与状态 |
| 开发规范   | `docs/12-开发规范-Dev-Rules.md`                  | 16 步协作流程  |
| 后端规范   | `docs/10-后端开发规范-Backend-Guidelines.md`     | 后端编码约定   |
| 前端规范   | `docs/11-前端开发规范-Frontend-Guidelines.md`    | 前端编码约定   |
| 部署指南   | `docs/13-部署运维指南-Deployment.md`             | 部署与运维     |
| 组件清单   | `docs/05-开源组件装配-Open-Source-Foundation.md` | 开源组件       |

### 子系统 PRD

| 子系统 | 文档                                                        |
| ------ | ----------------------------------------------------------- |
| S1     | `docs/subsystems/03-S1学习节奏子系统PRD-StudyRhythm.md`     |
| S2     | `docs/subsystems/03-S2-资料笔记子系统PRD-NoteBuilder.md`    |
| S3     | `docs/subsystems/03-S3-限时练习子系统PRD-PracticeRunner.md` |
| S4     | `docs/subsystems/03-S4-错题改错子系统PRD-ErrorFixer.md`     |
| S5     | `docs/subsystems/08-S5-期末冲刺子系统PRD-ExamCrammer.md`    |
| S6     | `docs/subsystems/06-S6-家长观察子系统PRD-ParentReport.md`   |
| S7     | `docs/subsystems/07-S7-课堂录音子系统PRD-ClassCapture.md`   |

### 核心源码入口

| 文件                                                   | 作用               |
| ------------------------------------------------------ | ------------------ |
| `packages/backend/src/server.ts`                       | 后端入口           |
| `packages/backend/src/bootstrap.ts`                    | 启动引导           |
| `packages/backend/src/app.ts`                          | Express 应用组装   |
| `packages/backend/src/config/env.ts`                   | 环境变量           |
| `packages/backend/src/db/connection.ts`                | 数据库连接         |
| `packages/backend/src/db/paths.ts`                     | 路径生成           |
| `packages/backend/src/adapters/ai/router.ts`           | AI Provider Router |
| `packages/backend/src/config/configuration-service.ts` | 配置中心           |
| `packages/shared/src/types.ts`                         | 共享类型           |
| `packages/frontend/src/app.tsx`                        | 前端路由壳         |
| `packages/frontend/src/main.tsx`                       | 前端入口           |
| `packages/frontend/src/api/api-client.ts`              | API 客户端         |

---

## 附录 B：测试覆盖

| 层级 | 测试框架            | 文件数 | 说明                 |
| ---- | ------------------- | ------ | -------------------- |
| 后端 | Node.js Test Runner | ~70    | 集成测试，不 mock DB |
| 前端 | Vitest              | ~26    | 组件/API 客户端测试  |
| E2E  | Playwright          | 15     | 浏览器端到端验收     |

---

## 附录 C：当前状态与下一步

- **已完成**：S1-S6 主线、S7-MVP、Phase 2 S5、POST-PHASE2 全系统验证、**开发机 P0 验收全绿（2026-07-30 r6）**
- **进行中**：Phase 3 高权重必做项恢复规划（T02-R1~~R4、T04-1~~T04-3、T05-1~T05-3）
- **下一步**：2026-08-01 使用电脑空数据迁移与重复验收
- **未开始**：完整 S7、S3 Worker、P1 外部能力配置、真实备份恢复

---

## 附录 D：现状评估与关键发现

> 本附录针对 2026-07-30 日审查中提出的六个关键问题，逐一给出代码级事实和评估。

### D.1 部署仓库 vs 开发仓库：缺失了什么

#### 部署仓库 (`h:\StudyBuddy`) 实际包含

| 内容                                        | 状态 |
| ------------------------------------------- | ---- |
| `app/backend/`（编译后 Express + 内嵌 SPA） | 存在 |
| `app/shared/`（编译后共享类型）             | 存在 |
| `app/requirements-ocr.txt`                  | 存在 |
| `scripts/`（11 个部署脚本 + lib 库）        | 存在 |
| `deployment/`（runtime-compatibility.json） | 存在 |
| `docs/`（6 份用户文档）                     | 存在 |
| `deployment-manifest.json`                  | 存在 |
| `README-Windows.md`                         | 存在 |

#### 未打包到部署仓库的内容（预期内）

| 内容                                  | 原因                   |
| ------------------------------------- | ---------------------- |
| 前端源码 (`packages/frontend/src/`)   | 已编译为 `public/` SPA |
| 后端源码 (`packages/backend/src/`)    | 已编译为 `dist/` JS    |
| 测试文件（后端 65+、前端 27、E2E 15） | 部署包不需要测试       |
| `.plans/` 计划文档                    | 仅开发用               |
| `pnpm-workspace.yaml`                 | 部署包用 npm ci        |
| 设计文档 (`docs/subsystems/` 等)      | 部署包有精简用户文档   |
| `.git`                                | 不应打包               |

**结论**：部署仓库内容完整，缺失项是预期内的设计选择，不是遗漏。

#### 需要关注：部署包里的 `package-lock.json`

`bootstrap-runtime.ps1` 第 44 行检查 `package-lock.json` 必须存在。该文件来自 `deployment/backend-package-lock.json`（`build-deployment-package.ps1` 第 35 行复制）。这个 lock 文件需要与 Node 24 + Windows x64 平台的 `better-sqlite3` 原生模块匹配，否则 `npm ci` 会失败。

---

### D.2 SQLite 数据存储：放在哪里、存了什么、如何防损坏

#### 存储位置

```text
APP_DATA_ROOT/
├── studybuddy.db                    ← 全局索引库
├── semesters/<semester-id>/
│   ├── semester.db                  ← 学期业务库
│   ├── files/                       ← 上传资料原文件
│   ├── tmp/                         ← OCR/转换临时文件
│   └── parent-reports/              ← 家长报告留档
├── tmp/
├── backups/
└── models/
```

#### 全局库 (studybuddy.db) 的表

| 表                      | 数据                                            |
| ----------------------- | ----------------------------------------------- |
| `app_meta`              | 系统配置键值对                                  |
| `students`              | 学生档案                                        |
| `parent_report_targets` | 家长报告渠道                                    |
| `semesters`             | 学期索引（含 `db_relative_path`、`ready` 标志） |
| `backup_records`        | 备份记录                                        |
| `schema_migrations`     | 迁移版本                                        |

#### 学期库 (semester.db) 的表

| 表                    | 数据                            |
| --------------------- | ------------------------------- |
| `course_instances`    | 课程实例（含重修关系）          |
| `assessment_attempts` | 考试目标（含确认状态）          |
| `study_tasks`         | 学习任务                        |
| `study_events`        | 学习时间线/报告证据             |
| `jobs`                | 后台持久化作业                  |
| `materials`           | 资料文件索引                    |
| `normalized_texts`    | 格式转换后的纯文本              |
| `structured_notes`    | AI 生成的结构化笔记（Markdown） |
| `mind_maps`           | 思维导图数据（Markmap JSON）    |
| `knowledge_modules`   | 可考知识模块                    |
| `parent_reports`      | 家长报告脱敏冻结快照            |
| `report_deliveries`   | 报告渠道发送状态                |
| `schema_migrations`   | 迁移版本                        |

#### 数据库损坏防护机制

**已有的保护**：

| 机制                  | 实现位置                          | 说明                                                                       |
| --------------------- | --------------------------------- | -------------------------------------------------------------------------- |
| WAL 模式              | `connection.ts` 第 21 行          | 所有库打开即启用 `PRAGMA journal_mode = WAL`，写操作不阻塞读               |
| 外键约束              | `connection.ts` 第 22 行          | `PRAGMA foreign_keys = ON`                                                 |
| integrity_check       | `connection.ts` 第 71 行          | `runIntegrityCheck()` 可随时调用 `PRAGMA integrity_check`                  |
| 备份前 checkpoint     | `connection.ts` 第 104 行         | `backupDb()` 先 `wal_checkpoint(TRUNCATE)` 再复制，确保 WAL 内容写入主文件 |
| 备份后 integrity 验证 | `backups.ts` 第 67 行             | 备份副本立即做 integrity_check，失败则删除备份                             |
| 恢复前 integrity 验证 | `backups.ts` 第 92 行             | 恢复前对备份副本做 integrity_check                                         |
| 恢复后 integrity 验证 | `backups.ts` 第 102 行            | 恢复后对目标库做 integrity_check                                           |
| 恢复时清除 WAL/SHM    | `backups.ts` 第 97 行             | 删除旧 `-wal`/`-shm` 防止旁路日志污染                                      |
| 安装检查              | `check-installation.ps1` 第 96 行 | `sqlite-precheck` 做 quick_check + 版本比对                                |
| 数据完整性测试        | `test-data-integrity.ps1`         | 可单独验证数据文件完整性                                                   |
| 学期初始化补偿        | `semester-initializer.ts`         | 跨文件系统操作失败时执行补偿清理，不留半成品                               |

**没有的保护**：

| 缺失                            | 影响                             |
| ------------------------------- | -------------------------------- |
| 自动定期备份                    | 备份需手动执行 `backup-data.ps1` |
| 损坏自动修复                    | 没有自动回滚到最近备份的机制     |
| 启动前自动 integrity_check      | 启动时不会自动检查数据库完整性   |
| SQLite 文件被外部进程锁定的处理 | 没有文件锁检测或重试             |

---

### D.3 备份导出与恢复导入

#### 已有的备份/导出能力

| 能力         | 实现                                  | 粒度                                                                                       |
| ------------ | ------------------------------------- | ------------------------------------------------------------------------------------------ |
| 整库备份     | `backup-data.ps1`                     | 已批准逻辑数据子集（payload 目录 + v2 manifest + 逐文件 SHA-256 + 只读标记），非整个目录     |
| 编程式备份   | `backups.ts` `createDatabaseBackup()` | 全局库或学期库                                                                             |
| 备份记录     | `backup_records` 表                   | 每次备份登记                                                                               |
| 备份验证     | `test-data-integrity.ps1 -BackupPath` | 验证备份 manifest                                                                          |
| 备份 SHA-256 | `backup-data.ps1`                     | 每个文件计算哈希并写入 manifest                                                            |

#### 恢复能力：**写入被故意禁用**

```powershell
# restore-data.ps1 第 24 行
New-AIStudyBuddyDataBoundaryError 'RESTORE_WRITE_DISABLED'
```

恢复脚本可以验证备份（`-EnableWrite` 不传时只读验证），但实际写入恢复被明确禁用。这是 Phase 3 的安全范围，需要"单独批准的 stop-service、recovery-point 和中断处理实现"。

#### **缺失的能力**

| 缺失               | 说明                                                                 |
| ------------------ | -------------------------------------------------------------------- |
| **按学期导出笔记** | 没有导出某学期/某课程全部笔记为 Markdown/PDF 的功能                  |
| **按课程导出资料** | 没有导出某课程全部资料和笔记的打包功能                               |
| **恢复写入**       | `RESTORE_WRITE_DISABLED`，Phase 3 未完成                             |
| **笔记单独备份**   | 笔记存储在 `structured_notes` 表的 Markdown 字段中，没有独立文件导出 |

---

### D.4 安装便捷性：一键打包 → 一键解压 → 一键启动

#### 当前状态

**一键打包**：已实现。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-deployment-package.ps1 -OutputRoot D:\release
# 输出：D:\release\ 目录 + D:\release.zip
```

**一键解压**：已实现。ZIP 解压到任意目录即可。

**一键启动**：需要两步。

```powershell
# 步骤 1：引导安装（首次，约 2-5 分钟）
.\scripts\bootstrap-runtime.ps1 -InstallRoot $installRoot -AppSource .\app -PythonPath 'C:\Python312\python.exe'

# 步骤 2：启动（每次）
.\scripts\start-production.ps1 -InstallRoot $installRoot
```

#### "70s UNIX" 问题的根源

当前安装流程有三个摩擦点：

1. **Node.js 24 需要用户手动安装**。`bootstrap-runtime.ps1` 第 48-50 行检查 Node 版本，不满足则报错退出。
2. **Python 3.10-3.12 x64 需要用户手动安装**。第 85-90 行检查 Python 版本和架构。
3. **`npm ci` 需要网络**下载原生依赖（`better-sqlite3` 等），网络不稳定时可能失败（虽已内置 3 次重试）。

#### 改进建议

| 改进                                | 难度 | 效果                   |
| ----------------------------------- | ---- | ---------------------- |
| 内嵌 Node.js portable 到 ZIP        | 中   | 消除 Node 手动安装     |
| 内嵌 Python embeddable 到 ZIP       | 中   | 消除 Python 手动安装   |
| 预编译 native `.node` 模块          | 低   | 消除 `npm ci` 网络依赖 |
| 一键安装脚本（自动检测+安装运行时） | 中   | 真正的一键安装         |
| 静默安装模式                        | 低   | 减少交互               |

---

### D.5 系统组件功能是否正常

#### 当前状态：开发机 P0 已通过

| 层次           | 状态                      | 证据                                                                                                                              |
| -------------- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 开发机构建     | 通过                      | `assemble-production.ps1` 成功，`build-deployment-package.ps1` 成功                                                               |
| 开发机 P0 验收 | **通过（2026-07-30 r6）** | 17 项 P0 全部通过：安装、启停、学期、课程、资料、OCR、笔记、练习、错题、模拟考、速背、冲刺、重启读回、AI 降级、密钥边界、网络边界 |
| P1 外部能力    | 暂未配置                  | DeepSeek、Kimi K3、SMTP、飞书、计划任务均未配置                                                                                   |
| 用户电脑验收   | 未开始                    | 2026-08-01 计划执行                                                                                                               |     |

#### 功能验收清单

部署仓库文档 `docs/02-功能验收清单.md` 中应包含详细验收项。验收分为三层：

- **P0 核心必测**：干净包、隔离安装、启动/停止、loopback、本地学习闭环、OCR、重启读回、脱敏边界
- **P1 受控后测**：DeepSeek、Kimi K3、SMTP、飞书、日报去重、计划任务
- **P2 后续范围**：cc-switch、真实数据迁移、备份/恢复写入、Phase 3

#### 已知限制

- AI Provider 需要用户自行配置 API Key（通过设置中心，DPAPI 加密存储）
- SMTP/飞书需要用户自行配置
- 恢复写入被禁用（Phase 3 范围）
- whisper.cpp 语音转写需要用户自行下载模型文件

---

### D.6 测试覆盖评估

#### 测试文件统计

| 层级 | 框架                | 文件数    | 覆盖范围                                  |
| ---- | ------------------- | --------- | ----------------------------------------- |
| 后端 | Node.js Test Runner | **65 个** | 所有子系统 API、配置、安全、边界、Adapter |
| 前端 | Vitest              | **27 个** | 所有页面组件、API 客户端、Hooks、导航     |
| E2E  | Playwright          | **15 个** | 所有子系统 UI 流程、响应式、导航          |

#### 后端测试覆盖详细

| 子系统      | 测试文件                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1 学习节奏 | `study-rhythm-api.test.mjs`、`daily-study-home-api.test.mjs`                                                                                                                                                                                                                                                                                                                                                                                                                          |
| S2 资料笔记 | `note-builder-api.test.mjs`、`note-generation-parsing.test.mjs`、`converter.test.mjs`、`docx-converter.test.mjs`、`pptx-converter.test.mjs`、`storage-adapter.test.mjs`、`url-fetcher.test.mjs`、`manual-text-recovery-api.test.mjs`、`manual-text-recovery-worker.test.mjs`                                                                                                                                                                                                          |
| S3 限时练习 | `practice-generation-api.test.mjs`、`practice-submit-api.test.mjs`、`practice-schema.test.mjs`                                                                                                                                                                                                                                                                                                                                                                                        |
| S4 错题改错 | `error-fixer-archive-api.test.mjs`、`error-fixer-schema.test.mjs`、`error-fixer-t04b-api.test.mjs`、`feedback-rules-service.test.mjs`                                                                                                                                                                                                                                                                                                                                                 |
| S5 期末冲刺 | `mock-exam-api.test.mjs`、`mock-exam-schema.test.mjs`、`cram-cards-api.test.mjs`、`cram-plan-api.test.mjs`                                                                                                                                                                                                                                                                                                                                                                            |
| S6 家长报告 | `parent-report-service.test.mjs`、`parent-report-delivery-service.test.mjs`、`parent-report-runner.test.mjs`、`parent-report-scheduler-script.test.mjs`                                                                                                                                                                                                                                                                                                                               |
| S7 课堂采集 | `s7-class-capture-api.test.mjs`                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 配置中心    | `configuration-service.test.mjs`、`config-api.test.mjs`、`config-registry.test.mjs`、`config-source-governance.test.mjs`、`config-validation-redaction.test.mjs`、`connection-tester.test.mjs`、`runtime-configuration.test.mjs`、`secure-store.test.mjs`                                                                                                                                                                                                                             |
| 安全/边界   | `secret-scan-boundary.test.mjs`、`trust-anchor-contract.test.mjs`、`trusted-approval-contract.test.mjs`、`trusted-approval-test-seam-isolation.test.mjs`、`verifier-integrity-gate.test.mjs`、`nofollow-contract.test.mjs`、`production-attack-surface-error-boundary.test.mjs`、`env-boundary.test.mjs`、`env-error-redaction.test.mjs`、`subprocess-environment-boundary.test.mjs`、`runtime-log-boundary.test.mjs`、`api-origin-policy.test.mjs`、`db-readonly-no-create.test.mjs` |
| 部署        | `deployment-output-delete-boundary.test.mjs`、`deployment-powershell-compatibility.test.mjs`、`production-static-host.test.mjs`、`app-bootstrap.test.mjs`                                                                                                                                                                                                                                                                                                                             |
| 其他        | `ai-router.test.mjs`、`ocr-converter-runtime.test.mjs`、`semester-initialization.test.mjs`、`semester-selector-api.test.mjs`、`semester-archive-api.test.mjs`、`semester-ocr-runtime-config.test.mjs`、`dev-converter-api.test.mjs`、`dev-storage-api.test.mjs`                                                                                                                                                                                                                       |

#### 前端测试覆盖详细

| 类型       | 测试文件                                                                                                                                                                                                                                                                                                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 页面组件   | `daily-study-home-page.test.tsx`、`course-page.test.tsx`、`material-upload-page.test.tsx`、`note-page.test.tsx`、`exam-workbench-page.test.tsx`、`practice-pages.test.tsx`、`practice-history-pages.test.tsx`、`mistake-pages.test.tsx`、`mock-exam-pages.test.tsx`、`cram-cards-page.test.tsx`、`cram-plan-page.test.tsx`、`semester-page.test.tsx`、`settings-page.test.tsx` |
| 通用组件   | `app-navigation.test.tsx`、`exam-context-nav.test.tsx`、`page-state.test.tsx`、`lazy-mind-map.test.tsx`                                                                                                                                                                                                                                                                        |
| API 客户端 | `api-client.test.ts`、`study-rhythm-api.test.ts`、`practice-runner-api.test.ts`、`cram-cards-api.test.ts`、`cram-plan-api.test.ts`、`mock-exam-api.test.ts`、`daily-study-home-api.test.ts`、`semester-api.test.ts`                                                                                                                                                            |
| Hooks      | `use-material-polling.test.ts`                                                                                                                                                                                                                                                                                                                                                 |
| 应用级     | `app-semester.test.tsx`                                                                                                                                                                                                                                                                                                                                                        |

#### E2E 测试覆盖

| Spec                                   | 覆盖流程       |
| -------------------------------------- | -------------- |
| `student-journey.spec.ts`              | 完整学生旅程   |
| `daily-study-home.spec.ts`             | 每日首页       |
| `course-schedule-exam-goals.spec.ts`   | 课程与考试目标 |
| `practice-runner.spec.ts`              | 练习           |
| `practice-history-archive.spec.ts`     | 练习历史       |
| `error-fixer.spec.ts`                  | 错题改错       |
| `mock-exam.spec.ts`                    | 模拟考         |
| `cram-cards.spec.ts`                   | 临考速背       |
| `cram-plan.spec.ts`                    | 冲刺计划       |
| `exam-workbench.spec.ts`               | 考试工作台     |
| `semester-selector.spec.ts`            | 学期管理       |
| `settings-provider-presets.spec.ts`    | 配置中心       |
| `global-navigation-responsive.spec.ts` | 导航与响应式   |
| `markmap-lazy-load.spec.ts`            | 思维导图懒加载 |
| `timeline.spec.ts`                     | 学习时间线     |

#### 测试覆盖评估结论

| 维度       | 评估                                                           |
| ---------- | -------------------------------------------------------------- |
| 子系统覆盖 | 全部 7 个子系统 + 共同底座 + 配置中心有独立测试                |
| 测试层次   | 单元/集成（后端）、组件（前端）、端到端（E2E）三层覆盖         |
| 边界测试   | 安全边界、环境变量、路径逃逸、API Origin、日志脱敏均有专项测试 |
| 测试独立性 | 后端集成测试不 mock DB，前端组件测试不依赖后端                 |
| 待确认     | 测试通过率（最近一次全量 `pnpm test` 结果）                    |
| 缺失       | 没有性能测试、没有压力测试、没有长时间运行稳定性测试           |

---

## 附录 E：总览表

| 问题               | 现状                                                      | 评级     |
| ------------------ | --------------------------------------------------------- | -------- |
| 部署仓库内容完整性 | 完整，缺失项是设计选择                                    | 正常     |
| SQLite 数据存储    | 双库模型，全局+学期，结构清晰                             | 正常     |
| 数据库损坏防护     | WAL+FK+integrity_check+backup 校验，但无自动定期备份      | 基本够用 |
| 备份导出           | 整库备份可用，但无按学期/课程导出笔记功能                 | 有缺口   |
| 恢复导入           | 写入被故意禁用，Phase 3 待实现                            | 未完成   |
| 一键打包 ZIP       | `build-deployment-package.ps1` 已实现                     | 正常     |
| 一键解压安装       | 需手动安装 Node+Python 前置                               | 有摩擦   |
| 组件功能           | 开发机 P0 全绿（2026-07-30 r6），P1 未配置                | 良好     |
| 测试覆盖           | 65+27+15=107 个测试文件，覆盖所有子系统                   | 良好     |
| 测试通过率         | 后端 237/237、前端 137/137、E2E 21/21（POST-PHASE2 全量） | 通过     |
| 文档同步           | 开发系统 22 份 + 部署系统 7 份，定位不同，无冲突          | 正常     |

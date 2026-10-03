# AI StudyBuddy Windows 部署与运维指南

**版本**：v1.0
**状态**：已触发并生效
**日期**：2026-07-23
**适用范围**：当前 Windows 原生单机部署准备；S7-MVP 若已在主线完成，只允许作为显式配置的本机 `whisper.cpp` 小功能部署（受控 PCM WAV、同步转写、无 Worker/Provider）；本文件不把它写成用户电脑验收，也不包含完整 S7、ASR Worker、实时录音、公网入口、云端数据库或 Docker/WSL 常驻产品依赖。

---

## 一、部署形态

AI StudyBuddy 当前生产形态是 Windows 本机应用：

- 后端 Express 只监听 `127.0.0.1`，不绑定局域网地址，不新增入站防火墙开放规则。
- 前端先构建为静态产物，再由后端生产进程提供静态文件和 SPA fallback。
- API 继续使用 `/api` 前缀；未知 `/api/*` 在生产模式下返回 `{ success:false, error:{ code:"NOT_FOUND" } }` JSON。
- SQLite、学习资料、日志、临时文件、模型缓存、备份和运行时 venv 彼此隔离。
- Docker/WSL 只承担开发隔离、ASR/G2 验证或未来可选实验，不是使用机器常驻依赖。

本轮 v1 部署采用“受控前置运行时”：使用机器需要先具备经过验证的 **Node.js 24 LTS**（脚本仅接受已验证的 Node major 24，`Test-AIStudyBuddySupportedNodeVersion` 强制）和 x64 Python 3.10+；Node 20/22 仅为历史兼容候选，当前脚本按验证基线收紧为仅 Node 24，Node 25 不属于受支持生产运行时。部署脚本在用户目录创建 Python venv 并安装锁定 OCR 依赖。真正无 Node/Python 前置依赖的 MSI/便携版不在本轮范围内。

---

## 二、目录结构

正式使用机器默认安装根：

```text
%LOCALAPPDATA%\AIStudyBuddy\
├─ app\          编译后的后端、前端、共享包和部署脚本
├─ config\       production.env 与非密钥配置状态
├─ data\         SQLite 全局库、学期库和 materials/
├─ logs\         脱敏运行日志
├─ tmp\          可清理临时文件
├─ models\       OCR/未来模型缓存，不进 Git/部署包/普通备份
├─ backups\      预留给后续受控 manifest/hash 备份和恢复点；当前不执行真实用户数据备份/恢复
└─ runtime\venv\ OCR Python 虚拟环境
```

开发机可以使用 `H:\ai-studybuddy-runtime\runs\<task-id>` 或 `H:\ai-studybuddy-tmp\runs\<task-id>` 做隔离验证，但这些 H 盘路径不得写入业务代码或使用机器配置。E2E/Playwright 必须使用可再生 `runs` 目录，不能复用正式 `%LOCALAPPDATA%\AIStudyBuddy\data`。

---

## 三、部署包内容和排除项

部署包应只包含：

- `app/backend`：编译后后端、生产 `package.json`、生产 `package-lock.json`、前端静态 `public/`。
- `app/shared`：编译后共享类型运行资产。
- `app/requirements-ocr.txt`：锁定 OCR Python 依赖。
- `scripts/`：bootstrap、start、stop、check、backup、restore、integrity、OCR smoke、父报告任务注册/注销/wrapper。
- `deployment/`：`.env.production.example`、运行时兼容清单。
- `deployment-manifest.json` 与 `README-Windows.md`。

必须排除：`.git`、`node_modules`、`.env.local`、真实 API Key/SMTP 授权码/完整 Webhook、真实资料、正式 SQLite、WSL venv、pip/npm cache、OCR/ASR 大模型缓存、完整运行日志和 Playwright 证据。

### 构建输出与 staging 边界

`scripts\build-deployment-package.ps1` 只能接收**显式传入、已存在、为空且位于仓库外的受控输出根**。它拒绝仓库根、磁盘根、用户目录、`APP_DATA_ROOT`、与这些受保护根交叠的目录以及符号链接/junction 等重解析点；不得用相对路径或默认输出目录代替。脚本仅在该输出根内创建本次操作专属的 staging 子目录，并且只允许清理由该操作标识的 staging 子目录；不会递归删除输出根，也不会覆盖或删除同名既有 ZIP。

构建前会按路径名和文件系统元数据拒绝 `.git`、`node_modules`/缓存、真实环境文件、正式数据库、日志、`tmp`、模型、备份或运行时目录，并以固定、脱敏的类别报告边界失败；错误不应回显绝对宿主路径、环境值、stack、原始命令输出或文件内容。该边界说明不构成真实打包、真实清理或用户电脑验收记录；这些操作须在单独批准的发布/验收流程中进行。

---

## 四、全新安装流程

在部署包根目录执行：

```powershell
$installRoot = Join-Path $env:LOCALAPPDATA 'AIStudyBuddy'
.\scripts\bootstrap-runtime.ps1 -InstallRoot $installRoot -AppSource .\app -PythonPath 'C:\Path\To\python.exe'
.\scripts\check-installation.ps1 -InstallRoot $installRoot
.\scripts\start-production.ps1 -InstallRoot $installRoot
# 然后在本机浏览器打开 http://127.0.0.1:3000/
```

`bootstrap-runtime.ps1` 会：创建目录、复制部署包、验证 Node/npm、安装生产 Node 依赖、验证 native 依赖导入、创建 Python venv、安装 OCR 依赖、验证 RapidOCR 导入，并生成不含真实密钥的 `config\production.env`。

Node native 依赖（例如 `better-sqlite3`）需要匹配当前 Node 的预编译包；当前已验证组合为 Node v24.14.0 + Python 3.10.19 x64，脚本仅接受 Node major 24（`bootstrap-runtime.ps1` 第 50 行与 `check-installation.ps1` 第 30 行均强制）。Node 25 被脚本明确拒绝：它在本机验收中未取得可用 `better-sqlite3` 预编译包，网络失败后会退回本地编译并要求 Visual Studio C++ Build Tools。bootstrap 已重试 npm 安装；使用机器应安装 Node 24 LTS、保持网络可访问生产依赖源，而不是依赖本地 C++ 编译回退。

---

## 五、生产启停与检查

```powershell
.\scripts\start-production.ps1 -InstallRoot $installRoot
.\scripts\stop-production.ps1 -InstallRoot $installRoot
.\scripts\check-installation.ps1 -InstallRoot $installRoot
```

检查脚本只读，不自动修复、防火墙、删除文件或覆盖数据。它检查 Windows、Node/Python、运行目录、OCR Worker、生产依赖、端口、健康接口、数据库状态、父报告任务、密钥文件误携带、明文密钥和 E2E 目录误用。

---

## 六、配置和密钥

安装包和 Git 不携带真实密钥。首次启动后通过设置中心配置：AI Provider、AI Base URL、AI Model、API Key、SMTP、飞书 Webhook、超时和连接状态。

密钥进入现有 Windows 用户保护存储；`.env.example` 和 `production.env` 只保留非密钥运行字段。日志不得输出 API Key、SMTP 授权码、完整 Webhook、资料原文、笔记正文或完整答案。AI/SMTP/飞书未配置时，离线确定性学习主线必须仍可运行；发送类能力不能伪造成功。

---

## 七、OCR 运行时

生产配置通过 `PYTHON_PATH` 指向安装根 venv：`%LOCALAPPDATA%\AIStudyBuddy\runtime\venv\Scripts\python.exe`。锁定依赖清单位于 `app\requirements-ocr.txt`，其中必须包含 `rapidocr-onnxruntime`，因为 Worker 直接导入 `rapidocr_onnxruntime.RapidOCR`。OCR 模型缓存归运行目录治理，不能提交 Git，不能放入源码目录或部署包。

部署后可执行：

```powershell
.\scripts\test-ocr-runtime.ps1 -PythonPath "$installRoot\runtime\venv\Scripts\python.exe" -RuntimeRoot $installRoot
```

---

## 八、备份、恢复、升级与回滚

### 8.1 手动备份

```powershell
.\scripts\backup-data.ps1 -InstallRoot $installRoot -OutputRoot <external-backup-root>
.\scripts\test-data-integrity.ps1 -BackupPath <backup-path>
```

`backup-data.ps1` 仅白名单 `studybuddy.db` 与 `semesters/` 学习数据；不读取 config、tmp、logs、models、缓存或 Playwright 证据。备份输出必须是显式、既存、同卷且位于安装根之外的受控目录。

### 8.2 自动定期备份（T04-1）

**注册自动备份任务**（每日自动执行）：

```powershell
.\scripts\schedule-auto-backup.ps1 `
  -InstallRoot $installRoot `
  -OutputRoot <external-backup-root> `
  -ScheduleTime "22:00"
```

**注销自动备份任务**：

```powershell
.\scripts\remove-auto-backup.ps1 -InstallRoot $installRoot
```

自动备份任务以当前 Windows 用户身份运行，默认每日 22:00 执行。任务名称为 `AIStudyBuddy-AutoBackup`，可在"任务计划程序"中查看。

### 8.3 数据恢复（T04-3）

**预检（不写入）**：

```powershell
.\scripts\restore-data.ps1 -InstallRoot $installRoot -BackupPath <backup-path> -WhatIf
```

**执行恢复**：

```powershell
# 1. 停止服务
.\scripts\stop-production.ps1 -InstallRoot $installRoot

# 2. 恢复数据
.\scripts\restore-data.ps1 -InstallRoot $installRoot -BackupPath <backup-path>

# 3. 手动重启服务
.\scripts\start-production.ps1 -InstallRoot $installRoot
```

恢复流程会自动创建 recovery point 到 `backups/recovery-points/`，失败时可用于手动回滚。恢复过程会验证每个文件的 SHA256 哈希。

### 8.4 启动时完整性检查（T04-2）

系统启动时自动检查全局库和所有活跃学期库的 `PRAGMA integrity_check`。任何损坏都会拒绝启动并输出明确错误：

```
[DATABASE] STARTUP_INTEGRITY_FAILED scope=global detail=...
[DATABASE] STARTUP_INTEGRITY_FAILED scope=semester semesterId=<id> detail=...
[DATABASE] STARTUP_INTEGRITY_ALL_FAILED count=N
```

启动失败时，检查日志并从最近备份恢复。

---

## 九、Windows 任务计划：家长报告

默认不注册、不发送真实家长报告。配置 SMTP/飞书并单独测试通过后，由当前 Windows 用户明确启用：

```powershell
.\scripts\register-parent-report-task.ps1 -InstallRoot $installRoot
.\scripts\unregister-parent-report-task.ps1 -InstallRoot $installRoot
```

注册脚本只创建当前用户任务；任务命令指向安装根中的 `scripts\run-parent-report-task.ps1` wrapper，再由 wrapper 加载 `production.env`、校验 `127.0.0.1` 和 `APP_DATA_ROOT`，最后调用部署包内已编译的 `parent-report-runner.js`。卸载或注销任务不能删除真实学习数据。

---

## 十、验收矩阵

全新安装至少验证：bootstrap、check、start、前端打开、学期初始化、课程/考试目标、合成资料上传、文本/PDF 转换、OCR、练习、错题、模拟考、冲刺、设置中心、关闭重启后数据仍存在。

OCR 至少验证：中文图片、空白图片、损坏/不存在路径、超时、失败后临时文件清理、模型缓存可复用、不长期留存原始输入。

无 AI/报告配置至少验证：AI Provider 为空时确定性流程可用；AI 不可用显示可理解状态；SMTP/飞书未配置时不发送、不伪造成功、不泄露凭据。

安全网络至少验证：后端仅 `127.0.0.1` 监听；局域网不可直接访问；不新增防火墙开放规则；日志不含密钥和资料原文；Docker/WSL 非必要常驻；S7/G2 复测证据与普通产品部署验收分开记录。

---

## 十一、当前非目标

本轮不包含：完整 S7 课堂录音装配、ASR Worker/长音频/格式转换/实时录音、真实用户音频、公网入口、家长远程登录、云端数据库、Docker 作为正式产品依赖、修改全局 Windows 防火墙策略、无备份/无确认迁移真实学习数据。S7-MVP 的受控本机 CLI 仍须在目标用户机器单独验收，当前不得宣称完成。

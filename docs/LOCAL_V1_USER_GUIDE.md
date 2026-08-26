# StudyBuddy 本地单机 v1：竣工报告、首次使用与验收手册

> 适用版本：StudyBuddy local v1，application version `local-v1`，schema v13。
>
> 支持范围：Windows、本机浏览器、单进程、单实例、SQLite、本地磁盘、一个 `data_root`。
>
> 正式上线证据：[`prompts/phase10/PHASE10_RELEASE_CANDIDATE_EVIDENCE.md`](prompts/phase10/PHASE10_RELEASE_CANDIDATE_EVIDENCE.md)。

## 先说结论：它现在能为学生做什么

StudyBuddy 现在不是一个云端 SaaS，也不是需要安装 Windows 客户端的软件；它是运行在你自己电脑上的本地学习系统。启动后用浏览器打开 `http://127.0.0.1:8787`，资料和学习记录保存在你指定的本地 data root 中。

当前可以实际使用的路径：

1. 导入 TXT、Markdown、PDF、DOCX、PPTX 学习资料；管理、搜索、查看、回收站恢复和导出资料。
2. 对已建立索引的资料提问，并查看回答引用对应的原文位置。
3. 创建卡片、练习、限时练习、错题反馈、冲刺目标、学习计划、资料笔记和学习节奏。
4. 创建课堂采集记录、在已实现范围内处理转写流程、预览和导出本地脱敏学习报告。
5. 创建 backup、验证 backup、恢复到新目录、检查 schema 和运行诊断。

默认安装不需要 API key。没有真实 AI 配置时，资料管理和手工学习功能照常可用；问答会安全提示 Provider 未配置。显式 demo 模式可以使用 deterministic fake provider 演示问答和学习工作流，但不代表真实模型回答。

## 1. 你需要准备什么

### 必需

- Windows 机器；
- 可用的 Python 3.10 环境。当前项目默认优先使用 `C:\miniconda\py310\python.exe`；
- 一个浏览器（当前正式验收路径是 Chromium；日常使用可先用你本机的现代浏览器）；
- 一个仅给 StudyBuddy 使用的本地 data root，例如 `D:\StudyBuddy\data`；
- 一个**不在 data root 内**的 backup 根目录，例如 `D:\StudyBuddy\backups`。

### 不要这样做

- 不要让两个 StudyBuddy 实例共用同一个 data root。
- 不要把 data root 放在 OneDrive/网盘同步目录、网络盘或 Git 仓库内。
- 不要把 backup 放在 data root 内。
- 不要把 API key 写进 Git、聊天记录、截图、命令参数、数据库或提交的 `.env` 文件。
- 不要手工编辑 `studybuddy.sqlite3`、`schema_migrations` 或 `PRAGMA user_version`。

## 2. 第一次正式启动：不配置真实 AI 的基础版

下面命令在 **PowerShell** 中、仓库根目录 `H:\studybuddy` 执行。路径可按你自己的磁盘修改。

```powershell
cd H:\studybuddy

# 为当前 PowerShell 窗口指定你的资料库位置。
$env:STUDYBUDDY_DATA_ROOT = 'D:\StudyBuddy\data'

# 不启用 demo，也不配置真实 Provider：先确认本地资料库工作正常。
$env:STUDYBUDDY_DEMO_MODE = 'false'
Remove-Item Env:STUDYBUDDY_AI_PROVIDER -ErrorAction SilentlyContinue
Remove-Item Env:STUDYBUDDY_AI_MODEL -ErrorAction SilentlyContinue
Remove-Item Env:STUDYBUDDY_AI_BASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:STUDYBUDDY_AI_API_KEY -ErrorAction SilentlyContinue

powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\start-studybuddy.ps1 `
  -DataRoot $env:STUDYBUDDY_DATA_ROOT `
  -Port 8787 `
  -OpenBrowser
```

也可以使用一次性首次启动助手（默认不配置真实 Provider）：

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\first-run-studybuddy.ps1 `
  -DataRoot 'D:\StudyBuddy\data' `
  -Port 8787 `
  -OpenBrowser
```

脚本输出 `studybuddy_first_run_ready` 后，浏览器会打开：

```text
http://127.0.0.1:8787
```

若没有使用 `-OpenBrowser`，请手工打开该地址。检查是否启动成功：

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\health-studybuddy.ps1 -Port 8787
```

预期会得到类似以下安全状态：

```json
{"liveness":"ok","health_status":200,"readiness_status":200}
```

这是你的本地前端。它只监听本机 loopback 地址，不会把系统作为局域网或互联网服务暴露出去。

### 首次停止

不用时应显式停止：

```powershell
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\stop-studybuddy.ps1 `
  -DataRoot 'D:\StudyBuddy\data'
```

预期输出 `studybuddy_stopped`。停止脚本只按这个 data root 的 PID 文件关闭对应进程，不会按端口误杀其他程序。

## 3. 首次正式验收：你必须亲手走一遍的功能

首次启动成功不等于资料库已经准备好。请在一个小的、无敏感内容的测试资料上完成下面清单，再导入自己的正式资料。

### A. 基础资料路径（必须）

1. 在浏览器的“材料”区域导入一个 TXT 或 Markdown 文件。
2. 在材料列表确认它出现；点开详情，确认正文可见。
3. 搜索一个资料中的关键词，确认结果、摘要和详情定位正常。
4. 点击“下载原文件”和“导出解析正文”，确认下载的是正确文件。
5. 删除该测试材料，切换到回收站，恢复它，确认详情和导出仍可用。

**通过标准：** 导入、读取、搜索、导出和删除/恢复都成功；页面不显示文件系统路径、SQL、traceback 或 API key。

### B. 学习路径（建议必须）

如果暂时未配置真实 Provider，可跳过问答生成，但其余手工路径可完成。

1. 在“学习计划”创建一个目标、一个计划和一个计划项；确认计划后激活，并记录一次开始进度。
2. 在“卡片与练习”创建一个卡片组和一个 true/false 练习；确认练习后创建一次限时练习、开始并提交答案。
3. 在“资料笔记”创建一条手工笔记。
4. 在“课堂与报告”创建一个报告快照并导出 JSON 或 Markdown。默认 delivery 是关闭的；导出成功不等于报告已发送给任何人。

**通过标准：** 刷新网页后，上述数据仍存在；练习列表和普通历史不应显示 answer key 或原始提交答案。

### C. AI 问答路径（配置真实或 demo Provider 后必须）

1. 选择一份非空材料，点击“建立当前材料索引”。
2. 在“问答”输入一个能从资料正文直接回答的问题。
3. 确认回答出现，并点击 citation；确认能回到正确材料和正文位置。
4. 刷新页面后，确认问答 history 和 citation 状态仍存在。

**通过标准：** 回答有服务端验证的 citation；没有 citation、资料未索引或 Provider 不可用时，应是安全错误或空状态，不应伪造答案。

### D. 备份与恢复演练（正式资料导入前必须）

选择一个从未使用过的 restore 目录。例如：

```powershell
$python = 'C:\miniconda\py310\python.exe'
$data = 'D:\StudyBuddy\data'
$backup = 'D:\StudyBuddy\backups\first-verified-backup'
$restore = 'D:\StudyBuddy\restore-check'

# 先停止运行中的服务，再做 operator 操作。
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\stop-studybuddy.ps1 -DataRoot $data

& $python -m backend.app backup --data-root $data --output $backup
& $python -m backend.app verify-backup --backup $backup
& $python -m backend.app restore --data-root $restore --backup $backup --confirm
& $python -m backend.app verify-restored-data --data-root $restore
```

**通过标准：** backup 与 verify 都成功；restore 只写入不存在或空目录；`verify-restored-data` 成功。恢复不会覆盖原 data root、不会自动运行 task、不会自动调用 AI/OCR/ASR/发送报告。

完成后可用 restore data root 启动一次，检查材料和导出；确认无误后可删除这次 restore-check 目录。不要用 restore 命令覆盖你正在使用的资料库。

## 4. 使用真实 AI 问答

### 已有精确真实 smoke evidence 的 Q&A 配置

目前真正做过受控真实网络验证的 Q&A 组合包括：

- DeepSeek：provider `deepseek`，model `deepseek-chat`，base URL `https://api.deepseek.com/v1`；
- Agnes AI-Hub：provider `agnes-ai-hub`，model `agnes-2.5-flash`，但该组合的 gateway/account 配置必须使用你自己的 provider 文档和凭据。

这不表示所有模型、供应商、额度、延迟或回答质量都已验证；只表示对应的精确组合已经过项目的 API/UI smoke。

### DeepSeek 正式首次配置示例

先在 PowerShell 中启动一个新的本地会话。**不要同时设 `STUDYBUDDY_DEMO_MODE=true` 和真实 Provider 配置。**

```powershell
cd H:\studybuddy

$env:STUDYBUDDY_DATA_ROOT = 'D:\StudyBuddy\data'
$env:STUDYBUDDY_DEMO_MODE = 'false'
$env:STUDYBUDDY_AI_PROVIDER = 'deepseek'
$env:STUDYBUDDY_AI_MODEL = 'deepseek-chat'
$env:STUDYBUDDY_AI_BASE_URL = 'https://api.deepseek.com/v1'
$env:STUDYBUDDY_AI_API_KEY = '<仅在本机粘贴你的真实 key>'

powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\start-studybuddy.ps1 `
  -DataRoot $env:STUDYBUDDY_DATA_ROOT `
  -Port 8787 `
  -OpenBrowser
```

之后重复上节的 **C. AI 问答路径**。第一次只用一份不敏感、较短的测试资料，确认：索引成功、提问成功、citation 可定位、页面不泄露 key。通过后再导入日常资料。

### 关于 embedding

系统支持显式 embedding indexing task；当前有 Mistral `mistral-embed` 的精确真实 evidence。它不是启动时自动运行的后台服务。没有配置 embedding 时，基础词法检索和 Q&A 仍可用；不要为“先跑起来”而急着配置 embedding。

### API key 保存建议

当前程序从**进程环境变量**读取 key；它不会自动读取 `.env` 文件。因此最简单安全的方式是：每次启动前在当前 PowerShell 会话设置 `$env:STUDYBUDDY_AI_API_KEY`。如需长期保存，请使用 Windows 的安全凭据/秘密管理方式，或由你自己的未跟踪启动脚本读取；不要把 key 写入本仓库。

## 5. 日常使用建议

### 每天

1. 启动 StudyBuddy，运行 health 检查，打开浏览器前端。
2. 导入当天材料；对重要材料先确认解析正文和搜索结果正常。
3. 对要问答的材料显式建立索引，再提问并核对 citation。
4. 卡片、练习、计划和笔记的“确认”是用户决定，不要把 AI draft 当作已核实事实。
5. 下班/学习结束后停止服务。

### 每周或重要资料导入后

1. 停止服务。
2. 创建一个新 backup 目录。
3. 执行 `backup` 和 `verify-backup`。
4. 至少定期恢复到一个新空目录并运行 `verify-restored-data`。

### 需要诊断时

```powershell
C:\miniconda\py310\python.exe -m backend.app diagnostics --data-root 'D:\StudyBuddy\data'
```

如果 health/readiness 不是 200、diagnostics 显示 degraded，或 backup/verify 失败：**先停止服务、保留 data root 和已验证 backup，不要手改数据库，不要尝试覆盖恢复。** 参考 [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md) 和 [`MIGRATIONS.md`](MIGRATIONS.md)。

## 6. 当前不该期待它做什么

这些限制是真实限制，不是使用错误：

- 不支持多用户、登录、权限、协作、云同步；
- 不支持多实例、多 worker 或共享 data root；
- 未验证真实断电、磁盘满、ACL、网络盘、文件系统损坏恢复；
- 真实 OCR/ASR 尚未正式接入；课堂转写的已验收路径是 deterministic fake/loopback；
- 报告可以本地预览和导出，但 live SMTP/飞书发送被固定阻止；
- 不是通用 Windows 安装包或后台 Windows 服务；按本手册用 PowerShell 启动和停止；
- 没有宣称无界长期负载、所有真实 Provider 或系统级无障碍验证。

## 7. 让它真正成为“学生学习好伴侣”的最小下一阶段

不建议现在继续堆基础设施。最小、最有实际价值的产品扩展应按这个顺序推进：

### P0-1：真实 AI 配置与首次使用向导

目标：让学生不需要了解环境变量也能安全配置一个已验证 Provider。

- 前端增加“Provider 设置”页：显示未配置 / 已配置但未验证 / 已验证的精确配置状态；
- key 只写入 Windows 凭据或运行时环境，不进数据库、日志、URL 或普通浏览器 storage；
- 提供“测试连接”与一份 synthetic material 的最小 Q&A smoke；
- 固定先支持 DeepSeek `deepseek-chat`，失败显示稳定、可理解的中文错误；
- 导出可分享的脱敏配置诊断，而不是导出 secret。

**验收：** 一个新用户可在 10 分钟内完成真实 Q&A，且能看到 citation；错误、超时、额度不足和未配置 key 都安全可理解。

### P0-2：一个真实 ASR Provider，而不是同时接十个

目标：让课堂录音成为可复核的转写草稿。

- 先选择并单独立项一个 Provider（例如 OpenAI-compatible Whisper API 或你明确拥有凭据的其他 ASR）；
- 上传的原始音频仍保留本地 hash-derived storage；raw provider response 不持久化；
- 转写结果始终为 draft，保留 confidence/uncertain，必须用户编辑/确认后才进入资料与检索链；
- 采用现有 operation/task、超时、取消、retry、source lifecycle 和 backup/restore 边界；
- 不把“远端 Provider 已收到音频”伪装成可撤销；在 UI 中明确隐私和网络提示。

**验收：** 一段真实、非敏感测试录音可上传、转写、编辑、确认，并进入 citation-safe Q&A；Provider 失败不会损坏原音频、材料或用户编辑。

### P0-3：一个真实报告交付渠道

目标：让用户可把自己确认的脱敏报告发给一个明确对象。

- 先二选一：SMTP **或** 飞书，不同时做；
- 收件人/目标必须 allowlist，发送前显示报告预览、目标标签和显式确认；
- delivery 保持默认 off；真实发送必须有运行配置、授权和确认三层开关；
- append-only 发送审计、幂等键、失败 retry 和“已提交给渠道但未知最终送达”状态；
- 测试收件箱/测试机器人先验收，绝不把真实家长/老师作为第一条测试消息。

**验收：** 一份脱敏报告能被明确确认后只发送一次；重复点击不重复发送；失败不泄露收件人、secret 或报告正文。

完成 P0-1、P0-2、P0-3 后，StudyBuddy 才会从“可靠的本地学习系统底座”跨到“真正可日常使用的 AI 学习伙伴”。

## 8. 竣工状态的准确说法

可以说：

> StudyBuddy 已在明确的 local single-process / single-instance / SQLite / local-disk v1 支持范围内完成生产化和上线收口；可以作为个人本机资料与学习工作流系统运行、备份、恢复和诊断。

不应说：

> StudyBuddy 已支持所有真实 AI、真实转写、真实外发、多用户云协作，或已经是全场景 production-ready 系统。

# X 横切能力：材料问答 / 朗读 / 备份恢复

> 状态以 [capabilities.json](../capabilities.json) 中 id=X-QA、X-TTS、X-BACKUP 为准；本文不写测试通过数。

三项能力不属于主闭环的某一跳，但服务所有子系统。设计细节见 [TTS_DESIGN](../03-ARCHITECTURE.md#6-横切能力) 与 [BACKUP_RESTORE](../06-OPERATIONS.md#2-备份校验恢复)。

## X-QA 材料问答

### 1. 目标
学生读资料时遇到不懂的地方，可以就选定材料提问，得到带引用的回答，回答能追溯到原文片段。它帮助学生读懂资料、更快确认知识模块，但不是通用对话，也不替学生做决定。

### 2. 用户流程
1. 在 `qa.html` 选择一个或多个材料，输入问题。
2. 系统检索相关片段并生成回答，回答中的引用可点击查看原文片段。
3. 同一线程可继续追问；历史线程可再次打开。
4. 其他页面右下角的问答浮窗（`js/chat-widget.js`，由 `shell.js` 挂载）提供同样的快捷提问。

### 3. 数据对象
| 表 | 关键字段 | 状态 |
|---|---|---|
| `qa_threads` | title, archived_at | 线程 |
| `qa_messages` | thread_id, role `system / user / assistant / tool`, content, ai_operation_id | 只追加 |
| `qa_answers` | message_id, answer_text, source_coverage, prompt_version, provider_id, model_id | `draft / ready / rejected / stale` |
| `qa_citations` | 回答引用的片段 | 随回答 |
| `retrieval_runs` `retrieval_hits` | 检索记录 | 只追加 |

### 4. 页面与 API
页面：`qa.html`；全局问答浮窗。

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/qa/ask` | 提问（question、material_ids、thread_id、top_k、retrieval_mode、allow_retrieval_fallback） |
| GET | `/api/qa/threads`、`/api/qa/threads/{thread_id}` | 线程列表 / 详情 |
| GET | `/api/qa/citations/{citation_key}` | 引用原文片段 |
| POST | `/api/retrieval`、`/api/context/assemble`、`/api/citation/validate` | 检索、上下文装配、引用校验 |

### 5. 规则与 AI 边界
- 检索和引用校验由规则完成；只有回答文本由 LLM 生成，且只能基于所选材料的检索片段。
- 检索为空时返回 `retrieval_empty`，不凭空回答；Provider 未配置时返回明确错误。
- 回答不写入知识模块、错题或计划，也不调用 S1–S7 的任何操作。
- 聊天内容不进入家长报告。

### 6. 验收标准
- 对选定材料提问，回答带可点击引用，引用能打开对应原文片段。
- 材料中找不到相关内容时提示检索为空。
- Provider 未配置时页面提示未配置，不报未知错误。

### 7. 已知缺口
- 不是通用对话，不调用 S1–S7 工具。

## X-TTS 朗读

### 1. 目标
让学生可以"听"知识模块的标题和描述，用于通勤或闭眼复习。朗读是辅助，不改变任何学习事实。

### 2. 用户流程
1. 在 `material-detail.html` 的知识模块工作区选择一个有效模块。
2. 在"朗读"卡片点"朗读选中模块"，可播放/暂停、停止、重试。
3. 页面显示当前引擎；失败时显示固定文案和"重试"。

### 3. 数据对象
无数据库表。播放会话在进程内管理：`playback_id`、`state`（`playing ⇄ paused → stopped`）、`engine`、`fallback_used`、WAV 产物。

### 4. 页面与 API
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/tts/capabilities` | 引擎与配置状态 |
| POST | `/api/tts/speak` | 合成（text ≤ 12000、engine `fake / sapi / edge-tts`、voice、rate 0.5–2.0） |
| POST | `/api/tts/control` | `play / pause / stop`，可调 rate |
| GET | `/api/tts/status/{playback_id}` | 播放状态 |
| GET | `/api/tts/audio/{playback_id}` | WAV 音频 |

### 5. 规则与 AI 边界
- 默认关闭（`STUDYBUDDY_TTS_ENABLED=0`），引擎需显式配置；edge-tts 失败时只有在 SAPI 已配置且允许 fallback 时才降级。
- 只朗读页面已展示的模块标题和描述，不绕过材料 API 读取原文。
- 错误只映射为稳定错误码（如 `tts_not_configured`、`tts_timeout`），不暴露命令路径或原始输出。

### 6. 验收标准
- 未配置时按钮旁显示未配置，点击后提示而不报错。
- 配置后选中模块可朗读、暂停、继续、停止；失败可重试。

### 7. 已知缺口
- 只接入 S2 知识模块。
- 真实 SAPI/edge-tts 与设备播放未验证。

## X-BACKUP 备份恢复

### 1. 目标
学生的学习数据只在本机，必须能在本机完成备份、校验和恢复，保证长期使用不怕丢失。这是维护者操作，不是学生日常功能。

### 2. 用户流程（维护者，命令行）
1. 停止服务后执行 `python -m app.cli backup --data-root <data-root> --output <backup-root>`。
2. 执行 `verify-backup --backup <backup-root>` 校验。
3. 恢复到不存在或为空的目录：`restore --data-root <new-root> --backup <backup-root> --confirm`。
4. 执行 `verify-restored-data --data-root <new-root>` 做恢复验收。
5. 可选：`rotate-backups`（默认 dry-run，`--confirm` 才删除）、`upgrade-preflight`、`schema-version`。

### 3. 数据对象
备份目录：`manifest.json`、`database.sqlite3`（SQLite Online Backup 快照）、`originals/<sha256[:2]>/<sha256[2:]>/original`。manifest 记录 schema 版本和文件哈希，不记录路径、正文或密钥。

### 4. 页面与 API
没有 HTTP 路由，也没有页面；只通过 `backend/app/cli.py` 子命令：`backup`、`verify-backup`、`restore`、`verify-restored-data`、`rotate-backups`、`upgrade-preflight`、`schema-version`。

### 5. 规则与 AI 边界
- 全部规则；不用 AI。
- 应用启动不会自动备份、恢复或修复。
- 校验不修复、不跑迁移、不改备份；恢复只允许空目标且必须 `--confirm`，验收失败不生效。
- 不修复损坏数据。

### 6. 验收标准
- 备份后 `verify-backup` 通过；篡改任一文件后校验失败。
- 恢复到空目录并通过 `verify-restored-data` 后，用新数据根启动，Today、材料、错题与备份前一致。
- 向非空目录恢复或缺少 `--confirm` 时拒绝执行。

### 7. 已知缺口
- 真实 Windows 数据根恢复未验证。
- 无页面入口，学生无法自助备份。

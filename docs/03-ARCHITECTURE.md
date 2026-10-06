# 03 · 架构

> 讲清"系统怎么搭、边界在哪"。能力完成度见 [`capabilities.json`](capabilities.json)。

## 1. 运行形态

本机单进程 Web 应用：FastAPI 后端 + 原生 HTML/CSS/JS 前端 + SQLite + 本地文件。只监听 `127.0.0.1:8787`，首页 `/app/buddy.html`。

- 单进程、单实例、单 `data_root`；`data_root/.studybuddy-instance.lock` 防止重复启动。
- 不支持：多 worker、多实例共享 `data_root`、云同步、多用户、认证授权、真实断电恢复。
- 不引入：React/Vite、pi、Electron、自动 Provider fallback。

## 2. 代码布局

```text
backend/app/
  main.py                 兼容 façade（create_app / app）
  app_factory.py          应用工厂；lifespan.py 启动顺序
  api/                    按业务域的 HTTP 路由，registration.py 统一注册
  repository.py           兼容 façade → repositories/ 各域持久化
  migrations/runner.py    唯一迁移入口；_vNN_*.py 为各版本实现
  storage.py              hash 派生原文件路径、原子写、containment 校验
  adapters/file_parsers/  TXT/MD/PDF/DOCX/PPTX 解析
  providers/              fake、OpenAI-compatible、embedding、registry
  tts.py                  朗读 Provider、缓存、播放会话
  backup.py / cli.py      备份、校验、恢复、诊断（仅 CLI）
  static/                 页面与 js/
```

规则：新代码走公共 façade；新增/重写的 `.py .js .css .html .ps1 .json` 文件不超过 32 KiB（`backend/scripts/check-source-size.py`）。

## 3. 数据与事实层级

```text
materials / extractions / text_spans        来源事实（source of truth）
  → revision → chunks → FTS/embedding      派生，可重建
  → retrieval → citations                  可回链到 span
  → knowledge_modules(+s2_knowledge_modules) 草稿 → 学生确认
  → exercises → practice_sessions/attempts → mistake_cases → weak points
study_plans / rhythm_allocations / cram_goals 学生目标
study_reports / delivery_attempts           只读聚合 + 外发审计
```

- 派生数据和 AI 产物不能静默覆盖来源事实或已确认编辑。
- 来源删除后保留模块身份和练习事实，但隐藏摘录并阻止新的生成。
- Today 是只读投影：在一个数据库快照里读上面各表，不写任何事实。

## 4. 启动与持久化不变量

启动顺序：preflight → SQLite 连接与迁移 → 诊断审计 → recovery → ready。只有全部完成，`/api/readiness` 才返回 ready。

- SQLite：WAL、外键、2000 ms busy timeout、显式事务。
- 迁移：连续、幂等、`BEGIN IMMEDIATE` 内原子提交；失败回滚，服务不会带半升级 schema 进入 ready。当前版本以 `runner.py` 中的注册表为准。
- 存储：原文件按 SHA-256 存放，校验 containment、regular-file、non-symlink。
- 错误：API、日志和 UI 不泄露路径、SQL、原文、密钥、Provider 原始响应或 traceback；使用稳定错误码。

## 5. AI 边界

依赖顺序固定：`revision → chunks → retrieval → citations → Q&A → 模块/卡片/练习`。

- 默认 Provider 是 deterministic fake；真实 Provider（OpenAI-compatible）显式配置、默认关闭、无自动 fallback。
- 生成内容先存为带引用的草稿；服务端重验 citation 后原子保存；确认前不进入练习或计划。
- 规则负责：客观题批改、日期、优先级、去重、统计、掌握度投影。简答题进入 `pending_review`，不产生正确性事实。
- 启动、备份、恢复不会触发生成、修复或重建。

## 6. 横切能力

- **朗读（TTS）**：`tts.py` 管理 Provider、缓存 `<data_root>/tts-cache/<sha256>.wav` 和短生命周期播放会话；浏览器负责实际播放。不建表、不写学习事实。Provider：`fake`（测试/演示）、SAPI、edge-tts（联网），均需显式开启。
- **材料问答**：`/api/qa/ask` 在选定材料范围内检索并带引用回答；不是通用对话。
- **外发**：报告外发默认 `off`；`dry_run` 只写审计；`live` 需逐次授权。

## 7. 组件进入正式系统的路径

```text
外部组件 → H:\studybuddy-composer 独立 smoke → H:\studybuddy-integration 组合验证
        → H:\studybuddy 按契约重新实现 Adapter → 正式测试 → 用户路径验收
```

不复制 Composer/Integration 源码进正式系统。任何一层通过都不能替代下一层。

## 8. 目录

| 目录 | 用途 |
|---|---|
| `H:\studybuddy` | 源码、正式测试、文档 |
| `H:\studybuddy-data` | 正式 data_root（根目录本身；`live/` 已废弃） |
| `H:\studybuddy-test` | 隔离 data_root、测试产物、验证证据 |
| `H:\studybuddy-composer` / `-integration` | 组件试炼场 / 组合验证 |
| `H:\studybuddy-ChinaTextbook` | 真实教材，只读；token 文件是密钥，永不读取或清理 |
| `H:\studybuddy-log` / `-tmp` | 日志 / 临时文件 |

清理规则见 [`06-OPERATIONS.md`](06-OPERATIONS.md) §5。

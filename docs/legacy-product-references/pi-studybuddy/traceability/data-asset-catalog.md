# T-M5-009 `data-asset-catalog`

**状态**：首版基线，`done`
**盘点日期**：2026-08-14
**任务**：T-M5-009
**权威来源**：docs/05、docs/08 §9、docs/13 §5、当前 `src/host`/`src/main`/`tests/helpers` 实现。
**默认业务根**：`%LOCALAPPDATA%\PiStudyBuddy`
**测试根**：`H:\pi-studybuddy-tmp\runs\<task-id>\`；测试运行数据不得连接、复制、覆盖或查询生产根。

## 1. 数据资产目录

| DATA-ID | 资产 | 介质/落点 | owner/来源 | 生命周期与真相 | 隐私/日志 | 备份/恢复 | 测试策略 | 当前状态 |
|---|---|---|---|---|---|---|---|---|
| DATA-BIZ-001 | 学期 | SQLite `<dataRoot>/global.db` 或正式 schema 关联 | S1 | 持久化业务事实；状态迁移后可回读 | 学习资料敏感；不进 DOM/日志 | 由归档/备份策略覆盖；恢复后回读 | 专用 global.db + 真机 UI | 已证实 |
| DATA-BIZ-002 | 课程 | `<dataRoot>/global.db` / 学期库关系 | S1 | 依赖学期；不可脱离 FK | 敏感 | 与学期一起备份/恢复 | 专用 SQLite + FK/CHECK | 已证实 |
| DATA-BIZ-003 | 任务/完成状态 | 学期 SQLite `sem.db` | S1 | 状态迁移；重启需回读 | 学习进度敏感 | 待发布 runbook 明确 | 真机 UAT + 真实 schema | 部分证据 |
| DATA-BIZ-004 | 考试/确认状态 | 学期 SQLite `sem.db` | S1/S5 | 确认是 S5 门控事实 | 敏感 | 待发布 runbook 明确 | 真机 UI + 重启回读 | 部分证据 |
| DATA-BIZ-005 | 资料元数据 | 学期 SQLite `sem.db` | S2 | 与正式文件/转换状态关联 | 资料标题/原文敏感 | 备份包含元数据 | 专用 SQLite + 文件 E2E | 部分证据 |
| DATA-BIZ-006 | 笔记/模块 | 学期 SQLite `sem.db` | S2 | 笔记和学习状态；正式事实 | 学习内容敏感；不输出原文到日志 | 需与资料绑定恢复 | 专用 SQLite + UI 回读 | 部分证据 |
| DATA-BIZ-007 | 练习 session/作答 | 学期 SQLite `sem.db` | S3 | 作答事实不可被 AI 改写 | 答案/解析敏感 | 备份后可重建结果 | 专用 SQLite + UAT | 已证实 |
| DATA-BIZ-008 | 练习结果 | 学期 SQLite `sem.db` | S3 | 提交后持久化；重启读取 | 敏感 | 同学期数据恢复 | UAT 第二次重启回读 | 已证实 |
| DATA-BIZ-009 | 错题/复盘事实 | 学期 SQLite `sem.db` | S4 | 来源于作答；错因建议非事实 | 敏感；AI 建议需标不确定 | 与作答事实一起恢复 | 真实 UI + 脱敏 DOM | 部分证据 |
| DATA-BIZ-010 | 错题学习状态 | 学期 SQLite `sem.db` | S4 | 可回退/重做；需审计 | 敏感 | 同学期恢复 | 定向 handler + UAT | 部分证据 |
| DATA-BIZ-011 | 模拟考/题目 | 学期 SQLite `sem.db` | S5 | 生成、作答、提交、结果 | 敏感 | 与考试/模块恢复 | 空课程与正常课程测试 | 已证实 |
| DATA-BIZ-012 | 模拟考模块分析 | 学期 SQLite `sem.db` | S5 | 依赖已有模块；未知模块不得写假引用 | 敏感 | 结果恢复 | GEN-05 + UAT | 已证实 |
| DATA-CFG-001 | 模型配置 | `<dataRoot>/config/models.json` | 设置/模型运行时 | 用户配置；由 modelsConfig 管理 | 不含密钥；不进 Git/DOM | 备份策略待明确 | 业务根隔离 + contract | 部分证据 |
| DATA-CFG-002 | 凭证 | `<dataRoot>/config/credentials.json` + Windows DPAPI | credential-vault | 安全资产；不可明文导出 | 永不记录 key/base URL | 卸载/备份保留策略待明确 | 只用受控本机 vault | 部分证据 |
| DATA-CFG-003 | 用户偏好/设置 | `<dataRoot>/config/` | Settings | 保存反馈已见；实际修改值重启回读未完成 | 脱敏 | 升级兼容性待明确 | 隔离根 + UI | 部分证据 |
| DATA-FILE-001 | 资料正式文件 | semester 下受限 `storageKey` | S2/file handler | 与资料元数据绑定；路径白名单 | 原文敏感；日志只记 opaque key | 备份/恢复需校验 | 文件选择 UI + isolated root | 部分证据 |
| DATA-FILE-002 | 导入 capability 暂存 | `<dataRoot>/imports/materials/<token>` | main/preload/host | 一次性消费；失败清理 | token 不进 DOM/日志 | 不应作为备份事实 | 受控文件 E2E | 部分证据 |
| DATA-FILE-003 | 导出/备份包 | `<dataRoot>/exports/` 或用户选择目录 | backup | 可导出、校验、恢复；失败不得覆盖原数据 | 包内容敏感 | 本轮真实恢复/回读未覆盖 | 备份/恢复专项 UAT | 未覆盖 |
| DATA-MEM-001 | L1 learner profile | `<dataRoot>/memory/l1/learner-profile.json` | memory layer | 来源可追踪；可备份 | 高敏感；不进日志 | 备份/恢复策略待明确 | 隔离根 + schema test | 未覆盖 |
| DATA-MEM-002 | L2 wiki index | `<dataRoot>/memory/l2/wiki-index` | memory layer | 可重建索引；不是唯一事实 | 资料敏感 | 允许重建 | 单件/集成 | 未覆盖 |
| DATA-MEM-003 | L3 conversation | `<dataRoot>/memory/l3/conversation.sqlite` | chat/agent | 会话事实；需与 session 关联 | 消息敏感；模型输出不进普通日志 | 备份/恢复待明确 | 专用根 + session E2E | 部分证据 |
| DATA-TEST-001 | 测试 global/semester SQLite | `H:\pi-studybuddy-tmp\runs\<task-id>\...` | tests/helpers | 非生产；任务结束后按证据保留/清理 | 不含真实学生数据 | 不进入正式备份 | 正式 schema/handler 建库 | 已登记 |
| DATA-TEST-002 | 测试截图/DOM/JSON/日志 | 同一任务运行根 | E2E/UAT | 证据资产；不作为业务事实 | DOM 不含完整 UUID/路径/栈 | 不进 Git | 结构化结果文件 | 已登记 |
| DATA-TMP-001 | 转换/缓存/临时连接 | imports、cache、内存 | 运行时 | 可清理；不得当唯一事实 | 最小化 | 不备份 | 清理/句柄测试 | 部分证据 |

## 2. SQLite 与文件副作用纪律

1. 单机、单用户、单写进程；`global.db` 与 `semester/<id>/sem.db` 的 owner 和连接边界必须可定位。
2. 建库辅助返回前关闭 SQLite 连接；Windows WAL/SHM 句柄不得阻塞真实 Electron 随后打开。
3. 文件—数据库双写必须登记顺序、失败补偿和孤儿文件处理；不能只写 happy path。
4. 生产根与测试根物理隔离；`test.*` 不得在运行中的应用中 seed 业务实体。
5. 新增持久化事实前，先更新 docs/05、此目录、error-catalog 和备份影响。

## 3. 仍待核验

- `storage/` 根级目录与 semester 正式资料落点的最终职责不能靠目录存在推断。
- DPAPI 凭证的升级、卸载、备份保留策略需由 T-M5-005/008 的发布证据补齐。
- DATA-FILE-003、DATA-MEM-* 的真实恢复回读尚未形成真机 UAT 证据。

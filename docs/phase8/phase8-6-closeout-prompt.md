# Phase 8.6：Backup / Restore、完整回归与文档收口 Prompt

## 目标
证明 Phase 8 不是只有代码，而是 migration、数据、API、UI、备份恢复和治理状态一致的正式阶段。

## 任务
1. 扩展 backup/verify/restore tests：draft、ready、rejected/stale、archived card/exercise、citations、reviews、attempts、operations 全部保留。
2. 验证 restore 到新空 data root；verify/restore 不自动生成、不 repair、不 rebuild、不把 stale 变 ready。
3. 运行 focused backend tests、Phase 8 Chromium tests、完整 backend suite；按项目 Python 环境执行：`D:\miniconda\py310\python.exe -m pytest backend/tests/`。
4. 运行 migration rollback、lifecycle invariant、API boundary、provider failure 和 frontend failure contract 回归。
5. 检查日志/API/UI 不泄露路径、SQL、traceback、raw provider response、secret、完整 source text 或 answer key。
6. 更新 `docs/STATUS.md`、`docs/TODO.md`、`docs/PHASE_ROADMAP.md`、`docs/PROJECT_PROGRESS_REPORT.md`，必要时更新 `docs/ARCHITECTURE.md`、`docs/DECISIONS.md`、`docs/INDEX.md`。
7. 生成脱敏、可复现的 acceptance evidence；不要把数据库、原文件、运行输出或 secret 写入仓库。
8. 只有所有完成门槛满足时，才删除 `docs/phase8/` 中的 prompt；否则保留并诚实记录 partial/not_verified。

## 最终报告
列出 migration version、API/state machine、citation/source lifecycle、grading/review/attempt、测试命令和结果、browser/restore evidence、real-pass 精确范围、限制和 Phase 9A 前置建议。

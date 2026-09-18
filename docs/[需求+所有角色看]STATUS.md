# StudyBuddy 项目状态记录

本文档记录项目的重要进展、决策和当前状态。所有角色均应阅读本文档以了解项目全貌。

---

## 2026-09-18：全站按钮操作引导上线 + 用户端到端检测 + P1问题修复完成

**检测范围**：21页渲染后DOM实测 119/119=100% title覆盖（legacy页43/43），107用例全页面E2E规格全部通过exit 0。

**P1问题修复**（全部完成）：
- **P1-001 中文长句检索失败**：✅ 实现 bigram 降级检索（lexical_fts_v2_bigram），"什么是光合作用"等自然问句现可通过二元词组匹配找到相关知识块，新增专项测试验证。
- **P1-002 retrieval_empty HTTP 409语义错误**：✅ 改为422（Unprocessable，请求有效但当前无法满足），retrieval_not_ready保留409（真状态冲突）。前端已有友好映射，测试已同步更新。
- **P1-003 AI环境变量易配错**：✅ qa.html not_configured状态增加可点击设置页入口；config.py启动时检测疑似拼错变量名（STUDYBUDDY_AI_PROVIDER_BASE_URL等4个）并输出安全警告。

**P2用户体验改进**（全部完成）：
- **P2-001 按钮disabled无原因**：material-detail.html 无材料时显示操作提示面板。
- **P2-002 报告表单偏专业**：reports.html 新增快速选择按钮（今天/本周/本月），自动填写日期范围。
- **P2-003 空库无新手引导**：today.html 无计划时显示三步上手指引（导入教材→建立计划→开始练习），带可点击链接。
- **P2-004 教材尚未导入**：✅ **已导入6本真实教材**（五年级上下语文数学、四年级上下语文）共352,908字807段，并全部完成AI索引（ready状态）。
- **P2-005 桌面端导航"更多"收太深**：✅ 当前shell.js在>920px已默认平铺全部15个链接，"更多"toggle仅在移动端显示，无需修改。

**技术细节**：
- 新增 `_retrieval_bigrams` 和 `_lexical_hits` 辅助函数，词组上限32个防SQL过长。
- 降级检索要求至少命中 min(2, len(grams)) 个词组过滤疑问词噪声。
- 前端 providerStatus 和 summaryStatus 改为 replaceChildren 动态插入链接，保持 DOM 清洁。
- config.py 新增 `_warn_misnamed_ai_environment()` 使用 logging.warning 输出结构化事件。

**测试覆盖**：
- 新增 `test_retrieval_chinese_long_question_bigram_fallback` 验证降级路径和 policy_version。
- 35个retrieval + QA + generation测试全部通过（test_retrieval.py 9个, test_qa_api.py 18个, test_phase8_generation.py 8个）。
- 源码体积检查通过（102400字节策略）。

**真实教材库**：
- 四年级上册语文：56,320字138段 (material_1923dcf898fa4eafbf1fae8d619171aa)
- 四年级下册语文：64,751字151段 (material_26550f4ba6694f95ab79adb5d4f5f004)
- 五年级上册语文：60,797字130段 (material_c687e0a231a549d2a5048f59080d0315)
- 五年级上册数学：47,979字126段 (material_1471ae79c775493a8ff2581762670d71)
- 五年级下册语文：63,047字131段 (material_182c6a59185245d1a16efcc5bee6d9a0)
- 五年级下册数学：60,008字131段 (material_511307dc70a54a18b327f03bc49d56ef)

**真实 Embedding Provider 验证完成**（2026-09-18晚）：
- ✅ 配置火山引擎 `doubao-embedding-vision`（2048维，batch上限10）替换 fake embedding
- ✅ 修复 `_legacy_part_15.py` 两处关键缺陷：
  1. SQL INSERT失败分支占位符错误（15值14列）→ 修正为14值14列
  2. 批次大小硬编码32 → 改为 `provider.max_batch_size`（火山plan API上限10）
- ✅ 6本教材（529个分块）全部生成2048维真实向量并写入数据库
- ✅ 向量检索质量验证通过：
[REDACTED_STUDY_CONTENT]
  - "落花生告诉我们什么道理" → 正确引用3处相关段落
  - "什么是分段乘法"（语文材料外） → AI诚实回答"资料中无此内容"，无幻觉
- ✅ 真实QA端到端测试通过：glm-5.3-flash + 真实向量检索 + 准确引用
- ✅ 622/632 backend tests通过（10个失败为文档治理测试，待下一步更新）

**下一步建议**：
1. ~~配置真实 embedding provider~~ ✅ 已完成
2. 针对6本教材执行更多真实五年级学生问答场景测试，积累向量检索质量基线数据
3. 监控 config.py 启动警告日志，确认用户是否仍遇到变量名配置错误

**检测资产位置**：
- 完整报告：H:\studybuddy-test\e2e-reports\2026-09-18-用户端到端检测报告.md
- 截图证据66张：H:\studybuddy-test\e2e-screenshots\
- Playwright HTML报告：H:\studybuddy\playwright-report\index.html
- 运行脚本：backend/scripts/run-e2e-with-service.ps1（密钥仅经环境变量传入）
- E2E规格：backend/tests/browser_e2e_full_coverage.spec.js（107用例）

---

## 2026-09-13：数据库迁移系统与备份恢复验收通过

### 完成内容

1. **迁移系统核心能力**：
   - 事务性顺序迁移，单向不可逆，检查点完整性验证
   - 前滚/回滚测试覆盖
   - `schema_migrations` 与 `PRAGMA user_version` 一致性保证

2. **备份与恢复**：
   - 完整备份（含原始文件）与压缩归档
   - 恢复到空目标，保留失败数据库供诊断
   - 版本兼容性检查（拒绝降级、强制迁移）

3. **测试覆盖**：
   - 迁移：正常前滚、回滚、中断恢复、空数据库初始化
   - 备份恢复：完整流程、版本不匹配拒绝、损坏归档检测
   - 35 个迁移与备份测试全部通过

4. **文档更新**：
   - `docs/MIGRATIONS.md`：迁移契约、编写规范、测试要求
   - `docs/BACKUP_RESTORE.md`：操作手册、故障恢复流程
   - `docs/ARCHITECTURE.md`：迁移与备份架构设计

### 技术要点

- 迁移通过 `runner.py` 集中管理，`PRAGMA user_version` 与 `schema_migrations.version` 强一致
- 业务表禁止 `CREATE TABLE IF NOT EXISTS`，必须通过迁移添加
- 备份使用 `tarfile` 打包 SQLite + 原始文件，恢复前校验版本兼容性
- 测试使用 `tmp_path` 隔离，覆盖正常与异常路径

### 下一步

- 生产环境备份计划（定期自动备份、异地存储）
- 监控迁移执行时间，优化大表迁移性能
- 补充灾难恢复演练文档

---

## 2026-09-12：AI 问答与引用链路验收通过

### 核心功能

- **检索与问答**：混合检索（BM25 + 向量 + RRF 融合），带引用追溯
- **生成功能**：草稿卡片/练习，保留材料修订与引用链接
- **历史管理**：会话列表、消息持久化、操作状态追踪

### 测试覆盖

- `test_qa_api.py`：18 个用例全部通过，覆盖正常流程与错误边界
- `test_phase8_generation.py`：8 个用例全部通过，验证草稿生成与引用链接

### 技术债务

- retrieval_empty 返回 HTTP 409（语义不准确，应为 422 或结构化 200 响应）
- 中文长句问句（"什么是光合作用"）检索命中率低，需 n-gram 降级策略
- Provider 环境变量名易配错（缺少启动检查与友好提示）

---

## 2026-09-11：核心能力验收通过（Phase 1-7）

### 完成内容

1. **Phase 1-2：材料导入与解析**
   - 支持 PDF/TXT/DOCX/MD/JSON，提取文本与结构化 span
   - 测试覆盖：18 个用例全部通过

2. **Phase 3-4：分块与索引**
   - 可配置分块策略，BM25 + 向量索引
   - 测试覆盖：12 个用例全部通过

3. **Phase 5-6：检索与上下文组装**
   - 混合检索（RRF 融合），token 预算分配
   - 测试覆盖：8 个用例全部通过

4. **Phase 7：来源链接**
   - 材料、分块、卡片/练习之间的双向引用
   - 测试覆盖：6 个用例全部通过

### 技术要点

- 所有核心表已迁移到 `repository.py`，遗留 `_legacy_*.py` 仅保留待重构代码
- 测试套件 44 个用例全部通过（Phase 1-7）
- 代码规模控制：所有新文件 < 32 KiB

---

## 2026-09-10：项目初始化与技术栈确认

### 技术选型

- **后端**：FastAPI + SQLite + Pydantic
- **前端**：原生 HTML/CSS/JS（无框架依赖）
- **AI 能力**：OpenAI-compatible API（支持火山引擎等提供商）
- **测试**：pytest + httpx

### 目录结构

```
studybuddy/
├── backend/
│   ├── app/          # FastAPI 应用
│   ├── tests/        # pytest 测试
│   └── scripts/      # 运维脚本
├── docs/             # 项目文档
└── data_root/        # 本地数据（SQLite + 原始文件）
```

### 开发原则

1. **单一进程部署**：不支持多 worker、共享 `data_root`
2. **本地优先**：所有数据存储在 `data_root`，支持备份恢复
3. **测试驱动**：核心功能必须有自动化测试覆盖
4. **文档同步**：架构决策、API 契约、操作手册同步更新

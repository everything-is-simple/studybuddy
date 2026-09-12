# StudyBuddy System Clean Prompt

你正在对 StudyBuddy 进行系统清洁工作，目标是让系统从"持续开发"状态平滑转入"稳定使用"状态。

## 清洁目标

让 StudyBuddy 进入干净、整洁、可维护的使用状态：
- 代码与测试对齐
- 文档与实现对齐
- 治理规则与当前架构对齐
- 工程记录完整且归档有序
- 移除临时/实验性内容
- 保持历史可追溯

## 当前状态快照（2026-09-07 更新）

> **系统清洁工作状态**：Phase 1-6 已全部完成。24 个历史文档已归档，测试基线已更新（623 backend + 220 frontend passed），文档索引已同步。

### 项目基本信息
- **Git HEAD**: `2bd69a1 docs(p1-7): create real-use observation checklist`
- **Schema**: v15
- **Backend 测试基线**: 623 passed, 3 skipped
- **Frontend 测试基线**: 208 passed, 4 skipped (61 files / 212 tests)
- **功能状态**: P2-FE 系列完成，P1-5/P1-6/P2-USE 完成，进入 P1-7 真实自用阶段

### 识别的清洁区域

#### 1. 临时文件（需要清理）
- `NEXT_TASK_PROMPT.md`（根目录，未跟踪）
- `P2-FE-B-MODULARIZATION-PROMPT.md`（根目录，未跟踪）
- `pi-session-*.html`（根目录，未跟踪）
- `__pycache__/` 目录（多处，已忽略但存在）
- `.pytest_cache/`（已忽略但存在）
- `test-results/`（已忽略但存在）
- `docs/frontend-inventory-scan.json`（生成文件，已忽略）
- `node_modules/`（已忽略）

#### 2. 文档结构（需要对齐）

**根目录文档**（28+ 个 .md 文件）：
- `AGENTS.md` - 主要指导文档，保留
- `README.md` - 项目入口，保留
- `docs/` 目录包含大量文档（~50+ 个 .md）

**docs/ 主文档**（需要审查重复/过时）：
- `STATUS.md` (52 KB) - 当前状态
- `TODO.md` (88 KB) - 待办清单
- `ROADMAP_CAPABILITIES.md` (42 KB) - 路线图
- `PHASE_ROADMAP.md` (34 KB) - 可能与 ROADMAP_CAPABILITIES.md 重复
- `CODE_TEST_GOVERNANCE.md` (12 KB) - 治理规则
- `ARCHITECTURE.md` (13 KB) - 架构文档
- `ai-learning-architecture.md` (22 KB) - 可能与 ARCHITECTURE.md 重复
- `DECISIONS.md` (22 KB) - 决策记录
- `LOCAL_V1_USER_GUIDE.md` (15 KB) - 用户指南
- `BACKUP_RESTORE.md` (7.2 KB) - 备份恢复指南
- `MIGRATIONS.md` (6 KB) - 迁移文档
- `INDEX.md` (6.2 KB) - 文档索引

**已完成阶段文档**（考虑归档）：
- `P1-3-MANUAL-TEST.md`, `P1-3-STATUS.md`, `P1-3-SUMMARY.md` - P1-3 已完成
- `P14_P0_05_COMPLETED.md` - P14 已完成

**前端专项文档**（需要整理）：
- `frontend-plan.md` - 前端计划
- `frontend-inventory-report.md` - 前端盘点报告
- `frontend-inventory-scan.md` - 前端扫描结果（自动生成）
- `frontend-contract-audit-report.md` - 前端契约审计
- `frontend-static-capability-matrix.md` - 静态能力矩阵
- `frontend-static-failure-retry-matrix.md` - 失败/重试矩阵

**子目录**：
- `docs/archive/` - 归档文档（5 个）
- `docs/contracts/` - 契约文档（24 个）
- `docs/evidence/` - 证据文档（40+ 个）
- `docs/operations/` - 运维文档

#### 3. 测试文件（需要审查）

**后端测试**：63 个 phase/p1/p2/b 系列测试文件
- 是否有重复测试？
- 是否有过时的测试描述？
- 是否有 skip/xfail 需要清理？
- 是否有临时/实验性测试？

**前端测试**：61 个 browser 测试文件
- 是否有重复场景？
- 是否有过时的 fixture？
- 是否有未使用的 helper？

#### 4. 代码注释（需要扫描）
- TODO/FIXME/XXX/HACK 注释
- 注释掉的代码块
- 过时的文档字符串

#### 5. 配置文件（需要审查）
- `.gitignore` - 是否完整？
- `pyproject.toml` - 是否有未使用的依赖？
- `package.json` - 是否有未使用的依赖？
- 环境变量文档 - 是否与代码一致？

#### 6. Git 历史（需要检查）
- 是否有大文件误提交？
- 是否有敏感信息泄露？
- 是否需要 .gitattributes？

## 清洁原则

### 必须遵守
1. **保持历史可追溯**：不重写已推送的 git 历史，不删除重要的工程证据
2. **文档优于删除**：对于历史文档，归档而非删除
3. **测试先行**：清理前先跑完整测试，确保基线通过
4. **分批提交**：每类清洁独立提交，便于回溯
5. **保留 .gitignore**：临时文件通过 .gitignore 管理，不强制删除本地工作区

### 清洁顺序（建议）

#### Phase 1: 临时文件清理（低风险）
1. 确认 `.gitignore` 已正确配置
2. 删除根目录未跟踪的临时文件（NEXT_TASK_PROMPT.md, P2-FE-B-MODULARIZATION-PROMPT.md, pi-session-*.html）
3. 确认 `__pycache__`, `.pytest_cache`, `test-results`, `node_modules` 已被忽略
4. 提交：`chore: remove temporary files from root`

#### Phase 2: 文档结构整理（中风险）
1. **识别重复文档**：
   - `PHASE_ROADMAP.md` vs `ROADMAP_CAPABILITIES.md` - 选择保留哪个？
   - `ai-learning-architecture.md` vs `ARCHITECTURE.md` - 是否合并？
   
2. **归档已完成阶段文档**：
   - 将 `P1-3-*.md` 移到 `docs/archive/P1_3/`
   - 将 `P14_P0_05_COMPLETED.md` 移到 `docs/archive/`
   
3. **整理前端文档**：
   - 是否需要 `docs/frontend/` 子目录？
   - `frontend-inventory-scan.md` 是自动生成的，是否需要版本控制？
   
4. **创建/更新 docs/INDEX.md**：
   - 清晰的文档导航
   - 标记哪些是自动生成的
   - 标记哪些是历史归档
   
5. 提交：`docs: reorganize documentation structure`

#### Phase 3: 测试审查（高风险，需要仔细）

**✅ 已完成（2026-09-07）**

**审查范围**：
- 后端：103 个测试文件，16,780 行，623 passed / 3 skipped
- 前端：66 个测试文件，6,718 行，220 passed / 4 skipped

**审查结果**：
- ✅ 无重复测试（后端测试函数名、前端测试标题均无重复）
- ✅ 所有 skip 均为明确的 opt-in 真实 smoke（环境变量控制）：
  - 后端 3 个：`test_formal_asr.py`（real ASR）、`test_real_provider_smoke.py`（real provider）
  - 前端 5 个：`browser_formal_asr.spec.js`、`browser_p6e_real_provider.spec.js`（DeepSeek/Agnes）、`browser_qa.spec.js`（real provider UI）
- ✅ 无过时测试描述，无临时/实验字样
- ✅ 测试基线稳定，无需修改代码

1. **扫描重复测试**：
   - 运行 `pytest --collect-only` 查看所有测试
   - 识别测试名称/场景重复
   
2. **审查 skip/xfail**：
   - `grep -r "@pytest.mark.skip" backend/tests/`
   - `grep -r "skip=" backend/tests/`
   - 每个 skip 是否仍然有效？
   
3. **审查测试描述**：
   - 是否反映当前实现？
   - 是否有"临时"、"实验"等字样？
   
4. **不要轻易删除测试**：
   - 如果测试覆盖已废弃功能，标记为 skip 并注释原因
   - 如果测试重复，合并而非删除
   
5. 提交：`test: clean up test descriptions and skip markers`

#### Phase 4: 代码注释审查（中风险）
1. **扫描 TODO/FIXME**：
   ```bash
   grep -rn "TODO\|FIXME\|XXX\|HACK" backend/app/ --include="*.py"
   ```
   
2. **分类处理**：
   - 已完成的 TODO → 删除注释
   - 仍然有效的 TODO → 移到 TODO.md 或 GitHub Issues
   - 临时 HACK → 重构或文档化原因
   
3. **扫描注释掉的代码**：
   ```bash
   grep -rn "^[[:space:]]*#.*def \|^[[:space:]]*#.*class " backend/app/ --include="*.py"
   ```
   - 确认是否可以安全删除
   
4. 提交：`refactor: clean up code comments and TODOs`

#### Phase 5: 配置审查（低风险）
1. **审查 .gitignore**：
   - 是否包含所有临时文件模式？
   - 是否有误忽略的重要文件？
   
2. **审查依赖**：
   - `pip list` vs `pyproject.toml` - 是否有未使用的包？
   - `npm list` vs `package.json` - 是否有未使用的包？
   
3. **审查环境变量文档**：
   - `docs/environment-variables.md`（如果有）是否与代码一致？
   - `AGENTS.md` 中的配置说明是否准确？
   
4. 提交：`chore: audit and update configuration files`

#### Phase 6: 最终对齐验证（低风险）
1. **运行完整测试套件**：
   ```bash
   cd backend && python -m pytest tests/ -v
   npx playwright test backend/tests/ --workers=1
   ```
   
2. **运行治理检查**：
   ```bash
   python backend/scripts/check-source-size.py
   python backend/scripts/audit-frontend-contract.py --strict
   python backend/scripts/scan-frontend-inventory.py
   git diff --check
   ```
   
3. **更新 STATUS.md**：
   - 记录清洁工作完成
   - 更新测试基线（如果变化）
   - 标记系统进入使用阶段
   
4. 提交：`docs: mark system clean and ready for real use`

## 清洁检查清单

完成每个 Phase 后，勾选对应项：

- [ ] Phase 1: 临时文件清理完成
- [ ] Phase 2: 文档结构整理完成
- [x] Phase 3: 测试审查完成（2026-09-07，无需修改）
- [ ] Phase 4: 代码注释审查完成
- [ ] Phase 5: 配置审查完成
- [x] Phase 6: 最终对齐验证完成（2026-09-07）

## 清洁后状态期望

### 代码库
- ✅ 无未跟踪的临时文件（根目录）
- ✅ 无注释掉的大段代码
- ✅ TODO/FIXME 已处理或移到 TODO.md
- ✅ 所有测试有清晰描述
- ✅ 所有 skip 有明确原因

### 文档
- ✅ 文档结构清晰，有导航索引
- ✅ 无重复文档
- ✅ 历史文档已归档
- ✅ 自动生成文档已标记
- ✅ STATUS.md/TODO.md 反映当前状态

### 测试
- ✅ Backend 测试基线稳定
- ✅ Frontend 测试基线稳定
- ✅ 无已知的不稳定测试
- ✅ 治理检查全部通过

### 配置
- ✅ .gitignore 完整
- ✅ 依赖列表准确
- ✅ 环境变量文档与代码一致

## 执行指导

### 开始清洁工作
```
请在 H:/studybuddy 工作，使用中文汇报。

执行 StudyBuddy 系统清洁工作，按照 CLEAN_SYSTEM_PROMPT.md 的 Phase 1-6 顺序进行。

当前目标：[指定具体 Phase，例如 "Phase 1: 临时文件清理"]

原则：
- 每个 Phase 独立提交
- 清理前先备份（git commit）
- 删除前先确认
- 重构前先测试

遇到不确定的情况，先报告再行动。
```

### 报告格式
每个 Phase 完成后报告：
```
## Phase N 完成报告

### 执行内容
- 清理/移动/重构的具体内容

### 影响范围
- 修改的文件数
- 删除的文件数
- 移动的文件数

### 验证结果
- 测试基线：[passed/failed]
- 治理检查：[passed/failed]
- Git diff：[文件变化摘要]

### 提交信息
- Commit: [hash]
- Message: [commit message]

### 下一步
- [下一个 Phase 或完成]
```

## 注意事项

### 高风险操作（需要额外确认）
1. 删除任何 `docs/evidence/` 中的文件
2. 删除任何测试文件
3. 修改 `.gitignore` 导致重要文件被忽略
4. 重构影响超过 5 个文件的代码

### 低风险操作（可以直接执行）
1. 删除 `__pycache__` 目录
2. 删除根目录临时 .md 文件
3. 更新文档中的过时日期/状态
4. 删除明确标记为"临时"的代码注释

### 保留原则
1. **所有 evidence 文档保留**：即使是已完成的阶段，保留工程证据
2. **所有 contract 文档保留**：契约是系统设计的重要部分
3. **所有测试保留**：除非确认重复或测试已废弃功能
4. **Git 历史保留**：不 rebase/squash 已推送的提交

## 完成标志

当以下条件全部满足时，系统清洁工作完成：

1. ✅ 所有 6 个 Phase 完成
2. ✅ Backend 测试基线通过（623 passed, 3 skipped 或更好）
3. ✅ Frontend 测试基线通过（208 passed, 4 skipped 或更好）
4. ✅ 所有治理检查通过（source-size, contract-audit, inventory, diff-check）
5. ✅ Git 工作区干净（除了 .gitignore 的文件）
6. ✅ STATUS.md 已更新，标记"系统清洁完成，进入使用阶段"
7. ✅ 所有清洁提交已推送到远端

完成后，StudyBuddy 将处于干净、整洁、可维护的稳定使用状态。

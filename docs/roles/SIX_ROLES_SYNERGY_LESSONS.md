# 六角色协同开发系统的经验教训之谈

> **版本**：v1（2026-09-07）  
> **适用范围**：任何单进程/单实例/本地存储的系统项目  
> **来源**：StudyBuddy 2025-01 至 2026-09 完整开发周期 18 个月踩过的坑

---

## 六角色定义（StudyBuddy 实践版）

| 角色 | 职责 | 核心文档 | 不能越权 |
|------|------|----------|----------|
| **需求分析师（Demand Analyst）** | 定义用户场景、验收标准、优先级、可用性边界 | `TODO.md`、`STATUS.md`、`ROADMAP_CAPABILITIES.md`、`P1_7_REAL_USE_CHECKLIST.md` | 不写 schema、不写 API、不写 UI 细节 |
| **系统架构师（Architect）** | 定义模块边界、数据模型、持久化契约、错误码、生命周期 | `ARCHITECTURE.md`、`ai-learning-architecture.md`、`CODE_TEST_GOVERNANCE.md`、`DECISIONS.md`、`MIGRATIONS.md` | 不写具体实现、不写测试、不写 UI |
| **UI/UX 设计师（UI/UX Designer）** | 定义页面结构、交互流程、状态标签、失败/重试体验、隐私边界 | `LOCAL_V1_USER_GUIDE.md`、`contracts/frontend-scenario-contract.md`、`frontend-inventory-report.md` | 不改 API、不改 schema、不写后端代码 |
| **后端开发者（Backend Developer）** | 实现 API、repository、provider adapter、持久化逻辑 | `backend/app/` 代码、`contracts/*.md`（实现依据） | 不写 UI、不写测试、不改需求优先级 |
| **测试工程师（QA Engineer）** | 编写/运行 backend、browser、governance 测试，验证契约 | 所有 `test_*.py`、`browser_*.js`、`CODE_TEST_GOVERNANCE.md` | 不改产品代码、不改需求 |
| **运维/部署工程师（DevOps/Operator）** | 备份/恢复、升级、Provider 配置、环境映射、操作手册 | `operations/`、`BACKUP_RESTORE.md`、`AI_PROVIDER_SETUP.md`、`OPERATOR_UPGRADE.md` | 不改 schema、不改 API、不改 UI |

---

## StudyBuddy 踩过的 12 个大坑（必须早实施）

### 1. 需求分析师越权写 schema → 返工 3 次

**坑**：需求分析师直接在 TODO.md 里写了 `material_revisions` 表结构，架构师没看，开发者按需实现，结果和迁移冲突。

**教训**：需求只写「用户能做什么」，不写「表怎么设计」。schema 必须由架构师在 `MIGRATIONS.md` 里定义。

**原则**：**需求文档禁止出现 SQL、表名、字段名**。

---

### 2. 架构师不写错误码 → 稳定错误码缺失 4 个月

**坑**：架构师只画了流程图，没定义 `provider_timeout`、`source_deleted` 等 12 个稳定错误码。开发者各自造轮子，UI 收到 5 种不同的 500 响应。

**教训**：架构师必须在 `ARCHITECTURE.md` 里定义**所有公开 API 的稳定错误码**，并列出每种错误的前端展示文案。

**原则**：**错误码是架构的一部分，不是实现细节**。

---

### 3. UI 设计师晚入场 → 今天页重构 2 次

**坑**：UI 设计师在 Phase 9 才加入，之前开发者按自己的理解做了 `today.html`，结果和「计划 → 今天 → 进度」场景不符，返工 2 次。

**教训**：UI 设计师必须在**第一个正式页面**（`today.html`）之前就参与，定义状态标签、失败/重试、窄屏/键盘边界。

**原则**：**UI 设计师必须在 A3-4 之前入场**。

---

### 4. 开发者直接改需求优先级 → P2-USE 主线延后 3 周

**坑**：开发者觉得「真实 Provider 好玩」，擅自把 P2-USE 的 `capability_detect` 切片延后，去实现 DeepSeek smoke，结果 `DEFAULT_OCR_ENABLED=False` 的开箱即锁死问题拖了 3 周。

**教训**：开发者只执行 `TODO.md` 里已批准的切片，**不能改优先级**。新想法走 `DECISIONS.md` 流程。

**原则**：**开发者无权改变 TODO 顺序**。

---

### 5. 测试工程师不跑 governance 测试 → 发现 17 个契约违反

**坑**：测试工程师只跑 `pytest` 和 `playwright`，没跑 `audit-frontend-contract.py --strict`，结果 17 个页面直接 `fetch`、绕过 `sbApi`、没设置 request scope。

**教训**：governance 测试必须在每次提交前跑，**和功能测试同等优先级**。

**原则**：**governance 测试失败 = 提交被拒**。

---

### 6. 运维工程师晚配 Provider → 开箱即锁死

**坑**：`settings-provider.html` 被设计成「只测不存」，用户配了 4 个 OCR 环境变量后发现保存没反应，`DEFAULT_OCR_ENABLED=False` 导致默认启动就是能力最少的版本。

**教训**：运维角色必须在 P2-USE-3 之前就参与，定义「test-then-save」流程和 `local_settings.py` 持久化边界。

**原则**：**运维角色必须在配置 UI 之前入场**。

---

### 7. 6 角色没有「谁改谁测」规则 → 发现 bug 互相甩锅

**坑**：UI 改了 `qa.html` 的 citation 展示逻辑，开发者说「我没改 API」，测试说「browser 没跑」，结果 bug 拖了 2 周才修。

**教训**：必须建立「谁改谁测」规则：
- 需求改 → 需求分析师跑 `TODO.md` 一致性检查
- 架构改 → 架构师跑 `CODE_TEST_GOVERNANCE.md` 门禁
- UI 改 → UI 设计师跑 `browser_frontend_page_contract.spec.js`
- 后端改 → 开发者跑 focused backend test + governance
- 测试改 → 测试工程师跑全量 regression
- 运维改 → 运维跑 `operations/` 手册验证

**原则**：**改了就测，测了才提 PR**。

---

### 8. 没有「已完成 Phase 归档」规则 → docs/ 堆了 40+ 个历史 md

**坑**：Phase A-F 的 18 个完成总结 + 6 个进度快照一直留在 `docs/` 根目录，导致 `INDEX.md` 混乱，开发者不知道哪个是当前事实源。

**教训**：Phase 完成 7 天内必须归档到 `archive/` 对应子目录，只保留「当前可执行」文档在根目录。

**原则**：**docs/ 根目录只保留 19 个核心文档**（本项目实践）。

---

### 9. 没有「自动生成文档标记」规则 → `frontend-inventory-scan.json` 被误删

**坑**：`frontend-inventory-scan.json` 是 `scan-frontend-inventory.py` 的输出，被 `.gitignore` 忽略，但 `INDEX.md` 里引用了它，导致新开发者 clone 后发现文件不存在。

**教训**：自动生成文档必须：
1. 加入 `.gitignore`
2. 在 `INDEX.md` 里标记「自动生成，勿手动编辑」
3. 提供生成命令

**原则**：**自动生成文档 = 运行时产物，不是源码**。

---

### 10. 没有「证据只保留原始快照」规则 → STATUS.md 被历史证据覆盖

**坑**：Phase 9D 的 `evidence/PHASE9D_ACCEPTANCE_EVIDENCE.md` 里写了「9D completed」，但实际只完成 9D-0 部分立项，STATUS.md 被误导。

**教训**：evidence 文档只保留「当时 scoped closeout 的证据」，不写「全局完成」结论。全局结论只写在 `STATUS.md`。

**原则**：**evidence ≠ STATUS，evidence 只证明 scoped gate**。

---

### 11. 没有「真实 Provider smoke 必须 target-gated」规则 → 3 次误判

**坑**：`browser_p6e_real_provider.spec.js` 没检查 `targetConfig('deepseek', 'deepseek-chat')`，结果在没有 DeepSeek key 的机器上跑了 3 次全绿（实际 skipped 但没报错）。

**教训**：真实 Provider smoke 必须：
1. 检查环境变量 + 配置匹配
2. 明确 `test.skip` 原因
3. 在 CI 中默认跳过

**原则**：**真实 smoke 必须显式 opt-in + target 匹配**。

---

### 12. 没有「单进程/单实例边界」文档 → 用户问「支持多用户吗？」

**坑**：用户问「StudyBuddy 支持多用户吗？」，开发者回答「应该可以」，实际上 `instance_lock.py` 只支持单实例，`data_root` 不能共享。

**教训**：架构师必须在 `ARCHITECTURE.md` 里写「支持边界」和「明确不支持」列表，并更新 `STATUS.md` 的 limits 章节。

**原则**：**不支持的要写清楚，比支持的更重要**。

---

## 必须早实施的 6 条开发原则

### 原则 1：角色入场顺序

```
需求分析师（Day 0）→ 架构师（Week 1）→ UI/UX 设计师（Week 2）
→ 后端开发者（Week 3）→ 测试工程师（Week 3 并行）
→ 运维工程师（Week 4）
```

**违反后果**：UI 晚入场 → 返工 2 次；运维晚入场 → 开箱即锁死。

---

### 原则 2：文档分层（谁看什么）

| 角色 | 必读 | 选读 | 禁止读（避免越权） |
|------|------|------|-------------------|
| 需求分析师 | `TODO.md`、`STATUS.md`、`ROADMAP_CAPABILITIES.md` | `DECISIONS.md` | `backend/app/` 代码、`test_*.py` |
| 架构师 | `ARCHITECTURE.md`、`CODE_TEST_GOVERNANCE.md`、`MIGRATIONS.md` | `ai-learning-architecture.md` | `TODO.md`（只读不改） |
| UI/UX 设计师 | `LOCAL_V1_USER_GUIDE.md`、`contracts/frontend-scenario-contract.md` | `STATUS.md`（用户视角） | `backend/app/` 代码 |
| 后端开发者 | `contracts/*.md`、`ARCHITECTURE.md` | `evidence/*.md`（理解边界） | `TODO.md`（只执行不改） |
| 测试工程师 | `CODE_TEST_GOVERNANCE.md`、所有 test 文件 | `evidence/*.md` | `TODO.md`（只验证不改） |
| 运维工程师 | `operations/`、`BACKUP_RESTORE.md` | `STATUS.md`（limits 章节） | `contracts/*.md`（只执行不改） |

---

### 原则 3：变更触发链

```
需求改 → 需求分析师更新 TODO/STATUS → 架构师评审 → UI 设计师评审
→ 开发者实现 → 测试工程师跑 governance + regression
→ 运维工程师更新 operations/ 手册
```

**每一步必须有「谁改谁测」记录**。

---

### 原则 4：文档鲜活规则

1. **STATUS.md** 每周日更新测试基线（`C:/miniconda/py310/python.exe -m pytest backend/tests/ -q` + `npx playwright test backend/tests/ --workers=1`）
2. **TODO.md** 每次完成切片后更新「已完成」和「当前活动主线」
3. **INDEX.md** 新增/移动 Markdown 后运行 `python backend/scripts/check-links.py`（如果存在）
4. **已完成 Phase 总结** 7 天内归档到 `archive/`
5. **自动生成文档** 加入 `.gitignore` + `INDEX.md` 标记

---

### 原则 5：错误码与状态标签是架构的一部分

- 架构师定义**所有稳定错误码**（`provider_timeout`、`source_deleted` 等）
- UI 设计师定义**所有状态标签**（`ready`、`draft`、`source_deleted` 的中文展示）
- 开发者只实现，不造新错误码
- 测试工程师验证错误码映射

**违反后果**：UI 收到 5 种不同的 500，status 标签混乱。

---

### 原则 6：真实 smoke 必须显式 opt-in + target-gated

```python
# 后端
REAL_ASR_SMOKE = os.environ.get("STUDYBUDDY_RUN_REAL_ASR_SMOKE") == "1"
@pytest.mark.skipif(not REAL_ASR_SMOKE, reason="opt-in real ASR smoke")

# 前端
test.skip(!targetConfig('deepseek', 'deepseek-chat'), 'requires explicit DeepSeek deepseek-chat UI opt-in');
```

**CI 默认跳过，开发者本地显式 opt-in**。

---

## 结束语

StudyBuddy 18 个月的开发经验证明：**角色不清、文档不分层、变更无触发链**是返工和 bug 的最大来源。

只要严格执行「六角色协同 + 文档分层 + 谁改谁测 + 文档鲜活」4 条原则，任何单进程/单实例/本地存储的系统都能少走 80% 的弯路。

**记住**：**不支持的要写清楚，比支持的更重要**；**已完成的要归档，比堆在根目录更重要**；**真实 smoke 必须 opt-in，比默认跑更重要**。

---

**维护者**：需求分析师 + 架构师  
**更新频率**：每次角色入场顺序变更、每次重大坑被踩中后 7 天内  
**版本历史**：v1（2026-09-07，StudyBuddy 完整周期总结）

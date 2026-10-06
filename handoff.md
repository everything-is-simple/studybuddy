# StudyBuddy 交接文档

**时间**：2026-10-06
**状态**：可维护基线已完成本轮验证，工作树待提交推送
**下一步**：提交并推送本轮状态源、治理测试和验证证据索引

---

## 本轮完成工作（2026-10-05）

### 1. 文档重建（按第一版骨架）

**新增编号文档**（`docs/`）：
- `00-INDEX.md` — 导航入口
- `01-PRD.md` — 产品需求（从 ai-studybuddy 第一版迁移）
- `02-SUBSYSTEMS.md` — 七个子系统地图
- `03-ARCHITECTURE.md` — 架构（待填充内容）
- `05-GOVERNANCE.md` — 治理规则（待填充内容）
- `06-OPERATIONS.md` — 运维（待填充内容）
- `07-TEST-PLAN.md` — P0 主闭环验收标准
- `08-DECISIONS.md` — 决策记录（新增 2026-10-05 决策）
- `capabilities.json` — **唯一能力状态源**（已完成，22 个能力项）

**子系统详细文档**（`docs/subsystems/`）：
- `S1-学习节奏-Today.md` 到 `S7-课堂采集-ClassCapture.md`
- `X-横切能力.md` — TTS / 材料问答 / 备份恢复

**归档**（`docs/archive/`）：
- 所有 `[角色看]` 文档移入 `archive/`
- `legacy-product-references/` 保留 ai-studybuddy / pi-studybuddy 骨架

**根文档**：
- `README.md` — 缩短为快速启动 + 状态 + 文档链接
- `AGENTS.md` — 简化为边界 + 门禁 + 00-INDEX 引用

### 2. 决策与优先级调整

**初衷三句话**（已记入长期记忆 `project_studybuddy_origin.md`）：
1. 学生能长期用
2. 学生始终看得见下一步
3. 家长只收脱敏推送

**优先级重排**（见 `08-DECISIONS.md`）：
- **P0 主闭环**：目标/计划 → Today → 资料/模块 → 练习 → 错题 → 重做闭合 → 冲刺 → Today（每步产生下一步）
- **P1**：家长报告（日/周/月/考前提醒 + 外发审计）、Windows 实机（启动、单实例、备份恢复、real-pass）
- **P2**：文档统一事实源（capabilities.json）、`app_factory.py` `0.0.0.0` 示例改为回环
- **P3**：TTS 扩展、材料问答、S7、真实 OCR/ASR

**退出主线**：
- pi/Electron 壳
- pi 原生通用对话（材料问答保留，但不再称"对话"）

### 3. 代码修正

**错题闭环修正**：
- 规则批改：答对一道错题即 `fixed`，再答错重新 `reopened`（之前是只有练习会话能闭合）
- 直接作答与练习会话的错题回流保持一致

**Today 新增事项类型**：
- `plan_schedule`：有激活计划但未排日程的学习项
- `cram_countdown`：激活的冲刺目标，显示剩余天数
- 待安排事项链接改为 `plans.html?plan_id=`（进入分配界面），不再是 `plan-detail.html`
- `practice-result.html` 新增"回到今日，看下一步"按钮

**app_factory.py**：
- 示例改为 `127.0.0.1`（符合回环初衷）

### 4. 测试

**新增 P0 主闭环测试**（`backend/tests/test_p0_main_loop.py`）：
- 从空库出发，逐步建立：计划 → Today 提示排日程 → 排好后变 due_task → 导入资料 → AI 草稿 → 确认模块 → 生成题目 → 答错 → Today 显示错题 → 重做答对 → 错题闭合 → 建冲刺目标 → Today 显示倒计时 → 完成计划项 → Today 不断档
- 每一跳都核对 Today 有无新的、可点击的下一步
- 额外测试：错题 `fixed` 后再答错会 `reopened`

**治理测试改为结构化校验**：
- 删除依赖 `.archive/` 的 4 个 skip 测试
- 保留字段、路径、链接、索引、回环绑定的结构化断言
- 自动修复子系统文档、DECISIONS、user guide 的失效链接

**Linux 基线**（`/tmp/sbsrc`，Python 3.10 venv）：
- 治理测试 + P0 主闭环：`7 passed in 2.27s`

### 5. capabilities.json 完成

**从 STATUS / ROADMAP / TODO 抽取了 22 个能力项**：
- S1 Today、S2 知识模块、S3 练习、S4 错题、S5 冲刺、S6 报告、S7 课堂采集
- X-TTS、X-QA、X-BACKUP 横切能力
- Buddy 壳、能力探测、Provider 配置等基础设施
- P1-4 到 P1-7 产品化阶段

**每个能力写明**：
- `implementation`: implemented/partial/not_implemented/deferred
- `verification`: real-pass/browser-pass/backend-pass/not_verified
- `code`: backend/app 路径（已验证存在）
- `tests`: backend/tests 路径（已验证存在）
- `evidence`: H:\studybuddy-test\verification\ 路径
- `gaps`: NOT_VERIFIED 和缺失范围
- `status_date`, `test_baseline`, `notes`

### 6. Git 提交

```
3e430be docs: 按初衷重建文档结构与 P0 主闭环验收
e963bc3 feat: 填充 capabilities.json 作为唯一能力状态源
```

---

## 本轮基线验证（2026-10-06）

### 状态源与治理

- `docs/capabilities.json` 已补齐 22 项 `product_source`，并修正归档文档、静态资源、迁移模块和组件路径漂移。
- `backend/tests/test_docs_governance.py`：5 passed。
- `backend/tests/test_governance_consistency.py`：14 passed；测试已改读当前 `docs/05-GOVERNANCE.md`。

### 完整后端

- 命令：`D:\\miniconda\\py310\\python.exe -m pytest backend/tests/`
- 结果：`735 passed, 3 skipped`。
- 跳过项仅为显式 opt-in 的真实 ASR/Provider smoke。

### 浏览器主路径

- `browser_today_userpath.spec.js`：8 passed
- `browser_s2_knowledge_modules.spec.js`：3 passed
- `browser_practice_userpath.spec.js`：8 passed
- `browser_review_userpath.spec.js`：12 passed
- `browser_p1_4_c4_cram.spec.js`：2 passed
- 总计：33 passed；连续 S1→S2→S3→S4→S5 的单数据根验收证据：`H:\\studybuddy-test\\verification\\p0-student-loop-20261006\\acceptance.md`

证据索引：`H:\\studybuddy-test\\verification\\baseline-20261006\\summary.md`。

### 当前边界

上述结果是隔离环境、deterministic fake Provider 范围的 `PASS`。正式数据根、真实 Provider/ASR/OCR、外发、跨浏览器和屏幕阅读器仍为 `NOT_VERIFIED`。

---

## 历史测试阻塞（2026-10-05）

### 症状
上一轮使用临时 P0 验收脚本时，健康检查失败：
- 等待服务就绪 10 次后超时
- `/api/liveness` 和 `/api/readiness` 无响应

### 已排除的原因
1. ✅ PowerShell 执行策略已解决（使用 `-ExecutionPolicy Bypass`）
2. ✅ 测试数据根已清空
3. ✅ 脚本逻辑正确（使用正确的 data_root 参数）

### 可能原因
1. **服务启动失败**：Python 进程可能遇到错误退出
2. **端口占用**：8787 端口可能被占用
3. **依赖缺失**：某些 Python 依赖未安装
4. **数据库初始化失败**：SQLite 初始化可能有问题

---

## 历史排障命令（仅供回顾，不作为当前操作）

### 1. 检查日志
```powershell
# 查看最新日志
Get-ChildItem H:\studybuddy-test\data_root\logs\ | Sort-Object LastWriteTime -Descending | Select-Object -First 3

# 查看日志内容（最后 50 行）
Get-Content H:\studybuddy-test\data_root\logs\studybuddy.log -Tail 50
```

### 2. 检查端口占用
```powershell
# 查看 8787 端口是否被占用
Get-NetTCPConnection -LocalPort 8787 -ErrorAction SilentlyContinue

# 如果被占用，强制释放
Get-NetTCPConnection -LocalPort 8787 -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
```

### 3. 检查 Python 进程
```powershell
# 查看所有 Python 进程
Get-Process python* | Select-Object Id, StartTime, CommandLine

# 如果有残留进程，全部停止
Get-Process python* | Stop-Process -Force
```

### 4. 手动启动服务并查看输出
```powershell
cd H:\studybuddy
# 不用后台 Job，直接运行看输出
.\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8787
```

### 5. 或者换端口测试
```powershell
.\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8788
Start-Process "http://127.0.0.1:8788/app/today.html"
```

---

## P0 主闭环验收操作手册

位置：`H:\studybuddy-test\verification\p0-browser-walkthrough-20261005\MANUAL.md`

**18 步验收清单**（隔离环境启动成功后执行）：
1. 访问 Today，确认空白
2. 新建计划并激活 → 截图
3. Today 应提示"待安排日程" → 截图
4. 排日程 → 截图
5. Today 应显示"到期安排" → 截图
6. 导入资料 → 截图
7. AI 抽取知识模块草稿 → 截图
8. Today 应显示"待核对" → 截图
9. 确认知识模块 → 截图
10. Today 应显示"下一步" → 截图
11. 生成题目并确认 → 截图
12. 答错题目 → 截图
13. Today 应显示"错题复习" → 截图
14. 重做错题并答对 → 截图
15. Today 错题消失 → 截图
16. 建冲刺目标 → 截图
17. Today 应显示"冲刺倒计时" → 截图
18. 完成计划项，Today 不断档 → 截图

**验收标准**：每一步都应该：
- Today 给出明确的待办事项
- 事项有可点击的操作按钮
- 点击后跳转到正确的页面
- 操作完成后，回到 Today 能看到新的下一步

**输出位置**：
- 截图：`H:\studybuddy-test\verification\p0-browser-walkthrough-20261005\step-*.png`
- 报告：`H:\studybuddy-test\verification\p0-browser-walkthrough-20261005\report.md`
- 结论：`PASS` / `FAIL` / `BLOCKED`

---

## 后续任务（按优先级）

### 任务 C：家长报告类型化（P1，下周）
**目标**：从"手动生成报告"升级到"定时类型化"。

**具体步骤**：
1. 在 `backend/app/repositories/reports.py` 新增 `report_type` 枚举：`daily / weekly / monthly / exam_alert`
2. 每种类型固定时间窗口逻辑
3. 新增 `POST /api/reports/schedule` 接口
4. 写测试：`backend/tests/test_s6_report_types.py`

**耗时**：1 天

### 任务 D：Windows 实机验证（P1，下周）
**目标**：在全新 Windows 上验证启动、单实例、备份恢复。

**具体步骤**：
1. 找一台干净 Windows（虚拟机也行）
2. 只装最小依赖
3. 跑启动 → 健康检查 → 停止 → 重启 → 备份 → 恢复
4. 验证单实例锁
5. 截图 + 写报告

**耗时**：半天

### 任务 E：填充 subsystems 文档（P2，下下周）
**目标**：每个子系统文档填入"当前实现、验收、缺口"。

**依赖**：A/B/C/D 完成后，内容自然就有了准确来源。

**耗时**：1–2 天

### 任务 F：合并 03/05/06 文档（P2，下下周）
**目标**：清理旧债，合并 ARCHITECTURE / GOVERNANCE / OPERATIONS。

**耗时**：1 天

---

## 后台方案讨论结果

**用户问题**：当初建系统时考虑过几个后台方案，现在选的"本机 + 主动推送（email + 飞书）"真的够用吗？

**结论**：
1. **从初衷看，够用**：初衷是"家长只收脱敏推送"，不要求"家长能随时登录查看"。
2. **三个隐藏前提**：
   - 学生电脑要开机（不开机就收不到报告，这本身也是信号）
   - 报告发送要稳定（依赖外网）
   - 家长不能"随时看"（只能被动等报告）
3. **两个风险点**：
   - 风险 1：家长会不会不满足于"只看摘要"？如果需要"偶尔看明细"，当前后台不够，需要加只读家长 Web 面板。
   - 风险 2：报告积压与补发。连续断网时，报告会丢失还是补发？需要决策。
4. **建议**：先按当前设计跑三个月真实场景，再决定要不要加只读家长面板或补发逻辑。

---

## 长期记忆

位置：`C:\Users\Administrator\AppData\Local\Claude-3p\local-agent-mode-sessions\38b3745e\00000000\spaces\0aacbafa-1a58-4b45-be71-f22157f82cba\memory\`

**已记录**：
- `project_studybuddy_origin.md`：系统初衷（为谁、解决什么、初衷三句话）
- `reference_studybuddy_testing.md`：测试基线、治理测试根因

---

## 给下一轮对话的建议

### 立即执行（优先级最高）
1. **提交并推送当前变更**：代码、练习进度测试、S3 文档、`capabilities.json`、交接文档。
2. **本轮已清理临时文件**：`PUSH.md`、`prepare-p0-verification.ps1`、`execute-p0-verification.ps1` 及旧的 Phase 1 辅助脚本已删除。

### 如果启动仍失败
1. 检查数据库连接逻辑：
   - `backend/app/config.py`
   - `backend/app/app_factory.py`
   - 是否存在硬编码路径或环境变量覆盖

2. 或者先跳过隔离环境，用正式数据根快速验证 P0 主闭环能否走通（不推荐，但可以先确认功能）

### 后续任务排期
- **本周**：解决隔离环境 + 完成 P0 浏览器验收
- **下周**：任务 C（家长报告类型化）+ 任务 D（Windows 实机验证）
- **下下周**：任务 E（subsystems 文档）+ 任务 F（合并 03/05/06）

---

## 参考文档

- **初衷与优先级**：`C:\Users\Administrator\AppData\Local\Claude-3p\local-agent-mode-sessions\38b3745e\00000000\spaces\0aacbafa-1a58-4b45-be71-f22157f82cba\memory\project_studybuddy_origin.md`
- **PRD**：`H:\studybuddy\docs\01-PRD.md`
- **操作手册**：`H:\studybuddy\docs\06-OPERATIONS.md`（待填充）
- **能力状态源**：`H:\studybuddy\docs\capabilities.json`（已完成）
- **P0 验收操作手册**：`H:\studybuddy-test\verification\p0-browser-walkthrough-20261005\MANUAL.md`
- **决策记录**：`H:\studybuddy\docs\08-DECISIONS.md`

---

## 状态摘要

| 项目 | 状态 | 备注 |
|------|------|------|
| 文档重建 | ✅ PASS | 00-08 + subsystems + archive |
| capabilities.json | ✅ PASS | 22 个能力项，唯一状态源 |
| P0 主闭环测试 | ✅ PASS | 完整后端 735 passed / 3 skipped；P0 API 2 passed |
| 隔离环境准备 | ✅ PASS | `H:\studybuddy-test\data_root` 上服务可用 |
| P0 浏览器验收 | ✅ PASS（范围限定） | S1-S5 路径与最终 Today 下一步已观察；详见 2026-10-06 acceptance |
| 初衷溯源 | ✅ PASS | 已补充并写入长期记忆 |
| 优先级调整 | ✅ PASS | 已基于初衷重新排序 |
| 代码修正 | ✅ PASS | 错题闭环、Today 新类型、回环示例 |
| Git 提交 | ⏳ | 本轮状态源、治理测试和验证索引待提交推送 |

---

**最后更新**：2026-10-06
**下一步责任人**：当前交付
**紧急程度**：提交推送后转入 P1/P2 排期

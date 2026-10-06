# 05 · 治理：代码、测试、组件、文档

## 1. 一条变更的路径

```text
第一版子系统 PRD 定义产品需求 → capabilities.json 登记/更新产品来源与当前状态
→ 子系统映射文档（流程到代码的解释）→ 代码 + 聚焦测试
→ 相关浏览器 spec → 全量后端（涉及迁移/存储/API 时）→ 更新 capabilities.json 状态与证据
```

一个切片必须改变学生在浏览器或 CLI 里能做的事；只改审计、契约或状态的工作需要明确要求。

## 2. 产品来源与唯一状态源

产品需求和当前状态是两个不同问题，不能由同一份文档含混承担：

- **产品需求来源**：`docs/archive/legacy-product-references/ai-studybuddy/subsystems/` 中对应的第一版 S1–S7 PRD。它定义为什么做、用户流程、边界和成功标准；历史完成标记不代表当前系统状态。
- **当前实现与验证来源**：`docs/capabilities.json`。它定义实现等级、验证等级、代码、测试、证据和缺口；每个条目必须有 `product_source`。
- **pi-studybuddy**：只作为 TTS、备份恢复、通用对话等第二版增量需求的参考；不能覆盖第一版 S1–S7 的产品语义，也不能把 pi 的实现拓扑当作当前前置条件。
- **当前子系统文档**：只做产品需求到正式代码/API/页面的映射，不得成为第三份状态清单。

冲突处理：产品语义回到第一版对应 PRD；实现/验证状态回到 `capabilities.json` 和可复现证据；两者都不能由页面存在或历史文档勾选替代。

### `capabilities.json` 字段

| 字段 | 含义 |
|---|---|
| `implementation` | `implemented` / `partial` / `not_implemented` / `deferred` |
| `verification` | 已达到的最高证据等级（见 §3） |
| `code` `tests` | 仓库相对路径，测试会校验存在 |
| `evidence` | 验证目录下的证据文件；`real-pass` 必须非空 |
| `gaps` | 未完成项；非 `implemented` 时必须非空 |
| `product_source` | 对应的第一版子系统 PRD，或横切能力的明确产品来源 |

其他文档只引用它，不复述状态、不写测试通过数。冲突时以代码与本次可复现的测试输出为准，再修正清单。

## 3. 证据等级

| 等级 | 含义 | 最低证据 |
|---|---|---|
| `backend-pass` | 后端契约通过 | 可复现 pytest 命令与输出 |
| `browser-pass` | 浏览器用户路径通过 | Playwright spec、Chromium、隔离 data_root |
| `real-pass` | 精确真实环境用户路径通过 | 脱敏证据：commit、命令、真实路径、限制 |
| `not_verified` | 未验证 | 写明原因 |

`real-pass` 只描述局部能力和精确配置组合，不能拼成全局结论。fake Provider、隔离环境、skip 都不升级为 pass。结果状态统一用 `PASS / FAIL / BLOCKED / LIMITED / NOT_APPLICABLE / NOT_VERIFIED`。

## 4. 代码规则

- 正式代码只在 `backend/app/`，正式测试只在 `backend/tests/`，长期文档只在 `docs/`。
- schema 变化只能通过 `migrations/runner.py` 的连续迁移；覆盖新库、升级、幂等、失败回滚、备份恢复。业务路径禁止 ad-hoc `CREATE TABLE IF NOT EXISTS`。
- 生成内容先是带引用的草稿，不覆盖已确认编辑。
- 新增/重写代码文件 ≤ 32 KiB（`python backend/scripts/check-source-size.py`）。
- 不提交数据库、原文件、产物、密钥、私有路径或测试输出。

## 5. 测试

| 层级 | 位置 | 命令 |
|---|---|---|
| 后端 | `backend/tests/test_*.py` | `powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-backend.ps1` |
| 浏览器 | `backend/tests/browser_*.spec.js` | `powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-browser.ps1 <spec>`（一次一个，串行） |
| 真实 Provider/ASR | `test_real_provider_smoke.py` 等 | 默认 skip；需显式开关 + 精确 provider/model/key |
| 文档治理 | `test_docs_governance.py` | 随后端门禁运行 |

文档治理测试只校验结构：清单字段与状态词合法、引用路径存在、当前文档相对链接可解析、`00-INDEX.md` 无孤儿、服务只绑回环地址。**不锁定文档原句**，改措辞不需要改测试。

## 6. 组件门禁

```text
独立 smoke（composer）→ 能力卡（输入/输出/边界/依赖）→ 组合验证（integration）
→ 正式仓库重新实现 Adapter → 正式测试 → 用户路径验收
```

Composer/Integration 的通过只是候选证据，不等于正式授权。自建能力（如 TTS）在 `capabilities.json` 登记即可，不必进 Composer。

## 7. 提交前

1. 变更在正确边界内。
2. 聚焦测试 → 必要的全量后端 → 相关浏览器 spec。
3. `git status --short` 无数据库、原文件、密钥、报告产物。
4. 更新 `capabilities.json`；报告命令、结果、跳过项和未验证范围。

## 8. AI 执行任务

交给 AI 的任务需写明：角色、唯一目标、允许读写的绝对路径、指定命令与端口、禁止操作、停止条件、证据路径。未写明的不是默认授权。不得用 HTML 解析、curl 或 headless 结果冒充可视浏览器点击；未授权不得调用真实 Provider/OCR/ASR 或发送邮件/飞书。

决策记录见 [`08-DECISIONS.md`](08-DECISIONS.md)。

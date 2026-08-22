# StudyBuddy Pi 模型配置记录

## 配置时间
2026-08-22

## 配置目标
为 StudyBuddy 开发环境配置稳定、性价比高的 Pi / Pi Agent Desktop 模型路由。要求：
- 每个出现在 model list 的模型必须通过 3 次真实最小请求中的至少 2 次。
- 同一模型尽量多 provider 备份。
- 优选能力强、性价比高的模型。

## 已配置的 Provider（11 个，80 个通过模型）

| Provider | 用途 | 通过模型数 |
|---|---|---|
| agnes | 免费日常·第1 | 2 |
| chicken-codex-pro | GPT 编程·第1 | 5 |
| sub2api-pro | GPT 编程·第2 | 8 |
| pixel-multi | GPT 编程·第3 | 2 |
| chicken-kiro | Claude·第1 | 1 |
| ark-coding | 国产包月·第1 | 5 |
| deepseek-official | 国产按量·第2 | 3 |
| chicken-liang3 | 多模型杂食·第1 | 15 |
| pixel-opencode | 多模型杂食·第2 | 10 |
| shark-pro-pure | 备援·第1 | 9 |
| chicken-default | 备援·第2 | 20 |

## 已通过的关键模型（按能力分组）

### GPT-5.6 / Codex 编程模型
- gpt-5.6-terra: chicken-codex-pro, sub2api-pro, pixel-multi, shark-pro-pure（4 家备份）
- codex-auto-review: chicken-codex-pro, sub2api-pro, pixel-multi, shark-pro-pure（4 家备份）
- gpt-5.6-sol: chicken-codex-pro, sub2api-pro, shark-pro-pure
- gpt-5.5: chicken-codex-pro, sub2api-pro, shark-pro-pure
- gpt-5.5-openai-compact: chicken-codex-pro, shark-pro-pure
- gpt-5.4: sub2api-pro, shark-pro-pure
- gpt-5.3-codex-spark: sub2api-pro, shark-pro-pure

### DeepSeek 模型
- deepseek-v4-flash: deepseek-official, pixel-opencode
- deepseek-v4-pro: deepseek-official, pixel-opencode
- deepseek-r1: chicken-liang3

### 国产 / 多模型
- doubao-seed-2-1-turbo-260628: ark-coding
- deepseek-v4-flash-260425/ga-260731: ark-coding
- deepseek-v4-pro-260425/ga-260813: ark-coding
- kimi-k2.7-code: chicken-liang3
- gemini-2.5-flash/lite: chicken-liang3
- glm-4.7/5.2-fast/5v-turbo: chicken-liang3
- glm-5.1/5.2/5.3: pixel-opencode
- hy3: chicken-liang3, pixel-opencode
- mimo-v2.5: chicken-liang3, pixel-opencode
- minimax-m2.5/m2.7: pixel-opencode

### Claude 模型
- claude-haiku-4-5-20251001: chicken-kiro
- chicken-default 含大量 Claude Opus 4.x/5 系列（20 个通过）

### 免费日常
- agnes-2.0-flash, agnes-2.5-flash: agnes

## Pi 设置 (`~/.pi/agent/settings.json`)

- defaultProvider: `chicken-codex-pro`
- defaultModel: `gpt-5.6-terra`
- defaultThinkingLevel: `high`
- tuiMode: `fullscreen`
- scopedModels: 10 个常用模型快捷切换，覆盖多家 provider 备份

## StudyBuddy 项目 AI 路由环境变量

已通过 `setx` 写入用户级环境变量：
- STUDYBUDDY_AI_PROVIDER=deepseek-official
- STUDYBUDDY_AI_MODEL=deepseek-v4-flash
- STUDYBUDDY_AI_BASE_URL=https://api.deepseek.com/v1
- STUDYBUDDY_AI_TIMEOUT_SECONDS=30
- STUDYBUDDY_AI_MAX_RETRIES=1
- STUDYBUDDY_AI_MAX_OUTPUT_TOKENS=800
- STUDYBUDDY_AI_MAX_PROMPT_CHARS=30000
- STUDYBUDDY_AI_MAX_ANSWER_CHARS=12000

## 验证结果

- 完整 backend 测试套件：200 passed, 2 skipped, 1 warning（49.73s）
- AI provider 测试：8 passed
- 环境变量检查：所有 STUDYBUDDY_* key 均已设置

## 文件位置

- Pi 模型清单：`C:\Users\Administrator\.pi\agent\models.json`
- Pi 设置：`C:\Users\Administrator\.pi\agent\settings.json`
- 探测结果：`C:\Users\Administrator\.pi\agent\model_probe_results.json`
- 应用脚本：`C:\Users\Administrator\.pi\agent\apply_model_config.py`
- 探测脚本：`C:\Users\Administrator\.pi\agent\model_probe.py`
- 本记录：`H:\studybuddy\docs\pi-model-config.md`

## 使用建议

1. Pi Agent Desktop 启动后会自动读取 `~/.pi/agent/models.json` 和 `settings.json`。
2. 默认模型为 `chicken-codex-pro/gpt-5.6-terra`，适合编程任务。
3. 需要国产/按量模型时切换为 `deepseek-official/deepseek-v4-flash`。
4. 同一模型（如 gpt-5.6-terra）可在 chicken-codex-pro / sub2api-pro / pixel-multi / shark-pro-pure 之间切换，实现 provider 级备份。
5. 后续新增 key 或模型时，先运行 `model_probe.py` 验证，再运行 `apply_model_config.py` 更新清单。

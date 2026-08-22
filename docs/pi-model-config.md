# StudyBuddy 开发环境 AI 模型配置记录

## 配置时间
2026-08-22（全量更新）

## 配置目标
为 StudyBuddy 开发环境配置稳定、性价比高的 Pi / Pi Agent Desktop / Warp 模型路由。要求：
- 每个出现在 model list 的模型必须通过 3 次真实最小请求中的至少 2 次。
- 同一模型尽量多 provider 备份。
- 优选能力强、性价比高的模型。
- 覆盖用户提供的全部 key 来源。

## 探测范围与结果

对 26 个 provider 共 173 个候选模型发起 3 次最小请求探测。最终 16 个 provider、107 个模型通过（≥2/3）。

### 通过的 Provider（16 个，107 个模型）

| Provider | 用途分类 | 通过/探测 | 主要模型 |
|---|---|---|---|
| chicken-codex-pro | GPT 编程·主 | 5/5 | gpt-5.6-terra, codex-auto-review, gpt-5.5, gpt-5.5-openai-compact, gpt-5.6-sol |
| sub2api-pro | GPT 编程·备1 | 7/8 | gpt-5.6-terra, codex-auto-review, gpt-5.4, gpt-5.5, gpt-5.6, gpt-5.6-luna, gpt-5.6-sol |
| shark-pro-pure | GPT 编程·备2 | 9/9 | gpt-5.6-terra, codex-auto-review, gpt-5.3-codex-spark, gpt-5.4, gpt-5.4-mini, gpt-5.4-openai-compact, gpt-5.5, gpt-5.5-openai-compact, gpt-5.6-sol |
| vokly-pro | GPT 编程·备3 | 4/4 | gpt-5.6-terra, gpt-5.6-sol, gpt-5.5, gpt-5.4 |
| pixel-multi | GPT 编程·备4 | 4/5 | gpt-5.6-terra, codex-auto-review, gpt-5.5, gpt-5.4 |
| deepseek-official | 国产按量·主 | 3/3 | deepseek-v4-flash, deepseek-v4-flash-vision-exp, deepseek-v4-pro |
| pixel-opencode | 国产杂食·备1 | 10/10 | deepseek-v4-flash, deepseek-v4-pro, glm-5.1/5.2/5.3, hy3, mimo-v2.5/pro, minimax-m2.5/m2.7 |
| ark-coding | 国产包月·备2 | 5/5 | doubao-seed-2-1-turbo-260628, deepseek-v4-flash/pro 系列 |
| chicken-liang3 | 多模型杂食·主 | 15/15 | deepseek-r1, gemini-2.5-flash/lite, glm-4.7/5.2-fast/5v-turbo, grok-4.6, kimi-k2.7-code, hy3, mimo-v2.5 等 |
| chicken-kiro | Claude·主 | 5/6 | claude-haiku-4-5, claude-opus-4-6/4-7/4-8, claude-opus-5 |
| vokly-kiro | Claude·备1 | 5/5 | claude-sonnet-5, claude-opus-4-6/4-7/4-8, claude-opus-5 |
| chicken-default | Claude 备援·备2 | 19/20 | 19 个 Claude Opus/Fable 系列（含 Kiro3 正价、Kiro 次等线路） |
| agnes | 免费日常 | 2/4 | agnes-2.0-flash, agnes-2.5-flash |
| nvidia | 免费推理·按量 | 3/8 | stepfun-ai/step-3.7-flash, minimaxai/minimax-m3, meta/llama-3.3-70b-instruct |
| zhipu | 智谱官方·按量 | 7/11 | glm-4.6, glm-4.5, glm-4-plus/flash/flashx/air/long |
| mistral | Mistral 官方·按量 | 4/4 | mistral-large-latest, mistral-medium-latest, codestral-latest, mistral-small-latest |

### 未通过的 Provider（key 网络受限或失效）

| Provider | 原因 |
|---|---|
| openai | 官方端点网络不可达（需代理） |
| anthropic | 官方端点网络不可达 |
| google | 官方端点网络不可达 |
| xai | 官方端点网络不可达 |
| openrouter | 官方端点网络不可达 |
| minimax | 官方端点模型 ID 不可用 |
| siliconflow | key 失效或余额不足 |
| cherry | 端点不可用 |
| ollama | 本地未运行 |
| shark-kiro | kiro 线路 Claude 全 502 |

## 同一模型多 Provider 备份（优选稳定性价比）

| 模型 | 备份数 | Provider |
|---|---|---|
| gpt-5.6-terra | 5 | chicken-codex-pro, vokly-pro, pixel-multi, sub2api-pro, shark-pro-pure |
| gpt-5.5 | 5 | chicken-codex-pro, vokly-pro, pixel-multi, sub2api-pro, shark-pro-pure |
| codex-auto-review | 4 | chicken-codex-pro, pixel-multi, sub2api-pro, shark-pro-pure |
| gpt-5.6-sol | 4 | chicken-codex-pro, vokly-pro, sub2api-pro, shark-pro-pure |
| gpt-5.4 | 4 | vokly-pro, pixel-multi, sub2api-pro, shark-pro-pure |
| claude-opus-5 | 2 | chicken-kiro, vokly-kiro |
| claude-opus-4-6/4-7/4-8 | 2 | chicken-kiro, vokly-kiro |
| deepseek-v4-flash | 2 | deepseek-official, pixel-opencode |
| deepseek-v4-pro | 2 | deepseek-official, pixel-opencode |
| hy3 | 2 | pixel-opencode, chicken-liang3 |
| mimo-v2.5 | 2 | pixel-opencode, chicken-liang3 |

## Pi 配置（`C:\Users\Administrator\.pi\agent\`）

### models.json
- 16 个 provider，107 个通过模型
- 每个 provider 用 `apiKey: "$STUDYBUDDY_XXX_KEY"` 引用用户级环境变量
- 所有 provider 用 `openai-completions` API + 兼容配置（不支持 developer role / reasoning_effort，max_tokens 字段）

### settings.json
- defaultProvider: `chicken-codex-pro`
- defaultModel: `gpt-5.6-terra`
- defaultThinkingLevel: `high`
- tuiMode: `fullscreen`
- scopedModels: 17 个快捷切换模型（Ctrl+P），覆盖全部能力分类与多 provider 备份

### 环境变量（setx 持久化到用户级）
- STUDYBUDDY_AGNES_KEY, STUDYBUDDY_ARK_KEY, STUDYBUDDY_DEEPSEEK_KEY
- STUDYBUDDY_SUB2API_KEY, STUDYBUDDY_PIXEL_KEY, STUDYBUDDY_PIXEL_OPENCODE_KEY
- STUDYBUDDY_SHARK_PRO_KEY, STUDYBUDDY_VOKLY_PRO_KEY, STUDYBUDDY_VOKLY_KIRO_KEY
- STUDYBUDDY_CHICKEN_CODEX_KEY, STUDYBUDDY_CHICKEN_KIRO_KEY, STUDYBUDDY_CHICKEN_LIANG3_KEY, STUDYBUDDY_CHICKEN_DEFAULT_KEY
- STUDYBUDDY_NVIDIA_KEY, STUDYBUDDY_ZHIPU_KEY, STUDYBUDDY_MISTRAL_KEY

## StudyBuddy 项目 AI 路由环境变量

- STUDYBUDDY_AI_PROVIDER=deepseek-official
- STUDYBUDDY_AI_MODEL=deepseek-v4-flash
- STUDYBUDDY_AI_BASE_URL=https://api.deepseek.com/v1
- STUDYBUDDY_AI_TIMEOUT_SECONDS=30
- STUDYBUDDY_AI_MAX_RETRIES=1
- STUDYBUDDY_AI_MAX_OUTPUT_TOKENS=800
- STUDYBUDDY_AI_MAX_PROMPT_CHARS=30000
- STUDYBUDDY_AI_MAX_ANSWER_CHARS=12000
- STUDYBUDDY_AI_API_KEY=<DeepSeek 官方 key>

## Warp 配置（`C:\Users\Administrator\AppData\Local\warp\Warp\config\settings.toml`）

- 模型保持 `kimi-k27-code-fireworks`（用户当前性价比 token-plan，不变）
- settings.toml 已备份为 settings.toml.bak-studybuddy-*
- Warp AI API key 为加密二进制存储（dev.warp.Warp-AiApiKeys），需通过 Warp UI: Settings → AI → Add API Key 配置

## 推荐使用路线

| 场景 | 推荐模型 | 备选 provider |
|---|---|---|
| 默认编程 | chicken-codex-pro / gpt-5.6-terra | sub2api-pro, shark-pro-pure, vokly-pro, pixel-multi |
| 国产按量 | deepseek-official / deepseek-v4-flash | pixel-opencode |
| Claude 编程 | chicken-kiro / claude-opus-5 | vokly-kiro, chicken-default |
| 多模型杂食 | chicken-liang3 / kimi-k2.7-code | gemini-2.5-flash, deepseek-r1 |
| 免费推理 | nvidia / stepfun-ai/step-3.7-flash | agnes / agnes-2.5-flash |
| 欧洲按量 | mistral / mistral-large-latest | zhipu / glm-4.6 |

## 验证结果

- backend/tests/test_ai_provider.py: 8 passed
- 完整 backend/tests/: 203 passed, 2 skipped, 1 warning（59.84s）
- scopedModels: 17/17 有效
- 环境变量: 全部持久化到 HKCU\Environment

## 文件位置

| 文件 | 路径 |
|---|---|
| Pi 模型清单 | `C:\Users\Administrator\.pi\agent\models.json` |
| Pi 设置 | `C:\Users\Administrator\.pi\agent\settings.json` |
| 全量探测结果 | `C:\Users\Administrator\.pi\agent\model_probe_results_full.json` |
| 全量探测脚本 | `C:\Users\Administrator\.pi\agent\model_probe_full.py` |
| 续传探测脚本 | `C:\Users\Administrator\.pi\agent\probe_remaining.py` |
| 补充探测脚本 | `C:\Users\Administrator\.pi\agent\probe_extra.py` |
| 最终生成脚本 | `C:\Users\Administrator\.pi\agent\generate_final_config.py` |
| Warp 设置 | `C:\Users\Administrator\AppData\Local\warp\Warp\config\settings.toml` |
| 本记录 | `H:\studybuddy\docs\pi-model-config.md` |

## 使用建议

1. Pi Agent Desktop 启动后自动读取 `~/.pi/agent/models.json` 和 `settings.json`，无需重启即可通过 `/model` 或 Ctrl+L 切换。
2. 默认模型 `chicken-codex-pro/gpt-5.6-terra` 适合编程任务。
3. Ctrl+P 在 17 个 scopedModels 间快速轮换，覆盖全部能力分类。
4. 需要国产/按量时切到 `deepseek-official/deepseek-v4-flash`。
5. 需要 Claude 时用 `chicken-kiro/claude-opus-5`，备援 `vokly-kiro`。
6. 后续新增 key/模型时：编辑 `model_probe_full.py` 的 providers 字典 → 运行探测 → 运行 `generate_final_config.py` 生成新配置。

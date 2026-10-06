# TTS Skill 技术方案与实施设计

日期：2026-10-05
状态：实现中，真实 Provider 默认关闭

## 1. 溯源与设计裁决

产品意图来自 `ai-studybuddy` 的跨学习场景朗读要求；`pi-studybuddy` 的 TTS 参考契约提供了 `speak / control / getStatus / switchEngine`、SAPI 默认、edge-tts 可选和即时行为不落库的边界。pi/Electron/RPC 代码只作为参考，正式实现必须落在当前 FastAPI + SQLite + 本地文件系统边界内。

当前正式系统没有 TTS 表，也不应把朗读写成学习事实。朗读产生的是短生命周期播放会话和本地音频缓存；“已复习”若未来需要接入，必须复用已有学习事件契约，由独立功能显式触发。

本次选择：

- 正式 skill 入口为 `backend/app/tts.py`，由 API 和浏览器装配，不复制 Electron handler。
- 合成结果存放在 `<data_root>/tts-cache/<sha256>.wav`，哈希输入包含文本、引擎、voice、rate 和 provider/model 身份；文件名不含原文。默认缓存上限 128 MiB，按最近访问时间淘汰旧 WAV，当前音频保留。
- API 只返回 `playback_id`、安全状态、音频 URL 和引擎结果，不返回 Provider 原始输出、路径或命令行。
- `fake` 只用于隔离测试或显式 demo；真实 `sapi`、`edge-tts` 均须显式配置。默认 `tts_enabled=false`、provider 未配置，不会自动联网、不自动调用 SAPI。
- edge-tts 失败时只在明确允许 fallback 且本地 SAPI 已显式配置时降级；否则返回稳定 `tts_provider_unavailable`。

## 2. Skill 接口与调用边界

Skill 的领域接口是：

```text
TtsManager.speak(text, engine?, voice?, rate?)
  -> playback_id, audio_url, engine, fallback_used, duration_ms
TtsManager.control(playback_id, play|pause|stop, rate?)
  -> state, position_ms, duration_ms
TtsManager.status(playback_id)
  -> state, position_ms, duration_ms
TtsManager.capabilities()
  -> status, provider_id, voice, network_required, supports
```

HTTP 装配为：

| Endpoint | 用途 | 写入边界 |
| --- | --- | --- |
| `POST /api/tts/speak` | 校验文本并合成/命中缓存 | 仅写 tts-cache 和进程内会话 |
| `POST /api/tts/control` | 播放会话状态控制 | 仅写进程内会话 |
| `GET /api/tts/status/{id}` | 查询状态 | 只读 |
| `GET /api/tts/audio/{id}` | 读取 WAV | 只读，必须是当前会话对应的缓存文件 |
| `GET /api/tts/capabilities` | 显示能力状态 | 只读，不探测网络 |

文本限制为非空、最大 12,000 字符；速率限制在 `0.5–2.0`；播放 ID 为随机 opaque id。播放控制由浏览器 `HTMLAudioElement` 执行，服务端保存状态用于重试、状态查询和安全 URL 绑定；服务端不假装控制操作系统扬声器。

## 3. Provider、配置与能力发现

配置来源遵循现有环境配置边界：

| 配置 | 环境变量 | 默认值 |
| --- | --- | --- |
| 开关 | `STUDYBUDDY_TTS_ENABLED` | `0` |
| Provider | `STUDYBUDDY_TTS_PROVIDER` | 未配置 |
| voice | `STUDYBUDDY_TTS_VOICE` | Provider 默认 |
| SAPI executable | `STUDYBUDDY_TTS_SAPI_PATH` | 空，使用显式系统命令名 |
| edge-tts command | `STUDYBUDDY_TTS_EDGE_COMMAND` | 空，不能自动联网安装 |
| timeout | `STUDYBUDDY_TTS_TIMEOUT_SECONDS` | 30 秒 |

`GET /api/system/capabilities` 增加 `tts` 项。状态使用 `not_configured / configured / demo / disabled`，`configured` 只表示配置结构有效，不表示声音质量或真实 Provider 已通过。网络需求、fallback 和支持的引擎会公开，路径和密钥不会公开。

Provider 协议只有 `synthesize(text, output_path, voice, rate)`；缓存、播放会话、错误码和安全边界由 skill 管理。fake Provider 产生确定性的合法 WAV；SAPI 通过显式 PowerShell 命令写 WAV；edge-tts 通过显式 CLI 写 WAV，禁止下载或隐式安装。

## 4. 播放、暂停、重试与降级

状态机为 `playing → paused → playing`，`playing/paused → stopped`。新的 speak 会结束旧会话的前端播放并替换当前会话。浏览器播放失败或 API 失败显示固定文案和“重试”；重试复用同一文本，不重复发送隐藏内容。

edge-tts 请求失败时，只有本地 SAPI 明确 configured 且 fallback 允许时才重试 SAPI，并返回 `fallback_used=true`。Provider 错误只映射为稳定错误码：`tts_not_configured`、`tts_invalid_request`、`tts_provider_unavailable`、`tts_timeout`、`tts_audio_unavailable`，不携带命令路径、stderr、原始响应或密钥。

## 5. 学习材料装配

第一处正式入口是材料详情的知识模块工作区：每个有效知识模块显示“朗读模块”按钮，朗读标题和描述；来源正文仍由现有材料权限和引用链控制，TTS 不绕过材料 API，也不读取数据库原文。

共享 `tts.js` 在材料详情页提供播放、暂停、停止、重试、引擎显示和安全错误反馈。未来可将相同入口装配到 Today 卡片或练习解析，但不在本次扩大为全站任意文本朗读。

## 6. 测试与音频产物

- 单元：文本/速率校验、哈希缓存键不含原文、fake WAV 头和可读性、会话状态机、未知播放 ID、edge fallback、安全错误。
- API：默认关闭、fake 合成、缓存命中、control/status/audio、错误边界、无数据库写入、路径不泄漏。
- 浏览器：知识模块朗读按钮、音频 URL、暂停/停止/重试和失败状态；使用 fake Provider，不调用真实 SAPI/edge-tts。
- 产物：验证文件存在于隔离 data root 的 tts-cache、MIME 为 `audio/wav`、WAV 可由 Python `wave` 读取；不提交音频、数据库或测试输出。
- 结构门禁：source-size、JavaScript 语法、`git diff --check`、后端 focused/full、S1/S2 关联浏览器回归。

## 7. 真实 Provider 政策

本次默认不允许真实 Provider 执行。Fake Provider 只证明协议、缓存、API 和 UI 装配；它不能证明 SAPI 语音质量、edge-tts 网络可用性或真实设备播放。真实 SAPI/edge-tts 需要单独授权、显式配置、隔离 data root 和单独 evidence，完成后仍只能报告 scoped real-pass。

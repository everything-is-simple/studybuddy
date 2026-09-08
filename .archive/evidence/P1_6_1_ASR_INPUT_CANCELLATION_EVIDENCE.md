# P1-6-1 B1 ASR 输入集与可取消性验证证据

> 状态：`implemented / focused-pass / 2026-08-31`
>
> 本证据只覆盖 canonical `WhisperCliCaptureProvider` 的输入拒绝、受控 timeout/中断边界和临时目录清理。它不代表通用 ASR real-pass，也不代表已经提供 graceful cancel API。

## 1. 精确范围

- Formal adapter：`backend/app/providers/_capture.py:WhisperCliCaptureProvider`
- Provider identity：`whisper-cpp` / `ggml-large-v3-turbo`
- 输入：内存中的 `CaptureTranscriptionRequest`；测试 fixture 为非敏感合成 WAV bytes
- 环境：当前 Windows / Python 3.10 / local single-process；没有真实网络
- 运行命令：固定 executable、model path、temporary input path；原始音频内容不进入命令行
- 输出：TXT/SRT 解析、输出大小上限、稳定错误码；stdout/stderr 丢弃

## 2. 本次验证

| 场景 | 结果 | 结论 |
|---|---|---|
| 非 audio `asset_kind` | passed | 在运行时调用前返回 `transcription_failed` |
| 空 audio bytes | passed | 在运行时调用前返回 `transcription_failed` |
| 合成成功输出 | passed | 解析 bounded transcript，临时目录在返回前删除 |
| timeout/受控中断 | passed | `TimeoutExpired` 映射为 `provider_timeout`，partial output 和临时目录删除 |
| 输出超限 | passed | 映射为 `payload_too_large`，finally 清理保持有效 |
| 原始内容隐私 | passed | 音频 sentinel 不进入 subprocess command；stdout/stderr 使用 `DEVNULL` |
| 不存在 runtime/model | existing pass | 映射为 `provider_unavailable`，不创建临时目录 |

“取消/中断”在本切片中只表示 adapter timeout 触发的受控停止边界。当前没有独立的 graceful cancel token、API cancel endpoint 或子进程树级终止协议，因此这些内容继续为 `not_verified`。

## 3. 测试结果

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_formal_asr.py -q
7 passed, 1 skipped
```

新增的 P1-6-1 focused assertions 位于 `test_formal_asr.py`，覆盖：

- 输入类型/空输入在 subprocess 前拒绝；
- 成功后 temporary root 删除；
- timeout 后 partial output 与 temporary root 删除；
- 音频内容不进入命令参数；
- timeout、stdout/stderr、bounded timeout 参数契约。

既有 `1 skipped` 为显式 opt-in 的真实 ASR smoke，未在本切片默认执行。

## 4. 未验证与边界

- 未执行真实 ASR runtime 或真实用户音频；
- 未扩大语言、音频格式、模型版本、Windows 以外 OS、CPU/GPU、容量或并发声明；
- 未证明可靠取消、Windows 子进程树强制终止、硬终止后的数据恢复或资源回收；
- 未新增后台 worker、task runner 接入、cancel API、schema、migration 或 API endpoint；
- 不把 `provider_timeout` 解释为完整 cancellation success；
- B2 OCR、B3 reports、B4 delivery 不在本切片范围，B4 继续 `delivery=off`。

## 5. 变更与安全检查

本切片只增加 ASR focused tests 和本 evidence；没有修改 `backend/app/`。原始音频、真实路径、Provider key、SMTP password、webhook、raw response 不进入仓库或 evidence。下一步应在独立切片中决定是否进行 B2 输入集/失败恢复验证，或另行冻结 ASR graceful cancellation 的实现契约。

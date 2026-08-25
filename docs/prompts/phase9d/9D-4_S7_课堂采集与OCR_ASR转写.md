# 9D-4 S7 课堂采集与 OCR/ASR 转写

```text
执行 Phase 9D-4：在共享 domain 层上完成 S7 ClassCapture 采集与转写 backend 闭环，不实现转写接入 S2（9D-5）、S6 报告、API 收口或 UI。

使用 ../00_COMMON_CONTEXT.md、9D-1 契约、9D-2 schema、9D-3 domain。实现显式 capture session：创建/读取/列表、上传课堂录音/图片作为敏感原件并纳入既有 hash-derived originals/material lifecycle、触发 OCR/ASR 转写、产出带置信度和 uncertain 标注的转写文本、读取转写结果。

必须遵守：
- 默认使用 deterministic fake/loopback OCR/ASR provider，保证可重复；真实 OCR/ASR 只在显式 gate 下接入，不得默认启用，也不得把 opt-in 真实结果宣称为通用 real-pass；
- 转写 operation 复用 ai_operations/provider registry 与幂等模式；raw request/response 不持久化，只保留转写文本、置信度、operation 元数据和可验证来源；
- 失败、超时、乱码、低置信/uncertain 有稳定处理：uncertain 内容要求用户核对，AI 不作最终裁决，不静默丢弃；
- 原件走 originals/material lifecycle，delete/purge 后转写读取路径安全降级，不伪造正文或路径；
- 普通响应和日志不得暴露原件路径、raw provider response、secret。

新增 focused backend tests（如 test_phase9d_capture.py），覆盖 session 生命周期、fake OCR/ASR 转写、置信度/uncertain、失败/超时、幂等/重复、隐私、rollback 和原件 lifecycle 读路径。运行 focused、相关 regression 和完整 backend，用 C:\\miniconda\\py310\\python.exe -m pytest 报告数字。

只允许修改 repository/domain/provider 适配与对应测试；不实现 9D-5 接入 S2、S6 报告/交付、API 或 Chromium。验收：采集/转写生命周期、置信度语义、失败边界、隐私和 lifecycle 读路径通过。状态为 implemented/backend-pass，不代表 9D-5、S6、API/UI、lifecycle/restore gates 或 Phase 9D completed。
```

# 9D-8 API contract

```text
执行 Phase 9D-8：实现 S6/S7 最小安全 FastAPI API，不实现 Chromium workspace 或 Phase 9D 收口。

使用 ../00_COMMON_CONTEXT.md、9D-1 契约与已完成的 domain 层（9D-3 至 9D-7）。在 backend/app/main.py 暴露最小 API：S7 capture session 创建/读取/列表、原件上传、转写触发与结果读取、转写接入 S2 的 confirm/reject/archive；S6 报告生成/读取/列表/预览/导出、交付触发（默认 dry-run）与交付审计读取。服务端注入 project scope 与 owner，复用 domain contract，不在路由层重复业务规则。

必须遵守：
- 稳定错误 contract（如 400/401-或-403/404/409/422/500），错误体不泄露路径、SQL、traceback、原始异常、secret、provider raw response、answer key 或原文全文；
- Idempotency-Key 处理与重复请求安全 replay；输入大小/类型/分页边界；
- 隐私：报告与交付相关响应严格遵守脱敏白名单；转写响应不含 raw provider response 或原件路径；交付默认走 dry-run，真实发送需显式授权且默认关闭；
- source deleted/purged/stale/unavailable 时 API 安全降级，不伪造正文/路径/citation；
- 不新增未走 domain/migration 的旁路写入。

新增 focused backend tests（如 test_phase9d_api.py），覆盖 S7/S6 各资源的成功路径、scope、稳定错误、幂等、隐私边界、交付默认关闭与授权、source lifecycle 读路径。运行 focused、相关 regression 和完整 backend，用 C:\\miniconda\\py310\\python.exe -m pytest 报告数字。

只允许修改 main.py 路由/请求响应模型与对应测试；不实现前端或收口文档。验收：安全 HTTP contract、隐私、幂等、交付默认关闭和错误映射通过。状态为 implemented/backend-pass，不代表 browser-pass、lifecycle/restore gates 或 Phase 9D completed。
```

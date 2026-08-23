# 9A-4：API contract

> 先使用 `00_COMMON_CONTEXT.md` 作为前置 prompt，再使用本文件。


```text
执行 Phase 9A-4：把已通过 repository/domain 测试的 9A 能力暴露为最小 FastAPI API，不扩展业务范围，不实现完整 UI。

先读取当前 main.py 的路由风格、错误响应、safe serialization 和输入边界测试。按 contract 实现最小 goal/module/plan/item/dependency/progress/source link API：创建/列表/详情、draft edit、confirm/activate、item add/edit/reorder/remove、dependency add/remove、progress event append、summary、source status。明确哪些动作不做，例如提醒、调度、自动重排、复杂 AI re-plan、9B/9C/9D 能力。

每条 API 必须定义 method/path、request/response、status、stable error code、active/deleted/purged 边界、重复请求语义、malformed JSON/ID/date/status 行为、隐私边界。不要返回路径、SQL、traceback、raw provider data、完整 source text 或未授权的 citation quote。保持现有 request ID、observability 和 safe failure contract。

新增 API boundary tests，覆盖 4xx/409/404/422/500 安全错误、非法依赖和状态转移、重复 progress、source unavailable、失败后 retry、响应字段隐私。涉及 API 必须运行完整 backend suite。

验收：API contract 与 repository 行为一致；失败响应稳定脱敏；没有为 UI 方便而泄露内部字段。
```
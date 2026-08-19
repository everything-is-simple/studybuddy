# StudyBuddy Architecture Boundary

当前只定义目录边界，不代表功能已经实现。

## Runtime target

`127.0.0.1` 本机 Web 应用：React/Vite 前端 + FastAPI 后端 + SQLite + 本地文件。AI 通过当前选中的单一 OpenAI-compatible provider 直接请求。不引入 pi、Electron、自动 fallback 或多进程 AgentSession。

## Evidence flow

```text
参考系统/组件
  -> H:\studybuddy-composer 独立 smoke
  -> H:\studybuddy-integration 组合测试
  -> H:\studybuddy 正式 Adapter 与用户路径
```

系统测试运行根统一位于 `H:\studybuddy-test`。任何目录的测试通过，都不能替代下一层真实测试。

## Non-goals for the first assembly

不预装所有 S1-S7，不预先接入 OCR、ASR、WPS、SMTP、飞书，不创建空 handler 或 mock 成功路径。每一项能力在真实组件可运行后再装配。

# A0 静态/前端现状与契约

## 现状结论

当前不存在 FastAPI `StaticFiles` mount，也不存在正式 static root。`backend/app/main.py` 只注册：

```python
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML
```

`INDEX_HTML` 从约第 2,979 行开始，以 Python triple-quoted string 内嵌完整 HTML、CSS 和 JavaScript，文件总长约 3,184 行。不能在 A0 凭空创建 `backend/app/<static root>/`，也不能把 `/` 改为 `FileResponse`。

## 页面行为冻结

入口 `/` 返回中文单页工作区，浏览器测试均以 `/` 为入口。当前页面包含：

- 材料导入：单文件、多文件、`webkitdirectory` 文件夹导入、逐项结果、部分成功、busy/失败恢复；
- 材料列表：正常/回收站、状态过滤、搜索、分页、详情、纯文本 snippet/高亮；
- 材料管理：重命名、软删、恢复、永久删除、原文件下载、正文导出、批量 original/text/bundle ZIP；
- Provider 状态与 AI capabilities；
- retrieval lexical/vector/hybrid、显式索引、Q&A threads、citation detail/location、失败重试/idempotency；
- Cards/Exercises、Plans/Goals/Modules/Progress/Rhythm、Notes/knowledge modules；
- S3 practice、mistakes/feedback/redo、S5 cram；
- S7 capture/transcript/edit/confirm/reject/archive；
- S6 report preview/export/delivery audit；
- URL query navigation：`material`、`thread`、`scope`、`citation`，并保留键盘/窄屏/焦点/ARIA/failure 行为。

动态文本使用安全 DOM text nodes；页面不得显示 backend detail、路径、SQL、traceback、raw provider error、secret 或不必要正文。

## 允许的未来演化

A3 才能将 HTML/CSS/JS 移出 `main.py`。迁移必须先逐字/等行为复制，再用相同 `/` 响应和 Playwright 验收替换；页面 URL、DOM 可访问名称、关键 id/class、接口 payload 和错误提示不得无计划改变。正式 static root 的命名必须在 A3 前通过实现方案冻结；建议结构只是目标草案，当前不是事实：

```text
backend/app/<formal-static-root>/
├── index.html
├── materials.html
├── material-detail.html
├── qa.html
├── capture.html
├── settings-provider.html
├── css/
└── js/
```

拆出多页不是 A0/A1/A2 的附带工作。Provider 设置页、采集页属于 A4；ASR/OCR 属于 B1/B2。

## 测试入口

- runner：`backend/scripts/test-browser.ps1`；
- package script：`npm run test:browser`（Playwright `1.62.1`）；
- runner 固定 serial：`--workers=1 --reporter=line`；
- specs：见 `A0_BASELINE_AUDIT.md`，当前共 18 个、53 tests；
- 每个 spec 通常从 `H:\studybuddy\backend` 启动 `C:\miniconda\py310\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port <独立端口>`，并设置 `PYTHONPATH=H:\studybuddy\backend` 与隔离 `STUDYBUDDY_DATA_ROOT`；
- 本次 browser 执行被本机缺少 Chromium executable 阻塞，必须标记 `not_verified`，不能生成 browser-pass 证据。

# StudyBuddy Architecture Boundary

## Runtime target

`127.0.0.1` 本机 Web 应用：React/Vite 前端 + FastAPI 后端 + SQLite + 本地文件。AI 通过当前选中的单一 OpenAI-compatible provider 直接请求。不引入 pi、Electron、自动 fallback 或多进程 AgentSession。

## Evidence flow

参考系统/组件 -> `H:\studybuddy-composer` 独立 smoke -> `H:\studybuddy-integration` 组合测试 -> `H:\studybuddy` 正式 Adapter 与用户路径。

系统测试运行根统一位于 `H:\studybuddy-test`。任何目录的测试通过，都不能替代下一层真实测试。

## Formal file foundation

`backend/app/adapters/file_parsers/` 是正式系统自己的解析模块，不导入 Composer、Integration 或 KaoBuddy。`parse_file(Path, declared_media_type, ParseOptions)` 返回版本、hash、状态、错误码、warning 和 document/page/slide spans。当前只实现 TXT、Markdown、PDF、DOCX、PPTX；RTF、旧 DOC、旧 PPT 拒绝。Parser 不保存原文件、不依赖网络、不打印完整正文。

`backend/app/storage.py` 通过配置传入的 root 保存 hash 派生路径下的原文件，并使用临时文件加原子替换。`backend/app/repository.py` 只承载 projects/materials/extractions/text_spans 最小 schema，启用外键和 WAL，extraction 与 spans 在同一事务中写入。

正式默认运行路径不指向 fixture；本阶段测试使用 `H:\studybuddy-test\runs`。尚未实现用户上传、页面展示、关闭重启回读、OCR、旧格式转换、provider 或 S1-S7。

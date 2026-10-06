# S2 资料笔记 / 知识模块（NoteBuilder）

> 状态以 [capabilities.json](../capabilities.json) 中 id=S2 为准；本文不写测试通过数。

原始意图参考 [S2 NoteBuilder PRD](../archive/legacy-product-references/ai-studybuddy/subsystems/03-S2-资料笔记子系统PRD-NoteBuilder.md)；AI 管线见 [AI_LEARNING_ARCHITECTURE](../03-ARCHITECTURE.md#5-ai-边界)。

## 1. 目标

学生手里的 PDF、图片、文本资料不能直接拿来练习和复习。S2 把资料导入、解析、分块索引，再抽取带来源证据的知识模块，学生确认后才成为事实。知识模块是资料、练习、错题、冲刺之间的共同语言；解析失败和待确认草稿会回流到 Today 的"待核对"。

## 2. 用户流程

1. 在 `materials.html` 上传单个或批量资料；可删除、恢复、导出。
2. 打开 `material-detail.html`，查看原件、解析正文和解析状态；解析失败时按提示修复后重新导入。
3. 对材料建立 AI 索引（同步或后台任务），在"知识"页签点击抽取，得到 AI 草稿模块。
4. 逐个核对草稿的来源片段，修改标题、描述、重要性、难度、标签，然后"确认模块"或"拒绝草稿"；也可手工从片段创建模块（直接为已确认）。
5. 在 `notes.html` / `note-detail.html` 生成或手写笔记，绑定知识模块和来源片段，确认、归档或导出。
6. 已确认且来源有效的模块出现在 `exercises.html` 的模块选择中，进入 S3。

## 3. 数据对象

| 表 | 关键字段 | 状态 |
|---|---|---|
| `materials` | original_name, stored_path, deleted_at | 软删除 / 恢复 / purge |
| `material_revisions` | material_id, parser_id, is_current | 当前修订 |
| `extractions` | material_id, parser_id, status, text | 最新一条为 `failed / rejected / empty` 时进入 Today |
| `text_spans` `chunks` `chunk_spans` | 文本片段与检索分块 | chunk `ready` 才可用于抽取 |
| `knowledge_modules` | title, description | `active / archived` |
| `s2_knowledge_modules` | material_id, source_evidence(JSON), importance 1–5, difficulty 1–5, estimated_minutes, tags, provenance, provider_id, model_id, deleted_at | lifecycle `draft → confirmed / rejected` |
| `module_source_links` | module_id, revision_id, chunk_id | `valid / source_deleted / source_unavailable / stale` |
| `s2_module_exercises` | module_id, exercise_id | 模块与题目关联，用于计算掌握度 |
| `notes` | title, provenance, user_edited | `draft / confirmed / rejected / archived` |
| `note_blocks` `note_module_links` `note_block_source_links` | block_kind `text/heading/bullet`；来源链接 | 来源状态同上 |

派生字段（不落库）：`source_status`、`mastery_level`（由关联题目作答计算，答对 +0.1×(1−level)，答错 ×0.8）、`learn_status`（`not_started / in_progress / mastered / needs_review`）。

## 4. 页面与 API

页面：`materials.html`、`material-detail.html`、`notes.html`、`note-detail.html`。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/materials`，POST `/api/materials/batch` | 列表 / 上传 / 批量上传 |
| GET/PATCH | `/api/materials/{material_id}` | 详情 / 修改 |
| GET | `/api/materials/{material_id}/original` `text` | 原件、解析正文 |
| DELETE | `/api/materials/{material_id}`；POST `.../restore` `.../purge` | 软删除、恢复、彻底清除 |
| GET | `/api/materials/deleted`；POST `/api/materials/export` | 回收站、导出 |
| POST/GET | `/api/materials/{material_id}/ai-index`，POST `.../ai-index/tasks` | 建索引 / 后台任务 |
| GET | `/api/knowledge-modules`、`/api/knowledge-modules/sources` | 模块列表（lifecycle/status 过滤）、可选来源块 |
| POST | `/api/knowledge-modules` | 手工创建（confirmed） |
| POST | `/api/knowledge-modules/extract` | AI 抽取草稿（draft） |
| GET/PATCH/DELETE | `/api/knowledge-modules/{module_id}` | 详情 / 修改 / 删除 |
| POST | `/api/knowledge-modules/{module_id}/confirm` `reject` | 确认 / 拒绝草稿 |
| GET | `/api/knowledge-modules/{module_id}/practice-history` | 模块作答历史 |
| GET/POST | `/api/study/notes`，POST `/api/study/notes/generate` | 笔记列表、创建、AI 生成 |
| GET/PATCH | `/api/study/notes/{note_id}`，GET `.../export` | 详情、修改、导出 |
| POST/PUT/PATCH/DELETE | `/api/study/notes/{note_id}/blocks[/{block_id}]` | 笔记块编辑 |
| POST | `/api/study/notes/{note_id}/confirm` `reject` `archive` | 笔记状态 |
| POST/DELETE | `/api/study/notes/{note_id}/modules/{module_id}`、`.../blocks/{block_id}/sources[/{link_id}]` | 绑定模块与来源 |
| POST | `/api/study/notes/sources/refresh` | 刷新来源状态 |

## 5. 规则与 AI 边界

- 规则：格式转换、解析、分块、来源状态、掌握度计算、去重都不用 LLM。
- AI 只起草：抽取模块需引用当前上下文中的 citation key，结构不合法整体拒收（`knowledge_generation_invalid`）；AI 结果一律 `lifecycle=draft`。
- 学生确认：只有 draft 可确认或拒绝；来源无效时不能确认；已拒绝的模块不能再编辑。
- 来源消失时保留模块和作答历史，`source_status` 降级，练习入口不再提供该模块。
- Provider 默认关闭；未配置时抽取和笔记生成返回明确错误，不阻塞手工建模块。
- 家长不看资料原文、笔记正文或模块内容。

## 6. 验收标准

- 上传后能在详情页看到解析正文；解析失败时 Today 出现"解析待处理 / 格式待处理 / 正文待核对"并链接到该材料。
- AI 抽取后，Today 出现"知识草稿待确认：<资料名>"及草稿数；全部确认或拒绝后该项消失。
- 每个模块能看到来源片段；删除来源材料后模块显示来源失效，不可再确认或练习。
- 确认的模块出现在练习页模块选择中；作答后模块显示掌握度变化。
- 笔记可编辑、绑定来源、导出；AI 生成的笔记先是草稿。

## 7. 已知缺口

- 真实 Provider 抽取质量未验证。
- 存在两套"模块"接口：`/api/study/modules`（S1 计划用，canonical `knowledge_modules`）与 `/api/knowledge-modules`（S2 元数据），页面分别使用，概念需统一说明。

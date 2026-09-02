# P1-3 Cards/Exercises Migration Status

## 目标
将 Cards 和 Exercises 的写操作和复习路径从旧的 `/legacy` 迁移到新的 `/app`。

## 已完成

### 后端 API (✅ 完成)
- ✅ `GET /api/study/decks` - 列出卡片组
- ✅ `GET /api/study/decks/{deck_id}` - 获取单个卡片组
- ✅ `POST /api/study/decks` - 创建卡片组
- ✅ `GET /api/study/cards` - 列出卡片（支持 `deck_id` 查询参数）
- ✅ `GET /api/study/cards/{card_id}` - 获取单个卡片
- ✅ `POST /api/study/decks/{deck_id}/cards` - 创建卡片
- ✅ `PATCH /api/study/cards/{card_id}` - 更新卡片
- ✅ `POST /api/study/cards/{card_id}/confirm` - 确认卡片
- ✅ `POST /api/study/cards/{card_id}/reject` - 拒绝卡片
- ✅ `POST /api/study/cards/{card_id}/archive` - 归档卡片
- ✅ `POST /api/study/cards/{card_id}/reviews` - 记录复习
- ✅ `GET /api/study/exercise-sets` - 列出练习集
- ✅ `GET /api/study/exercise-sets/{set_id}` - 获取单个练习集
- ✅ `POST /api/study/exercise-sets` - 创建练习集
- ✅ `GET /api/study/exercises` - 列出练习题（支持 `set_id` 查询参数）
- ✅ `GET /api/study/exercises/{exercise_id}` - 获取单个练习题
- ✅ `POST /api/study/exercise-sets/{set_id}/exercises` - 创建练习题
- ✅ `PATCH /api/study/exercises/{exercise_id}` - 更新练习题
- ✅ `POST /api/study/exercises/{exercise_id}/confirm` - 确认练习题
- ✅ `POST /api/study/exercises/{exercise_id}/reject` - 拒绝练习题
- ✅ `POST /api/study/exercises/{exercise_id}/archive` - 归档练习题
- ✅ `POST /api/study/exercises/{exercise_id}/attempts` - 提交练习尝试

### 后端仓库函数 (✅ 完成)
- ✅ `get_card(connection, project_id, card_id)` - 添加到 `_legacy_part_01.py`
- ✅ `get_exercise(connection, project_id, exercise_id)` - 添加到 `_legacy_part_03.py`

### 前端页面 (✅ real-pass)
- ✅ `/app/cards.html` - 卡片管理页面（基础功能）
- ✅ `/app/exercises.html` - 练习题管理页面（基础功能）
- ⚠️ 前端 API 调用路径已修正：
  - `GET /api/study/cards?deck_id={id}` (修正自 `/api/study/decks/{id}/cards`)
  - `GET /api/study/exercises?set_id={id}` (修正自 `/api/study/exercise-sets/{id}/exercises`)
- ⚠️ 创建请求已添加必需字段：
  - 卡片：`card_type`, `tags`, `explanation`, `citations`
  - 练习题：`explanation`, `citations`, `exercise_kind`

### 测试 (✅ real-pass)
- ✅ 后端完整测试：468 passed, 3 skipped
- ✅ P1-3 浏览器验收：3 passed
  - ✅ Cards：创建→详情→编辑→确认→复习
  - ✅ Exercises：创建→详情→编辑，且不暴露 answer key
  - ✅ Review：用户可见来源状态与再次练习操作
- ✅ 前端契约审计：0 findings
- ✅ source-size check：通过

## 验收结论

P1-3 已完成 real-pass：Cards、Exercises 和 Review 的 `/app` 核心用户路径均通过隔离数据目录的真实浏览器测试。写操作使用共享 API 请求层，状态和来源显示使用共享映射，页面不暴露 answer key、路径、SQL 或 traceback。

## 后续边界

- AI 生成草稿的真实 Provider 验收仍受既有 Provider/材料索引门槛约束；本次仅验证页面请求契约和用户创建路径。
- 批量操作、高级筛选和排序不在 P1-3 范围内。

## 收尾验证

- P1-3 浏览器验收：3 passed
- 后端完整测试：468 passed, 3 skipped
- 前端契约审计：0 findings
- source-size check：passed

## 全量回归说明

P1-3 定向验收及相关状态矩阵验证均通过（6 passed）。随后完成完整 Chromium 回归：`144 passed, 4 skipped`，无失败；skip 均为默认关闭的 opt-in 真实 smoke。

## 技术债务
- `backend/app/static/cards.html` 和 `exercises.html` 的 JavaScript 应该提取到独立文件
- 错误消息应该更具体，而不是通用的"请求失败，请重试"
- 需要更好的前端状态管理，避免复杂的嵌套回调

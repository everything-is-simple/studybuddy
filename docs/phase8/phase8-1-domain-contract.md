# Phase 8.1 领域契约记录（工作中）

> 这是 Phase 8 中间记录，最终结论必须吸收到正式状态/架构文档；Phase 8 完成后随 `docs/phase8/` 删除。

## Migration

- 当前 schema：v7
- migration：`phase8_cards_exercises_schema`
- 新增业务表：`study_decks`、`study_cards`、`card_citations`、`card_reviews`、`exercise_sets`、`exercises`、`exercise_citations`、`exercise_attempts`
- 新表只由 migration 创建；业务运行时不得建表。
- backup/restore 通过 SQLite database snapshot 自动覆盖这些表，不执行生成、repair 或 rebuild。

## 生命周期

- deck/set：`active → archived`
- card/exercise：`draft → ready | rejected | stale | archived`
- AI 生成产物使用 `card_type=ai_generated` 或对应 generation operation，并从 draft 开始。
- 用户创建内容使用 `user_created`，不能伪造 AI citation。
- `edited_by_user=1` 后生成流程不能覆盖现有 artifact；后续实现应创建新 draft 或拒绝覆盖。

## Source / citation

- `source_revision` 绑定 material revision；citation 记录 material/revision/extraction/chunk/span 和有界 quote。
- citation 状态：`valid`、`source_deleted`、`source_unavailable`、`stale`、`invalid`。
- 删除、purge、revision supersede 不得伪造历史来源；历史 artifact 可以保留，但不可用来源必须显式表达。

## History / grading

- `card_reviews` 和 `exercise_attempts` 是 append-only 历史。
- exercise 首批类型：`multiple_choice`、`true_false`、`short_answer`。
- `multiple_choice` / `true_false` 由 repository deterministic grading；`short_answer` 使用 `pending_review` / `needs_review` 等不确定状态。
- `answer_key_json` 是内部数据，普通列表和非授权响应不得返回。

## 尚未实现

本记录只冻结 schema 和领域边界。Repository、API、生成、UI、review/attempt 行为仍由 Phase 8.2–8.6 分步实现；不能把 migration 存在写成 Cards/Exercises 已完成。

# Phase 8.3：Exercises Repository / API / Deterministic Grading Prompt

## 目标
实现 Exercise MVP：exercise set、题目类型、严格 schema、draft/ready 生命周期、citation、attempt 历史和确定性评分。

## 任务
1. 实现 exercise set 创建/列表/详情；exercise 创建、编辑、确认、拒绝、归档。
2. 首批类型只做 `multiple_choice`、`true_false`、`short_answer`；不要无证据扩展 cloze/ordering。
3. 对题干、选项、正确答案、解释、题型和 payload 做严格 schema/大小/数量校验；非法 payload 使用稳定 `invalid_exercise_schema`。
4. AI 生成默认 draft，确认时重新验证 citation、source binding、状态和内容版本。
5. 实现 `exercise_citations`，复用 citation key 验证和 source lifecycle；invalid/deleted/purged/stale source 不得伪造 ready 来源。
6. 实现 `exercise_attempts` append-only：提交答案、评分、grading_status、时间和必要 metadata；不得修改旧 attempt。
7. multiple choice / true_false 使用 deterministic grading，统一记录正确答案、得分和结果，但 answer key 不进入普通列表响应。
8. short_answer 只能返回 pending_review/needs_review 等不确定状态；不得声称 deterministic truth；允许人工确认路径或明确留作后续。
9. 覆盖重复提交、非法状态跃迁、编辑/确认保护、material lifecycle、transaction rollback 和安全错误。

## 验收
backend tests 必须证明正确/错误答案、边界答案、选项重复/缺失、answer-key privacy、attempt 历史和 restart/backup 后恢复。未实现的 grading 能力必须明确 not_implemented，不得返回假成功。

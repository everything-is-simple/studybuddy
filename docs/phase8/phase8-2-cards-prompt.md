# Phase 8.2：Cards Repository / API / Lifecycle Prompt

## 目标
实现可独立验收的 Card MVP：deck/card CRUD、draft → ready 确认、编辑保护、citation 绑定与 review 历史。

## 前置
先完成并验证 8.1 migration/契约。复用现有 repository 事务、project/material lifecycle、citation validation、observability 和安全错误边界。不得复制历史项目实现。

## 任务
1. 实现 deck 创建/列表/详情/归档或安全删除；card 创建、列表、详情、编辑、确认、拒绝、归档。
2. card schema 严格校验 front/back/explanation/tags 等字段，限制长度、数量和 JSON 大小。
3. AI card 永远从 draft 开始；确认时重新验证 citation、source revision、状态和 payload。
4. 实现 `card_citations`，保存可验证的 material/revision/chunk/span 定位和有界 quote；citation 无效不得 ready。
5. 用户编辑后设置明确 edited 状态或 version 语义；重新生成必须新建 draft 或明确拒绝，绝不覆盖 user-edited/confirmed card。
6. material delete/restore/purge、revision supersede 后更新 citation 可用性，不删除用户 card 历史，不伪造来源。
7. 实现 `card_reviews` 追加写入，记录 review result/time/metadata；历史不可覆盖。
8. 增加 API 输入边界、稳定错误码、request ID、safe response 和事务 rollback。

## API 方向
具体路径以现有风格冻结，但至少覆盖 deck/card 列表、详情、编辑、confirm、reject/archive、review；普通列表不返回不必要 source quote 或内部路径。

## 验收
backend tests 覆盖 CRUD、状态机、citation、编辑保护、source lifecycle、review append-only、重复操作和失败重试。必要时补 browser contract，但完整路径留给 8.5。

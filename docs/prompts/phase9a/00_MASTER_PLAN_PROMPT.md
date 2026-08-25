# Phase 9A 总规划 Prompt


```text
请为 StudyBuddy 规划 Phase 9A“学习领域基础与计划核心”，不要修改任何文件。

先完整审计当前源码和权威文档，确认当前 migration version、repository 事务、material revision/citation lifecycle、Phase 8 source lifecycle、backup/restore、main.py 路由和现有 Chromium workspace。然后输出一份可直接转化为 TODO、migration、测试和逐 commit 实施计划的中文规划。

Phase 9A 最小对象：learning goal、knowledge module、study plan、study plan item、dependency、append-only progress event、progress summary、source revision/citation link。必须重新基于当前 StudyBuddy contract 设计，不得直接复制历史 KnowledgeModule。

必须明确：goal/module/plan/item 的关系；plan 是否必须绑定 goal；module 是否可复用；item 是否允许无 source；citation 绑定层级；dependency 是否只允许同一 plan；DAG/cycle 规则；draft→confirm→active 规则；pause/archive/complete 是否纳入；progress event 与 summary 重算；delete/restore/purge/re-index/source unavailable/stale 行为；AI draft 是否纳入 9A；用户编辑/确认/完成保护；日期与 timezone；project/user 边界；backup/restore non-repair。

请将 9A 拆成 9A-0 至 9A-8 的独立子任务，每个任务给出目标、前置、源码范围、测试、验收标准、风险、独立提交性和阻塞关系。至少覆盖：现状审计、领域契约、migration、repository/domain、API、最小 UI、source lifecycle、backup/restore、全量验收与文档收口。

明确排除 9B/9C/9D/Phase 10，并给出最终允许使用的状态措辞。输出只做规划，不实现。
```

---
# 9A-6：Source lifecycle 集成

> 先使用 `00_COMMON_CONTEXT.md` 作为前置 prompt，再使用本文件。


```text
执行 Phase 9A-6：单独完成 9A 计划对象与材料 source lifecycle 的集成，不新增不必要的 AI 功能。

覆盖 material delete、restore、purge、新 extraction/new revision、chunk re-index 后的 plan/module/item source link 状态。明确 valid、source_deleted、source_unavailable、stale 的映射和返回 contract。已完成 item 的历史记录必须保留；purge 不得恢复名称、正文或可点击 source。恢复后是否自动 valid 必须遵守 contract，不能通过启动或读取自动 repair；如需 refresh，必须是显式动作。

测试 active plan 在 source unavailable 时的行为：是允许 active 并显示 warning，还是禁止 activate；对已完成、未开始、编辑中 item 分别验证。验证 delete/restore/purge/re-index 不会删除 progress event、不复制正文、不自动解析、不自动调用 Provider。

新增/修改 source lifecycle backend 和 Chromium tests，并运行完整 backend + Phase 9A browser tests。更新 domain contract/evidence 草案，但只有 closeout 才更新 completed 状态。

验收：source 状态不会被伪造提升；历史 progress 和 plan artifact 保留；UI/API 状态一致。
```
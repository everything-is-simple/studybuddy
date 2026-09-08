# Phase F 执行计划 - Legacy Repository 层注释

## 背景调整

原决策为"Legacy 代码等待重构后再注释"。用户于 2025-01-18 明确指示开始 Phase F。
策略调整为：**现在完成模块级 docstring（领域职责 + 函数分组 + 依赖说明），
函数级详细注释随重构时补充**——与 Phase B 代理文件的注释深度一致。

## 文件清单与领域映射（20 文件，6,924 行）

| 文件 | 行数 | 领域 |
|------|------|------|
| _legacy.py | 473 | 兼容桥接：装配 18 个 part 的公共/私有绑定 |
| _legacy_runtime.py | 24 | 共享运行时导入（所有 part 的唯一入口） |
| _legacy_part_00.py | 421 | 检索策略常量 + FTS 搜索索引维护 |
| _legacy_part_01.py | 369 | 材料导入/列表/卡片 CRUD/生成操作 |
| _legacy_part_02.py | 421 | 卡片确认/复习/练习集/生成操作 |
| _legacy_part_03.py | 328 | 练习管理 + Phase 9C 基础工具 + 尝试 |
| _legacy_part_04.py | 308 | 冲刺目标/练习会话/错题实例化 |
| _legacy_part_05.py | 428 | 错题本/弱点分析/采集会话创建 |
| _legacy_part_06.py | 337 | 采集资产/转录操作 |
| _legacy_part_07.py | 381 | 转录完成/确认/报告周期工具 |
| _legacy_part_08.py | 388 | 报告投影/快照/交付尝试 |
| _legacy_part_09.py | 393 | 学习目标/模块/计划 CRUD/进度摘要 |
| _legacy_part_10.py | 362 | 计划项目/依赖 DAG/源链接刷新 |
| _legacy_part_11.py | 418 | 源候选/节奏设置分配/周趋势/笔记创建 |
| _legacy_part_12.py | 327 | 笔记管理/块/链接/确认 |
| _legacy_part_13.py | 324 | 笔记生成操作/材料状态/分块 |
| _legacy_part_14.py | 378 | 材料清理/软删除/修订指纹/索引/QA线程 |
| _legacy_part_15.py | 370 | 后台任务视图/嵌入索引操作 |
| _legacy_part_16.py | 288 | 检索执行（混合/向量/分块） |
| _legacy_part_17.py | 362 | QA 幂等/引用键/上下文装配 |

## 批次计划（5 批）

- **F1**（基础+检索）: _legacy.py, _legacy_runtime.py, part_00, part_01, part_02
- **F2**（练习/采集）: part_03, part_04, part_05, part_06
- **F3**（报告/学习计划）: part_07, part_08, part_09, part_10
- **F4**（节奏笔记/修订）: part_11, part_12, part_13, part_14
- **F5**（任务/QA）: part_15, part_16, part_17

每批完成后：导入验证 + 提交推送。

## 架构要点（写入各 docstring）

1. **装配机制**: _legacy.py 启动时把所有 part 的符号互相注入
   （`setdefault` 交叉绑定），part 之间不 import 桥接模块
2. **运行时**: 所有 part 以 `from ._legacy_runtime import *` 获取
   标准库和项目依赖，避免重复导入
3. **边界**: 这些文件是待重构的旧实现；新代码走 repositories/*.py 代理
4. **指纹分隔符**: part_14 的指纹公式使用四字符字面量 `\x1f`（非 0x1F），
   与 migrations/_v14 必须保持一致

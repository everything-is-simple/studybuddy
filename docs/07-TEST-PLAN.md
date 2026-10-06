# 07 · 验收计划

> 单个子系统的验收标准写在各自文档 §6。本文只写跨子系统的主路径验收，以及证据放在哪里。

## 1. P0 主闭环验收

在空的隔离 data_root 上，一步一步做，并检查 Today：

| 步骤 | 学生动作 | 持久化事实 | Today 应出现 |
|---|---|---|---|
| 1 | 建计划并激活，设节奏 | `study_plans` active、`study_plan_items` | 计划有未排日程项时：提示去安排；排了今天的：`due_task` |
| 2 | 导入资料，抽取知识模块 | `materials`、`s2_knowledge_modules` draft | `quality_check`：待确认模块 |
| 3 | 确认模块 | lifecycle=confirmed | `next_step`：练这个模块 |
| 4 | 按模块生成并确认题目，开始练习，答错一题 | `practice_sessions`、`mistake_cases` open | `mistake_review` |
| 5 | 重做错题并答对 | `mistake_cases` fixed | `mistake_review` 消失 |
| 6 | 建冲刺目标（N 天后） | `cram_goals` active | 冲刺倒计时项 |
| 7 | 完成冲刺练习 | 计划项进度事件 | 回到新的下一项 |

自动化：`backend/tests/test_p0_main_loop.py` 按上表逐跳断言 Today 的输出。手工可视验收另写证据。

## 2. 证据存放

```text
H:\studybuddy-test\verification\<主题>-<YYYYMMDD>\
  acceptance.md     做了什么、命令、结果、未验证范围
  *.log             原始测试输出（脱敏）
```

证据目录不进 Git。`capabilities.json` 的 `evidence` 字段引用这里的文件。

## 3. 尚未覆盖（NOT_VERIFIED）

- 正式 data_root 上的 real-pass。
- 真实 Provider 内容质量、真实 OCR/ASR、SAPI/edge-tts、真实邮件/飞书外发。
- 可视浏览器人工验收、跨浏览器、屏幕阅读器、真实扬声器。

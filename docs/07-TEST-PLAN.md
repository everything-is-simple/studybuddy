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

## 3. Windows 与真实组件验收

- S6/S7 分别执行相关后端与浏览器用户路径，检查报告脱敏、外发默认关闭、转写草稿确认和来源绑定。
- TTS：显式选择真实引擎，核对音频接口、音频时长及设备播放返回；听感需使用者确认。
- OCR/ASR：使用已知内容的 synthetic 输入，核对有意义文本，再验证草稿 → 学生确认 → 带引用的材料修订；不能只检查退出码或文件存在。
- Windows：在独立数据根与隔离端口运行正式启动/健康/停止脚本，检查同端口重复启动、同数据根其他端口拒绝、操作系统实例锁、停机重启及事实保留。
- 恢复：停止隔离服务后 backup → verify → restore 到空目录 → 离线验收 → 用恢复数据根启动 → 在线验收；比较材料、错题、Today 和原件哈希，确认备份没有被修改。
- 发布：相关浏览器 spec、全量后端、源码大小与 `git diff --check` 门禁通过后提交推送。

当前实现、验证结论、精确范围、未验证项和证据只读取 [`capabilities.json`](capabilities.json)。验收脚本与报告放在 §2 的证据目录，不构成第三份状态源。

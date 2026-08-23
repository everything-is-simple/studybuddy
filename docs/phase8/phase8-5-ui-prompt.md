# Phase 8.5：Cards / Exercises UI 与 Chromium Acceptance Prompt

## 目标
在现有内嵌单页中加入可操作的 Cards/Exercises 工作区，完成 fake provider 下真实浏览器用户路径。

## 完整路径
导入材料 → 显式 indexing → 生成 card/exercise draft → 查看安全 citation → 编辑 → 保存 → 确认 ready → review/attempt → 刷新/重启恢复。

## 任务
1. 增加统一导航、deck/set 选择、card/exercise 列表、详情和状态展示。
2. 提供生成、重试、编辑、保存、确认、拒绝/归档、review/答题控件；draft 与 ready 视觉和语义必须明确。
3. citation 可查看并定位现有材料；deleted/purged/stale source 显示 unavailable，不伪造名称/正文。
4. answer key 只在允许作答/评分的受控 UI 状态使用，不通过普通列表 DOM/API 暴露。
5. 完成 busy guard、generation/request stale guard、网络/500/ malformed response 失败恢复；动态文本使用安全 DOM API。
6. 保持窄屏布局、键盘焦点、heading/label/button/list/status/alert/dialog 语义和可见焦点。
7. 编写独立 Chromium spec，避免依赖外部 provider；real provider gate 仍显式 opt-in。

## 验收
至少有一条稳定 fake-provider 完整路径；覆盖未配置 provider、invalid citation/schema、删除/purge、重复点击、过期响应、网络失败 retry、answer-key privacy、窄屏与键盘。记录真实通过项和 not_verified 限制。

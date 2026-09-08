# P1-5-4 Provider / Email 配置浏览器安全证据

> 状态：`implemented / browser-pass / mock-tested`
> 日期：2026-01-09

## 1. 范围

本切片验证正式页面 `/app/settings-provider.html` 的 Provider / Email 配置 UI：只测试、不保存；secret 仅在用户输入、connection-test 请求或用户明确点击复制时短暂存在。

不新增配置持久化、schema、migration、保存 API 或热重载。P1-5-1.1 修正了 Provider ID 与 provider type 分离、Email 环境变量复制入口、浏览器原生校验、Feishu HTTPS 形态校验，以及 pagehide/pageshow secret 清理。

## 2. 被测 endpoint 与数据

- `POST /api/system/provider-connection-test`
- `POST /api/system/email-connection-test`
- 只读状态：`GET /api/ai/capabilities`、`GET /api/readiness`
- 测试采用 Playwright route interception；未连接真实 Provider、SMTP 或 Feishu。

Synthetic sentinel：

- `TEST_SECRET_DO_NOT_LEAK_7d0f`
- `TEST_SMTP_PASSWORD_DO_NOT_LEAK_29ce`
- `TEST_WEBHOOK_DO_NOT_LEAK_5a21`

## 3. P1-5-1.1 修正

- 增加 `provider_id`，不再把 `llm` / `embedding` 当作环境变量中的 Provider ID。
- Provider connection-test 请求仍只发送已批准的 schema 字段；`provider_id` 仅用于客户端环境变量片段。
- 增加 Email 环境变量复制按钮，覆盖 SMTP host/port/secure/username/password/targets 与 Feishu webhook。
- 移除 `novalidate`，使用 `checkValidity()` / `reportValidity()`；校验 URL、端口、timeout、Email 和 Feishu HTTPS 前缀。
- connection-test、复制成功/失败、渠道切换、`pagehide`、bfcache `pageshow` 均清理 secret 输入。

## 4. 证据矩阵

| 场景 | 结果 | 证据 |
|---|---|---|
| 页面安全结构与无自动 connection-test | pass | 1 test；3 个 secret 控件均为 password、autocomplete=off、spellcheck=false；无保存按钮 |
| Provider 成功 | pass | 请求含字段和 sentinel；环境变量复制使用 `provider_id`；请求后和复制后清空 API key |
| Provider 失败 | pass | `provider_auth_failed`、`provider_timeout`、`provider_response_too_large` 均测试；安全提示且清空 API key |
| SMTP / Feishu | pass | SMTP 类型字段转换正确；Feishu 切换隐藏 SMTP 并清理 secret；两类请求后清空 |
| Clipboard 成功 | pass | mock Clipboard API；片段只交给 mock，不插入 DOM；不自动启用 delivery |
| Clipboard 拒绝 | pass | 只显示无 secret 的失败提示；仍清空 API key |
| DOM / outerHTML / URL / history / cookie / storage | pass | sentinel 全部不出现 |
| 刷新与后退 | pass | 页面刷新及返回页面后 password 为空，sentinel 不恢复 |

## 5. 无自动副作用

页面加载未触发任何 connection-test。页面未调用 delivery API、配置保存 API 或启用 delivery 的环境变量。只有 capabilities/readiness 状态请求在加载时执行。

页面不写入 `localStorage`、`sessionStorage`、cookie、IndexedDB、URL 或 history state；不生成保存配置文件。

## 6. 测试命令与结果

```text
npx playwright test backend/tests/browser_p1_5_configuration_security.spec.js \
  --workers=1 --reporter=line --timeout=60000
5 passed

npx playwright test backend/tests/browser_a4.spec.js \
  backend/tests/browser_frontend_system_matrix.spec.js \
  --workers=1 --reporter=line --timeout=60000
13 passed

C:/miniconda/py310/python.exe -m pytest \
  backend/tests/test_p1_5_0_governance.py \
  backend/tests/test_p1_5_3_persistence.py \
  backend/tests/test_p1_5_4_browser_security.py -q
23 passed
```

全量后端回归、source-size、frontend contract audit 和 `git diff --check` 在提交前执行并记录于最终 STATUS；schema 维持 v14。

## 7. 当前状态与诚实边界

当前状态：`implemented / browser-pass / mock-tested`。

本证据不代表：

- ❌ real provider/email pass
- ❌ real SMTP pass
- ❌ real Feishu pass
- ❌ 多浏览器兼容性 pass（本切片使用 Chromium）
- ❌ 对恶意浏览器扩展、操作系统剪贴板历史或同用户恶意进程的防护

未发现 synthetic sentinel 进入 DOM、URL、history、cookie、localStorage、sessionStorage、日志、backup 或持久化文件；测试中不打印完整 request body。

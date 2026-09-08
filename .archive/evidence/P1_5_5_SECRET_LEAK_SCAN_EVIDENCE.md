# P1-5-5 Provider / Email Secret 泄漏扫描证据

> 状态：`implemented / scoped-pass / synthetic-tested`
> 日期：2026-01-09

## 1. 范围

本切片建立受控运行产物的 synthetic sentinel 扫描能力，并用治理测试检查 Provider / Email 的日志、diagnostics、backup、浏览器和持久化边界。

扫描器：`backend/scripts/scan-secret-leaks.py`

扫描器只接受操作员明确指定的文件或目录，跳过符号链接、`.git`、`__pycache__`、`node_modules`、`test-results`、`playwright-report`，单文件上限 16 MiB。输出只包含状态、路径、匹配数量和 sentinel 索引，不输出 sentinel 原文、行内容、请求体或 secret 值。

## 2. 使用的 synthetic sentinel

- `TEST_SECRET_DO_NOT_LEAK_7d0f`
- `TEST_SMTP_PASSWORD_DO_NOT_LEAK_29ce`
- `TEST_WEBHOOK_DO_NOT_LEAK_5a21`

未读取 `H:\。backup\*.txt` 或任何真实凭据。

## 3. 扫描结果

在仓库内新建临时运行目录，写入无凭据的 synthetic runtime JSON 后执行：

```text
C:/miniconda/py310/python.exe backend/scripts/scan-secret-leaks.py --json H:/studybuddy/.p1-5-5-scan-tmp
{"files_scanned":"bounded","findings":[],"status":"clean"}
```

临时目录已删除，未提交。

另以 synthetic sentinel 写入临时日志验证命中行为：

- `scan_files()` 返回路径、`match_count`、`sentinel_indexes`
- 不返回 sentinel 内容
- 不向 stdout 打印匹配文本
- 符号链接和已知测试缓存不会被扫描

## 4. 代码边界核查

治理测试验证：

- `observability.py` 的日志 payload 使用固定 allowlist
- 不接受 request body、`api_key`、`smtp_password`、`feishu_webhook` 或异常文本作为观测字段
- `connection_test.py`、`delivery.py`、`api/system.py` 不直接 logger/print 连接凭据
- 页面不使用 localStorage、sessionStorage、IndexedDB 或 delivery live 启用变量
- schema 仍为 v14
- 不存在配置保存 API 或配置持久化路径
- browser evidence 已覆盖 DOM、outerHTML、URL、history、cookie、storage、刷新和后退

## 5. 测试结果

Focused governance：

```text
C:/miniconda/py310/python.exe -m pytest \
  backend/tests/test_p1_5_0_governance.py \
  backend/tests/test_p1_5_3_persistence.py \
  backend/tests/test_p1_5_4_browser_security.py \
  backend/tests/test_p1_5_5_secret_leak_scan.py -q
30 passed
```

全量后端：

```text
C:/miniconda/py310/python.exe -m pytest backend/tests/ -q
569 passed, 3 skipped
```

三个 skip 是显式 opt-in 的真实 ASR / Provider smoke test；本切片没有启用真实连接。

其他检查：

```text
backend/scripts/check-source-size.py       passed
backend/scripts/audit-frontend-contract.py --strict   0 findings
git diff --check                         clean
```

## 6. 结果解释

本切片可以声明：

- synthetic sentinel 在受控临时运行产物扫描中未发现泄漏
- 生产观测、connection-test、delivery 和配置页面的静态边界通过治理断言
- P1-5-4 browser evidence 与 P1-5-5 scanner 输出均为脱敏形式

本切片不能声明：

- ❌ 真实 API Key / SMTP 授权码 / Feishu Webhook 已被扫描
- ❌ real Provider pass
- ❌ real SMTP pass
- ❌ real Feishu pass
- ❌ 恶意浏览器扩展、系统剪贴板历史、同用户恶意进程风险已解决
- ❌ 所有外部日志采集器、终端录屏或操作系统级审计通道已验证

## 7. 交付边界

- 未修改生产 API、schema、migration 或数据库
- 未新增配置持久化
- 未新增真实网络测试
- 扫描器不会递归跟随符号链接，不读取超大文件
- 扫描器默认 sentinel 是测试值；真实凭据不会被作为命令行参数传入
- 任何真实凭据泄漏发现都必须停止提交并单独处理，不能用本证据覆盖

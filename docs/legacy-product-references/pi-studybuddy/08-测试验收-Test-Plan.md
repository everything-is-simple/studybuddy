# 08 测试验收计划

**版本**：v0.1.7
**日期**：2026-08-13
**状态**：✅ 已审查批准；T-M5-011 执行中。

> 测试服务于开发机真实主路径：单元/集成/Electron E2E/安全检查用于定位和回归，不能单独把系统标记为可用。当前问题总账见 [系统集成/02](./系统集成/02-系统问题总账与整改清单.md)。
**批准基线**：用户于 2026-08-07 批准；v0.1.6 为测试数据库治理修订，v0.1.7 为唯一 `test.turnEndIndex` 窄桥接例外登记。
**上游**：[02-PRD v0.1.4 §7](./02-PRD-产品需求-Product-Requirements.md)、[03-Architecture v0.1.3 §3/§8/§9](./03-架构设计-Architecture-Design.md)、[05-ERD v0.1.2 §6](./05-数据模型-ERD-Data-Model.md)、[06-API v0.1.6](./06-API契约-API-Contracts.md)、[07-Workflow v0.1.3 §8/§9](./07-工作流-Workflow.md)
**下游**：04-Todo、09-UI
**血统**：ai-studybuddy 已验证测试纪律迁移（342 后端 + 149 前端 + 24 E2E + 真实冒烟，不复制实现）

---

## 1. 概述

### 1.1 测试目标

pi-studybuddy 的测试要回答三个问题：

1. **业务闭环是否打通**：S1-S7 + TTS + 备份恢复全链路可走通（02-PRD §7.1）
2. **隐私边界是否守住**：作答前 DTO 防泄露、家长报告脱敏、UUID 泄漏检测、AI 日志 allowlist、安全不变量六条（02-PRD §7.2）
3. **规则优先是否落实**：批改/聚合/速背卡/冲刺计划由确定性规则负责，AI 失败不阻塞（02-PRD §7.4）

### 1.2 测试金字塔

```
        ┌───────────┐
        │ 系统 E2E  │  vitest + Electron 启动，全链回归，少量高价值（~24）
        ├───────────┤
        │ 系统冒烟  │  vitest + 真实组件，每子系统 1 条主路径
        ├───────────┤
        │  集成测试  │  vitest，extension×pi 底座契约 + 钩子协作
        ├───────────┤
        │  单件测试  │  vitest（TS）+ pytest（Python 桥），数量最多
        └───────────┘
```

### 1.3 测试纪律（铁律）

1. **五阶段映射**：单件→集成→系统冒烟→系统 E2E，任一阶段失败退回上一阶段，不进 master（03-Architecture §9.1）
2. **冒烟失败=退件不是事故**：工位不合格退件，修复后重走当前阶段
3. **防泄露先于功能**：作答前 DTO / 家长报告脱敏 / UUID 泄漏检测的断言优先级最高，失败即阻塞
4. **规则优先可证伪**：批改/聚合/速背卡必须有"AI 不可用仍产出正确结果"的测试
5. **运行数据隔离**：所有测试写 `H:\pi-studybuddy-tmp\runs\<test-task-id>\`，绝不污染真实业务数据根
6. **不连真实外部服务**：AI/SMTP/飞书/whisper.cpp 全部 mock，仅冒烟/E2E 可走受控夹具
7. **测试即文档**：每个测试名用中文描述被验证的行为，失败即知"哪条业务铁律破了"

---

## 2. 测试分层总览（对应五阶段）

| 分层 | 五阶段 | 范围 | 工具 | 运行环境 | 目标数量 |
|---|---|---|---|---|---|
| **单件测试** | 阶段 2 | registerTool 契约 / 数据层触发器约束 / 外部桥 / 技能夹具 / TTS skill | vitest（TS）+ pytest（Python 桥） | Node + venv | ≥ 300 |
| **集成测试** | 阶段 3 | studybuddy-extension × pi 底座 / 工具 × pi.on 钩子 / createAgentSession 真实 provider | vitest | Node + pi 真实包 | ≥ 60 |
| **系统冒烟** | 阶段 5a | S1-S7 主路径 / TTS / 备份恢复 / 家长报告脱敏 / 路径守卫 / credential-vault / 安全不变量六条 | vitest + check-desktop-security.mjs | 真实 Electron + 真实组件（外部 mock） | ≥ 30 |
| **系统 E2E** | 阶段 5b | 学生主路径 / 家长报告 / TTS / 备份恢复 全链回归 | vitest + Electron 启动 | 真实 Electron 启动 | ≥ 24 |

> 数量目标是"等价覆盖 ai-studybuddy 已验证测试面"，非硬性 KPI；以断言密度与铁律覆盖率为准。

---

## 3. 单件测试（阶段 2）

### 3.1 registerTool 工具契约断言

**依据**：03-Architecture §2.2（registerTool 契约：`ToolDefinition` 必填 name/label/description/parameters/execute；execute 返回 `{content, details, usage?, terminate?}`；错误须 throw 不返回 error 对象）。

**每个学习工具必须断言**：

```typescript
// 伪代码，vitest 风格
describe("studybuddy_archive_mistake 工具契约", () => {
  it("registerTool 返回 void（不返回 disposer/handle）", () => {
    const ret = pi.registerTool(createMistakeArchiveTool());
    expect(ret).toBeUndefined();
  });

  it("ToolDefinition 含必填字段 name/label/description/parameters/execute", () => {
    const tool = createMistakeArchiveTool();
    expect(tool.name).toMatch(/^studybuddy_[a-z_]+$/);
    expect(tool.label).toBeTruthy();
    expect(tool.description).toBeTruthy();
    expect(tool.parameters).toBeDefined();
    expect(typeof tool.execute).toBe("function");
  });

  it("execute 成功返回 {content, details, usage?, terminate?}", async () => {
    const tool = createMistakeArchiveTool();
    const result = await tool.execute({ practiceAnswerId: "ans-1" }, ctx);
    expect(result).toHaveProperty("content");
    expect(result).toHaveProperty("details");
  });

  it("execute 失败 throw Error（不返回 error 对象）", async () => {
    const tool = createMistakeArchiveTool();
    await expect(tool.execute({ practiceAnswerId: "not-exist" }, ctx))
      .rejects.toThrow();
  });
});
```

**覆盖清单**：03-Architecture §3.1-§3.2 全部工具（S1-S7 + TTS + 备份恢复，约 30 个工具）每个至少 4 条契约断言。

### 3.2 数据层单测（触发器 / 约束 / 状态机）

**依据**：05-ERD §6（触发器）、§3（CHECK 约束）、07-Workflow §8（11 状态机）。

#### 3.2.1 关系一致性触发器（6 个，05-ERD §6.1）

| 触发器 | 断言用例 |
|---|---|
| question/course 一致 | 插入 question 引用不存在的 course_instance → 拦截 |
| question/module 一致 | 插入 question 引用不存在的 knowledge_module → 拦截 |
| answer/question 一致 | 插入 practice_answer 引用不存在的 question → 拦截 |
| mistake/question 一致 | 归档 mistake 引用不存在的 question → 拦截 |
| mistake_evidence/answer 一致 | 插入证据引用不存在的 practice_answer → 拦截 |
| weak_point/module 一致 | 归纳 weak_point 引用不存在的 module → 拦截 |

#### 3.2.2 storage_key 路径逃逸防护触发器

```
插入 materials.storage_key 含 ".." → 拦截
插入 materials.storage_key 含 ":\" → 拦截
插入 materials.storage_key 含 ":/" → 拦截
正常相对路径 "semester/xxx/storage/file.pdf" → 通过
```

#### 3.2.3 mock_exam_papers 触发器（assessment_attempt 必须 confirmed）

```
未确认考试（confirmation_status=pending）→ 生成模拟卷 → 拦截
已确认考试（confirmed）→ 生成模拟卷 → 通过
```

#### 3.2.4 幂等归档约束

```
同一 question_id 二次归档 mistake → UNIQUE 冲突拦截
同一 source_practice_answer_id 二次写 mistake_evidence → UNIQUE 冲突拦截
```

#### 3.2.5 CHECK 约束

- `mock_exam_questions`：选择题 vs 填空题字段互斥（选择题 options/correct_answer 必填，填空题 acceptable_answers 必填）
- `semesters.end_date > start_date`
- `schedule_entries.end_time > start_time`
- `study_tasks.priority BETWEEN 1 AND 5`

### 3.3 外部桥 Adapter 单测

#### 3.3.1 WPS COM 桥（pytest，Python 子进程契约）

**依据**：03-Architecture §3.3。主进程 Node 经 `child_process.spawn` 调用 Python，stdin/stdout JSON 协议。

```python
# 伪代码，pytest 风格
def test_wps_bridge_doc_to_docx(tmp_path):
    """doc → docx 转换返回归一化 JSON"""
    result = run_wps_bridge(["convert", "--in", "test.doc", "--out", str(tmp_path)])
    assert result["status"] == "ok"
    assert (tmp_path / "test.docx").exists()

def test_wps_bridge_crash_isolation():
    """WPS 崩溃不影响主进程：子进程退出码非 0，主进程收到 INTERNAL_ERROR"""
    with pytest.raises(ChildProcessError):
        run_wps_bridge(["convert", "--in", "corrupt.doc"])

def test_wps_bridge_json_protocol():
    """stdin/stdout 严格 JSON，无额外输出污染"""
    out = run_wps_bridge(["ping"])
    json.loads(out)  # 不抛异常即通过
```

#### 3.3.2 whisper.cpp Adapter（vitest，子进程契约）

**依据**：03-Architecture §3.3。CLI/模型路径只来自配置，不猜路径不回退云端。

```typescript
it("路径未配置 → INTERNAL_ERROR + 固定错误码，不泄漏路径", async () => {
  config.whisperCliPath = "";
  await expect(transcribe({ audioFile: "test.wav" }))
    .rejects.toThrow(/未配置/);
  // 错误消息不含路径/stdout/stderr
});

it("受控 PCM WAV 文件头验证：拒绝 MP3/M4A/WebM", async () => {
  await expect(transcribe({ audioFile: "test.mp3" }))
    .rejects.toThrow(/PCM WAV/);
});

it("转写成功返回文本，不返回 stdout 全文", async () => {
  const result = await transcribe({ audioFile: "valid.wav" });
  expect(typeof result.text).toBe("string");
  expect(result).not.toHaveProperty("stdout");
});
```

#### 3.3.3 OCR venv Adapter（pytest）

**依据**：03-Architecture §3.3。onnxruntime/PIL 全图片格式。

```python
@pytest.mark.parametrize("fmt", ["jpg","jpeg","png","webp","gif","bmp","tiff"])
def test_ocr_all_image_formats(fmt, sample_image):
    text = run_ocr(sample_image(fmt))
    assert isinstance(text, str) and len(text) > 0
```

### 3.4 引入技能夹具（pi-skills）

**依据**：03-Architecture §5.2（引入的 pi-skills）+ §5.1（pi-skills 缺测试，pi-studybuddy 必补夹具）。

| 技能 | 夹具断言 |
|---|---|
| `youtube-transcript` | 给定 video-id/URL → 返回带时间戳字幕；429/5xx 指数退避 |
| `brave-search` | API key 走 credential-vault；返回结果列表 |
| `browser-content`（pi-skills browser-tools 子能力） | 给定 HTML → Readability+Turndown 提取正文 |

### 3.5 TTS skill 单测

**依据**：03-Architecture §3.2（TTS 工具）+ 07-Workflow §4。

```typescript
it("SAPI 默认引擎离线可用，返回 playbackId", async () => {
  const r = await ttsSpeak({ text: "测试朗读" });
  expect(r.playbackId).toBeTruthy();
});

it("edge-tts 网络失败自动降级 SAPI", async () => {
  mockNetwork.fail();
  const r = await ttsSpeak({ text: "测试", engine: "edge-tts" });
  expect(r.fallbackUsed).toBe(true);
  expect(r.engine).toBe("sapi");
});

it("朗读本身不写 StudyEvent（除非学生标记已复习）", async () => {
  await ttsSpeak({ text: "..." });
  expect(studyEventsTable.count()).toBe(0);
});
```

---

## 4. 集成测试（阶段 3）

### 4.1 studybuddy-extension 与 pi 底座对接

**依据**：03-Architecture §2.1（单一 extension factory）+ §9.1（集成测试产物）。

```typescript
it("createStudyBuddyExtension() 注册全部业务工具且返回 void", () => {
  const pi = createMockPi();
  const ext = createStudyBuddyExtension();
  ext.setup(pi);
  // 断言所有 S1-S7 + TTS + 备份恢复工具均被 registerTool
  expect(pi.registeredTools.map(t => t.name)).toEqual(
    expect.arrayContaining([
      "studybuddy_init_semester",
      "studybuddy_archive_mistake",
      "studybuddy_generate_mock_exam",
      "studybuddy_tts_speak",
      "studybuddy_backup_course",
      // ... 全部
    ])
  );
});

it("pi.registerProvider() 注入学习场景 provider，不重写 provider", () => {
  // 断言调用 registerProvider 而非覆盖 builtinProviders
});
```

### 4.2 工具与 pi.on 钩子协作

**依据**：03-Architecture §2.3（6 个钩子）+ §3.4（workspace-path-guard）。

| 钩子 | 集成断言 |
|---|---|
| `before_agent_start` | 注入 L1 画像 + 当前学期/课程上下文 + 私有技能清单 |
| `session_start` | 初始化学期库连接 + 加载 L1 画像 |
| `tool_call` | write/edit 工具尝试逃逸业务数据根 → block:true |
| `tool_result` | 工具失败统一走此钩子记录（observability） |
| `model_select` | 持久化到 `<dataRoot>/config/models.json`（`__studybuddy_managed` 标记） |
| `turn_end` | L3 增量索引（last_offset + last_mtime_ms） |

```typescript
it("workspace-path-guard 拦截符号链接逃逸", () => {
  const symlink = path.join(dataRoot, "evil");
  fs.symlinkSync("/etc/passwd", symlink);
  const decision = checkWorkspaceMutationPath(dataRoot, symlink);
  expect(decision.block).toBe(true);
});

it("tool_result 钩子集中记录工具失败（observability）", async () => {
  await failingTool.execute({...}, ctx);
  expect(observedEvents.some(e => e.event === "tool_execution_end" && e.errorCode))
    .toBe(true);
});
```

### 4.3 createAgentSession 真实 provider 拼装

**依据**：03-Architecture §9.1（`createAgentSession({ customTools })` 拼装真实 pi-ai provider）。

```typescript
it("createAgentSession 拼装真实 provider + customTools 可执行", async () => {
  const session = await createAgentSession({
    customTools: [...createS1RhythmTools(), ...createTtsTools()],
    provider: mockProvider,  // mock LLM 响应
  });
  const result = await session.callTool("studybuddy_tts_speak", { text: "集成" });
  expect(result.content).toBeTruthy();
});
```

---

## 5. 系统冒烟测试（阶段 5a）

> 真实 Electron + 真实组件，外部服务（AI/SMTP/飞书/whisper.cpp）mock。每子系统 1 条主路径，验证"端到端可走通 + 铁律不破"。

### 5.1 S1-S7 全链路冒烟

| 冒烟用例 | 验证铁律 |
|---|---|
| S1 学期初始化：建学期→建课程→OCR 课表→确认考试→ready=1 | 未确认考试不驱动冲刺 |
| S2 资料笔记：上传 PDF→转换→AI 生成笔记→知识模块带 source_evidence | AI 失败保留 normalized_text + pending_quality_check |
| S3 限时练习：选模块→AI 生成题→作答→规则批改→is_correct=false 流 S4 | 作答前 DTO 不含 correct_answer/explanation |
| S4 错题改错：幂等归档→AI 错因建议→学生确认→重做→weak_point | 幂等 UNIQUE；evidence_count≥2 才形成 weak_point |
| S5 期末冲刺：confirmed 考试→生成模拟卷→作答→批改→速背卡+冲刺计划 | 速背卡/计划确定性只读，不依赖 AI |
| S6 家长报告：规则报告→冻结→UUID 泄漏检测→投递（渠道隔离） | assertNoSensitiveLeak；渠道独立失败隔离 |
| S7 课堂采集：许可确认→PCM WAV→whisper.cpp→保存为 S2 输入 | 受控 PCM WAV；原始音频 finally 清理 |

### 5.2 TTS 跨子系统冒烟

```
打开工作台 → S2 笔记朗读 → 暂停 → 继续 → 停止
           → S4 错题复盘朗读
           → S5 速背卡朗读
           → 任意 Markdown 朗读
           → 标记"已复习" → 写 practice_reviewed StudyEvent
SAPI 默认离线可用；edge-tts 失败降级 SAPI
```

### 5.3 备份恢复冒烟

```
单课程备份 → zip 含 manifest.json + data/*.jsonl + storage/ → content_hash 校验
全课程备份 → 多 zip
定期调度 → cron 到期自动执行 → backup_records(scheduled)
恢复 → content_hash 校验 → schema_version 兼容 → 同名冲突学生确认 → integrity_check
归档前后强制备份 → backup_type=pre_archive/post_archive
```

### 5.4 家长报告脱敏冒烟

```
生成报告 → 序列化 ParentReportResult → UUID 正则检测 → 发现完整 UUID 抛 PARENT_REPORT_PRIVACY_VIOLATION
AI 摘要也经检测 → 失败降级规则报告
报告不含：原文/题干/答案/作答/错因/完整 UUID/真实渠道地址
```

### 5.5 workspace-path-guard 冒烟

```
write 工具尝试写 ~/.pi/agent/ → block（业务数据根是 %LOCALAPPDATA%\PiStudyBuddy）
write 工具尝试符号链接逃逸 → block
正常写业务数据根内 → 通过
```

### 5.6 credential-vault 冒烟

```
safeStorage.isEncryptionAvailable() → true（Windows DPAPI）
encryptString/decryptString 往返一致
文件 mode 0o600
键名匹配 /^modelProvider:[a-z0-9._-]{1,160}$/i 和 /^parentContact:[a-z0-9._-]{1,160}$/i
```

### 5.7 安全不变量校验脚本（六条，check-desktop-security.mjs）

**依据**：03-Architecture §8.2（借鉴 pi-desktop `scripts/check-desktop-security.mjs:75` 硬断言）。

```javascript
// scripts/check-desktop-security.mjs（硬断言，CI 必跑）
assert(windowConfig.webPreferences.sandbox === true, "sandbox:true");
assert(csp.includes("default-src 'self'"), "严格 CSP");
assert(preloadOnlyExposesPiBridge, "preload 仅 exposeInMainWorld('piBridge')");
assert(usesSafeStorage, "credential-vault 用 safeStorage");
assert(hasContractApiAndRpc, "Host RPC 契约化");
assert(htmlPreviewCsp.includes("form-action 'none'"), "HTML 预览独立 CSP");
```

> 此脚本在 CI 与本地 `pnpm precheck` 均跑，任一断言失败阻塞合并。

---

## 6. 系统 E2E 测试（阶段 5b，vitest + Electron 启动）

> 真实 Electron 启动，全链回归。外部服务 mock，但数据层与组件真实。
>
> **框架选择**（v0.1.2 修订）：pi-studybuddy 是 Electron 单体（无独立后端），ai-studybuddy 的 Playwright webServer 模式不适用；参考 pi-desktop `scripts/test-browser-agent-e2e.mjs` 范式，采用 vitest + `_electron.launch()` 直接启动 Electron 窗口，通过 `webContents.executeJavaScript` 驱动 UI 交互 + RPC 通道验证数据层。不引入 Playwright 依赖（AGENTS.md §6.4 禁止过度工程化）。

### 6.1 学生主路径 E2E

```
E2E-01 学期初始化全链
  启动应用 → 新建学期 → 新建课程 → 上传课表图片(夹具) → OCR 预览 → 确认 → 补考试 → 确认考试 → 首页 ready

E2E-02 资料笔记全链
  选课程 → 上传 PDF(夹具) → 转换完成 → 生成笔记 → 查看导图 → 知识模块学习状态流转

E2E-03 练习→错题→薄弱点全链
  选模块 → 生成题 → 作答(故意答错) → 提交 → 批改 → 错题归档 → 确认错因 → 重做正确 → 薄弱点形成

E2E-04 期末冲刺全链
  confirmed 考试 → 生成模拟卷 → 限时作答 → 批改 → 查看弱项分析 → 速背卡 → 冲刺计划

E2E-05 课堂采集→S2 handoff
  许可确认 → 选 PCM WAV(夹具) → whisper.cpp(mock) → 修改转写 → 保存为 S2 输入 → 生成笔记
```

### 6.2 家长报告 E2E

```
E2E-06 家长报告生成与投递
  触发报告 → 规则生成 → 冻结 → UUID 检测通过 → 本地导出 → 文件存在 → 投递状态 sent
  渠道隔离：SMTP(mock) 失败不影响本地导出
```

### 6.3 TTS E2E

```
E2E-07 TTS 随时可击发
  打开 S2 笔记 → 点朗读 → 听到播放(断言 playbackId + state=playing)
  切换 S4 错题 → 点朗读 → 新播放
  标记已复习 → study_events 多一条 practice_reviewed
```

### 6.4 备份恢复 E2E

```
E2E-08 备份与恢复全链
  建课程+资料+练习 → 单课程备份到 tmp 目录 → zip 存在 → content_hash 校验
  删除课程数据 → 从 zip 恢复 → 课程数据回来 → integrity_check 通过

E2E-09 定期调度备份
  配置 cron(每分钟,测试用) → 等待触发 → backup_records(scheduled) 写入
```

### 6.5 通用 AI 对话 E2E（02-PRD §3.11 + 07-Workflow §2.8）

```
E2E-10 对话 Tab 默认主入口 + AI 自主调用工具
  启动应用 → 默认打开"💬 对话"标签页 → 看到"你好，今天想学点什么？"
  → 学生发送"帮我理解极限的 ε-δ 定义"
  → AI 流式回复（断言 Streams["agent.events"] 推送）
  → L1 画像注入（断言 before_agent_start 钩子触发）

E2E-11 对话中 AI 自主调用工具 + 跳转结构化 Tab
  学生发送"帮我出 5 道导数定义题"
  → AI 调用 studybuddy_generate_questions → 工具调用视图可见
  → renderer 展示"已生成 5 题 [去练习]"按钮
  → 点击"去练习" → 跳转练习 Tab（断言 sessionId 传递）

E2E-12 对话 @文件引用 + TTS 朗读
  学生输入 @ → 弹出当前课程资料选择器
  → 选"第2章笔记.pdf" → 文件内容注入对话
  → AI 回复后点击"朗读"按钮
  → 调用 studybuddy_tts_speak → 朗读控制条状态 playing
  → 标记"已复习" → study_events 多一条 practice_reviewed

E2E-13 对话 L3 会话检索
  长对话多轮 → turn_end 钩子增量索引
  → 关闭应用重开 → sessions.search("极限") → 找到历史会话
```

**关键断言**：
- 应用启动默认 Tab 是"💬 对话"（不是首页）
- AI 回复经 `Streams["agent.events"]` 流式推送
- 工具调用过程可视化（工具名 + 结果摘要）
- @文件引用经 allowed-roots 校验
- L1 画像在 before_agent_start 注入（集成 §4.2 断言）
- L3 在 turn_end 增量索引（断言 chunks_fts 有记录）

### 6.6 用户端到端测试铁律（真机 UAT，v0.1.5 用户明确指令 2026-08-12）

每个任务在收尾前，除了自动化全测试（unit/integration/E2E/verify full）之外，**必须执行用户端到端测试（真机 UAT）**：

- 使用真实 Electron 应用 + 全新隔离数据根（`H:\\pi-studybuddy-tmp\\runs\\<task-id>\\`），不种子、不调用 handler 绕过界面，完全通过可见 UI 操作走用户主路径；
- 至少覆盖本任务涉及的每个用户可见闭环（创建→使用→重启持久化），并逐页/逐按钮记录可达性与可用性；
- 记录步骤级证据（DOM/截图/JSON）到运行根，并在实施记录 §6 登记；
- DOM 不得含完整 UUID、绝对路径或错误栈；
- 真机 UAT 未通过或证据不足时，不得报告任务完成。

参考实现：T-M5-002 真机 UAT 证据位于 `H:\\pi-studybuddy-tmp\\runs\\T-M5-002\\uat\\`（first-run.json / reopen.json / UAT-报告.md）。

---

## 7. 关键断言矩阵（对应 02-PRD §7 成功标准）

> 每条成功标准对应至少一个测试断言，形成"需求→测试"可追溯。

### 7.1 闭环完整性（02-PRD §7.1）

| 成功标准 | 断言位置 | 断言要点 |
|---|---|---|
| S1-S7 全部可演示 | E2E-01~05 | 全链路无异常退出 |
| 学期→资料→模块→练习→错题→冲刺→报告打通 | E2E-01~04+06 | 数据流贯通 |
| S7→S2 handoff | E2E-05 | 转写保存为 materials(file_type=text, status=converted) |
| S4→S5 薄弱点回流 | E2E-03+04 | weak_point 被 S5 速背卡读取 |
| TTS 随时可击发 | E2E-07 | S2/S4/S5/任意 Markdown 均可触发，SAPI 离线可用 |
| **通用 AI 对话默认主入口** | **E2E-10~13** | **应用启动默认打开对话 Tab + AI 自主调用工具 + @文件引用 + L3 检索** |

### 7.2 隐私边界守护（02-PRD §7.2）

| 成功标准 | 断言位置 | 断言要点 |
|---|---|---|
| assertNoSensitiveLeak UUID 检测 | 冒烟 §5.4 + 单件 | 注入完整 UUID 到报告 → 抛 PARENT_REPORT_PRIVACY_VIOLATION |
| AI 日志 allowlist | 单件 + 冒烟 | 非 allowlist 字段抛错；字符串值 ≤128 字符 |
| 家长报告不含原文/题干/答案/作答/错因/UUID | 冒烟 §5.4 | 报告序列化正则扫描禁用词 |
| API 信封统一 6 错误码 | 单件（每个 RPC 方法） | 失败返回 `{success:false, error:{code,message}}` |
| 仅 127.0.0.1 | 安全不变量脚本 | 无公网监听断言 |

### 7.3 证据驱动（02-PRD §7.3）

| 成功标准 | 断言位置 | 断言要点 |
|---|---|---|
| 知识模块带 source_evidence 回链 | 单件 S2 + E2E-02 | knowledge_modules[].source_evidence 非空 |
| 考试日期带来源/置信度/确认/变更历史 | 单件 S1 | assessment_attempts 字段齐全 |
| 错题幂等归档 | 单件 §3.2.4 | UNIQUE(question_id) + UNIQUE(source_practice_answer_id) |
| 错因学生确认 | 单件 S4 + E2E-03 | AI 建议带"不确定"标记，confirmed_by='student' |
| 薄弱点 evidence_count≥2 | 单件 S4 + E2E-03 | 单次错误不形成 weak_point |

### 7.4 规则优先（02-PRD §7.4）

| 成功标准 | 断言位置 | 断言要点 |
|---|---|---|
| 批改由规则负责 | 单件 S3 | mock AI 不可用，批改仍正确（单选精确/多选 deepEquals/填空 normalize） |
| 每日首页规则聚合 | 单件 S1 | daily_brief 不调 LLM |
| 速背卡/冲刺计划确定性只读 | 单件 S5 + E2E-04 | 不建表、不持久化、不调 LLM |
| AI 不可用保留确定性输出 | 冒烟 §5.1 各子系统 | S2 pending_quality_check / S6 规则报告 |

### 7.5 单机零云（02-PRD §7.5）

| 成功标准 | 断言位置 | 断言要点 |
|---|---|---|
| 无公网入口 | 安全不变量 | 仅 loopback 监听 |
| 无云数据库 | 架构审查 | 仅 SQLite + 本地文件 |
| 可本地推理 | 集成 §4.3 | Ollama provider 可注入 |
| whisper.cpp 本机不回退云端 | 单件 §3.3.2 | 路径未配置 → 报错，不尝试云端 |

### 7.6 备份恢复（02-PRD §7.6）

| 成功标准 | 断言位置 | 断言要点 |
|---|---|---|
| 每课程独立 zip | 冒烟 §5.3 + E2E-08 | zip 含 manifest + data + storage |
| 备份到本地其他目录 | E2E-08 | targetPath 可选 |
| 从 zip 恢复 + content_hash 校验 | E2E-08 | 损坏 zip → BAD_REQUEST |
| 定期调度默认每周一/可配置每月一 | 单件 + E2E-09 | cron_expression 校验 |
| 手动触发单课程/全课程 | 冒烟 §5.3 | backup_type=manual |
| 归档前后强制备份 | 冒烟 §5.3 | pre_archive/post_archive |
| SQLite 崩溃后可恢复 | E2E-08 | 删数据→恢复→integrity_check 通过 |

---

## 8. 状态机测试矩阵（11 个状态机）

> 07-Workflow §8 的每个状态机必须有"合法迁移通过 + 非法迁移拦截"断言。

| 状态机 | 合法迁移 | 非法迁移拦截 |
|---|---|---|
| 学期 | active→teaching_ended→follow_up→archived | archived→active 拦截 |
| 考试确认 | pending→confirmed/rejected；confirmed→superseded | pending→superseded 拦截 |
| Material | pending→converting→converted→note_generating→completed | completed→pending 拦截 |
| Job | pending→running→completed/failed | completed→running 拦截 |
| 练习会话 | in_progress→submitted→graded | graded→in_progress 拦截 |
| 错题 | needs_review→mastered；mastered→needs_review | mastered→archived(无此迁移) 拦截 |
| 薄弱点 | active→resolved；resolved→regressed | resolved→active(非回退路径) 拦截 |
| 模拟考 | in_progress→submitted→graded | submitted→in_progress 拦截 |
| 报告投递 | pending→sent/failed/retained_locally | sent→pending 拦截 |
| 知识模块 | not_started→learning→mastered/needs_review | mastered→not_started 拦截 |
| 备份 | in_progress→completed/failed | completed→in_progress 拦截 |

---

## 9. 测试夹具与运行数据隔离

### 9.1 运行数据隔离（铁律）

**依据**：00 索引 §五 + v2 Prompt §三（`H:\pi-studybuddy-tmp\runs\<task-id>`）。

- 所有测试写 `H:\pi-studybuddy-tmp\runs\<test-task-id>\`，**绝不污染**真实业务数据根 `%LOCALAPPDATA%\PiStudyBuddy`
- 测试启动时设置环境变量 `PI_STUDYBUDDY_DATA_ROOT=H:\pi-studybuddy-tmp\runs\<test-task-id>`
- 测试结束后 `finally` 清理 tmp（S7 原始音频同此）
- E2E 每条用例独立 `test-task-id`，互不干扰
- **专用测试数据库**：数据库型测试须在运行根建立专属 `global.db` 与 `semester/<semester-id>/sem.db`；测试可用合成学习内容在该专属库中建立前置数据，但不得连接、复制、覆盖或查询 `%LOCALAPPDATA%\PiStudyBuddy`。
- **测试库建立边界**：优先经正式 schema 与正式 handler 创建学期、课程、任务、考试、资料等实体；当前无公开创建 RPC 的前置实体只能在 Electron 启动前写入专属测试库，并须保留真实 FK/CHECK/触发器约束。不得提供用于创建、预置或篡改业务数据的 `test.*` RPC，也不得在运行中的应用 handler 中 seed。
- **唯一既存 E2E 桥接例外（须显式登记）**：`tests/e2e/test-main.js` 的隔离 loopback 测试子进程仅以 `test.turnEndIndex` 转接生产纯函数 `indexTurnEndChunks`，模拟 E2E 环境未启动的 pi `turn_end` 钩子；它不出现在生产 contract/agent-host、不得作为 renderer 可达方法、不得预置 S1-S7 业务实体，并且只在独立运行根内执行。任何新增 `test.*` 例外均须先修改本条、补测试并经任务范围裁决。
- **连接生命周期**：建库辅助函数返回前必须关闭 SQLite 连接；Windows WAL/SHM 句柄不得阻止专属库清理，也不得与随后真实 Electron 进程争抢数据根。

### 9.2 合成夹具原则

- **资料夹具**：每个 file_type 至少 1 个最小合成样本（pdf/docx/pptx/xlsx/image/pcm-wav）
- **不使用真实学生数据/真实资料原文**（02-PRD §5.2 隐私边界）
- **AI 响应夹具**：mock provider 返回固定 JSON，覆盖成功/超时/格式错误三态
- **PCM WAV 夹具**：合成 16kHz/单声道/16-bit 正弦波几秒音频

### 9.3 禁用真实外部服务

| 外部服务 | 测试中处置 |
|---|---|
| AI provider（云端 LLM） | mock，返回固定响应 |
| SMTP | mock，记录投递调用不真发 |
| 飞书 Webhook | mock |
| whisper.cpp | 单件可真实（本机）；集成/E2E 用 mock 避免依赖模型文件 |
| WPS COM | 单件需真实 WPS；集成/E2E 可 mock 子进程返回 |
| OCR venv | 单件真实；集成/E2E 可 mock |

> 仅"系统冒烟"允许少量真实组件（Electron/SQLite/credential-vault/safeStorage），外部服务一律 mock。`runMockFixture` 只能由 VITEST 测试注入；生产 agent.send 没有可用模型配置时必须返回固定 `MODEL_NOT_CONFIGURED`，不得静默回退夹具。

---

## 10. 测试命名与组织约定

### 10.1 命名

- 测试文件：`*.test.ts`（vitest）/ `test_*.py`（pytest）
- 测试名用中文描述被验证行为：`it("未确认考试生成模拟卷 → 拦截", ...)`
- 测试 ID：`T-<子系统>-<序号>`（如 `T-S4-003`），便于失败追溯

### 10.2 目录组织

```
src/
  ├ agent/
  │  ├ studybuddy-extension.ts
  │  └ __tests__/
  │     ├ studybuddy-extension.test.ts       ← 集成
  │     ├ tools/
  │     │  ├ s1-rhythm.test.ts               ← 单件
  │     │  ├ s4-error.test.ts
  │     │  └ tts.test.ts
  │     └ hooks/
  │        ├ workspace-path-guard.test.ts
  │        └ observability.test.ts
  ├ main/
  │  └ __tests__/
  │     ├ credential-vault.test.ts
  │     └ check-desktop-security.mjs          ← 安全不变量脚本
  └ data/
     └ __tests__/
        ├ triggers.test.ts                   ← 触发器单件
        └ state-machines.test.ts            ← 状态机单件

e2e/                                          ← vitest + Electron E2E
  ├ helpers/
  │   ├ electron-launcher.ts
  │   ├ rpc-driver.ts
  │   └ fixtures.ts
  ├ e2e-01-semester-init.test.ts
  ├ e2e-02-materials-notes.test.ts
  ├ e2e-03-practice-mistake-weakpoint.test.ts
  ├ e2e-04-cram.test.ts
  ├ e2e-05-capture.test.ts
  ├ e2e-06-parent-report.test.ts
  ├ e2e-07-tts.test.ts
  ├ e2e-08-backup-restore.test.ts
  └ e2e-09-scheduled-backup.test.ts

scripts/
  └ wps-bridge/                              ← Python 桥 pytest
     ├ test_wps_convert.py
     └ test_ocr.py
```

### 10.3 运行命令（约定）

```
pnpm test           # 全部 vitest 单件+集成
pnpm test:smoke      # 系统冒烟（真实 Electron）
pnpm test:e2e        # vitest + Electron E2E
pnpm precheck        # check-desktop-security.mjs + 类型检查 + lint
pytest scripts/wps-bridge/   # Python 桥单件
```

---

## 11. 测试通过门槛（门禁）

### 11.1 合并到 master 的门槛

- [ ] 全部单件测试通过（vitest + pytest）
- [ ] 全部集成测试通过
- [ ] 系统冒烟全部通过
- [ ] 安全不变量校验脚本六条断言全过
- [ ] 受影响子系统的 E2E 通过
- [ ] `git diff --check` 无空白错误
- [ ] 不提交：真实密钥/.env.local/资料原文/完整 UUID/node_modules

### 11.2 五阶段组件治理门槛（03-Architecture §9.1）

任一阶段失败 → 退回上一阶段重做，不进 master：

```
阶段 2 单件失败 → 修复组件 → 重跑单件
阶段 3 集成失败 → 退回单件 → 重跑集成
阶段 5 冒烟/E2E 失败 → 退回集成 → 重跑冒烟
```

### 11.3 冒烟失败处置

**冒烟失败 = 该工位不合格退件，不是事故**（00 索引 §四）：
- 不追责，修复后重走当前阶段
- 修复记录写 docs/04-Todo 证据

---

## 12. 版本历史

| 版本 | 日期 | 变更 |
| v0.1.6 | 2026-08-13 | 测试数据库治理修订：§9.1 明确数据库型测试在 `H:\pi-studybuddy-tmp\runs\<task-id>` 下建立专属 `global.db` + `semester/<id>/sem.db`，优先正式 schema/handler 建前置数据，禁止运行中的 `test.*` seed RPC；建库后关闭 SQLite 连接，消除 Windows WAL/SHM 锁。依据：用户明确“测试阶段数据不依赖 mock 数据，建立专门测试数据库”+ AGENTS.md §5.3/§9.5。 |
| v0.1.4 | 2026-08-09 | 交叉审查修订：增加真实 Electron 代表性 business RPC（`semesters.list`）与无模型 `agent.send` 生产路由断言；强化契约覆盖为遇到未解析 spread/缺失 handler 直接失败；测试夹具仅限显式 VITEST 注入。 |
| v0.1.3 | 2026-08-08 | §4.2 model_select 断言落点修订：`~/.pi/agent/models.json` → `<dataRoot>/config/models.json`（T-M3-005 裁决 1，AGENTS.md §9.5 物理隔离；与 03-Arch §2.3 supersedes 同步） |
| v0.1.2 | 2026-08-08 | §6 E2E 框架由 Playwright 改为 vitest + Electron 启动。原因：pi-studybuddy 是 Electron 单体（无独立后端），ai-studybuddy 的 Playwright webServer 模式不适用；参考 pi-desktop `scripts/test-browser-agent-e2e.mjs` 范式，采用 vitest + `_electron.launch()` 直接启动，通过 `webContents.executeJavaScript` 驱动 UI 交互。依据：AGENTS.md §6.4 禁止过度工程化 + 用户批准 T-M1-010 方案 A。影响：§1.2 测试金字塔 + §2 分层总览 + §6 标题与说明 + §10.2 目录结构 + §10.3 运行命令，无 E2E 用例设计变更 |
| v0.1.1 | 2026-08-07 | 按用户反馈增强：§6.5 新增 E2E-10~13 通用 AI 对话 E2E（默认主入口 + AI 自主调用工具 + @文件引用 + TTS 朗读 + L3 会话检索）；§7.1 闭环完整性表补"通用 AI 对话默认主入口"行；响应用户反馈"pi 天生自带对话，不能废弃 ai 输入" |
| v0.1.0 | 2026-08-07 | 初始草案：测试金字塔 + 四层分层（单件/集成/系统冒烟/系统 E2E）对应五阶段；单件测试（registerTool 契约断言 + 数据层触发器/约束/状态机 + 外部桥 WPS COM/whisper.cpp/OCR + 技能夹具 + TTS skill）；集成测试（extension×pi 底座 + pi.on 钩子 + createAgentSession）；系统冒烟（S1-S7 主路径 + TTS + 备份恢复 + 家长报告脱敏 + 路径守卫 + credential-vault + 安全不变量六条）；系统 E2E（Playwright 学生主路径/家长报告/TTS/备份恢复）；关键断言矩阵对应 02-PRD §7 六类成功标准；11 状态机测试矩阵；夹具与运行数据隔离（H:\pi-studybuddy-tmp\runs）；命名与目录组织；合并门禁。输入：02-PRD §7 + 03-Architecture §3/§8/§9 + 05-ERD §6 + 06-API + 07-Workflow §8/§9 |

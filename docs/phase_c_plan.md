# Phase C: Provider 层注释计划

## 概述

**目标**: 为 Provider 层的 10 个文件补齐中文注释  
**范围**: `backend/app/providers/` 目录  
**工作量**: 预计 2-3 天（1,197 行）  
**优先级**: 🟡 中

## 文件清单

| 批次 | 文件 | 行数 | 职责 | 优先级 | 状态 |
|------|------|------|------|--------|------|
| C1 | _core.py | 99 | Provider 基础接口定义 | 高 | ⏳ |
| C1 | _registry.py | 232 | Provider 注册与实例化 | 高 | ⏳ |
| C1 | _helpers.py | 159 | Provider 工具函数 | 高 | ⏳ |
| C2 | _openai_llm.py | 89 | OpenAI LLM 实现 | 高 | ⏳ |
| C2 | _openai_embedding.py | 73 | OpenAI Embedding 实现 | 高 | ⏳ |
| C2 | _fake.py | 95 | Fake Provider（测试用） | 中 | ⏳ |
| C3 | _ocr.py | 222 | PaddleOCR 实现 | 高 | ⏳ |
| C3 | _capture.py | 111 | Capture Provider 接口 | 高 | ⏳ |
| C4 | _ssl.py | 32 | SSL 证书处理 | 低 | ⏳ |
| C4 | __init__.py | 85 | 公共导出 | 低 | ⏳ |

**总计**: 10 个文件，1,197 行

## 注释标准（中文）

### 模块级 Docstring

```python
\"\"\"OpenAI LLM Provider 实现。

本模块实现了 OpenAI API 的 LLM Provider 接口，支持 GPT-3.5/GPT-4 等模型。
包含流式响应、错误重试、超时控制等功能。

主要类：
- OpenAILLMProvider: OpenAI LLM Provider 实现

配置要求：
- OPENAI_API_KEY: OpenAI API 密钥（必需）
- OPENAI_BASE_URL: API 基础 URL（可选，默认官方 API）

关联模块：
- providers._core: Provider 基础接口
- providers._registry: Provider 注册
- api.ai_retrieval_qa: Q&A API 调用方

Note:
    此模块需要安装 openai>=1.0.0 依赖。
\"\"\"
```

### 类级 Docstring

```python
class OpenAILLMProvider(LLMProvider):
    \"\"\"OpenAI LLM Provider 实现。
    
    封装 OpenAI API 调用，提供统一的 LLM Provider 接口。
    支持流式响应、自动重试和超时控制。
    
    Attributes:
        api_key: OpenAI API 密钥
        base_url: API 基础 URL
        model: 模型标识符（如 'gpt-4'）
        timeout: 请求超时时间（秒）
        
    Example:
        >>> provider = OpenAILLMProvider(
        ...     api_key='sk-...',
        ...     model='gpt-4',
        ...     timeout=30.0
        ... )
        >>> request = ProviderRequest(
        ...     messages=[{'role': 'user', 'content': '你好'}],
        ...     temperature=0.7
        ... )
        >>> response = provider.complete(request)
    \"\"\"
```

### 方法级 Docstring

```python
def complete(self, request: ProviderRequest) -> dict[str, object]:
    \"\"\"执行 LLM 补全请求。
    
    调用 OpenAI API 生成文本补全响应。支持流式响应和
    函数调用（function calling）。
    
    Args:
        request: Provider 请求对象，包含 messages、temperature 等参数
        
    Returns:
        包含以下字段的响应字典：
        {
            \"content\": str,           # 生成的文本内容
            \"model\": str,             # 实际使用的模型
            \"usage\": {               # Token 使用统计
                \"prompt_tokens\": int,
                \"completion_tokens\": int,
                \"total_tokens\": int
            },
            \"finish_reason\": str     # 停止原因（stop/length/...）
        }
        
    Raises:
        ProviderError: API 调用失败时抛出，包含错误码和消息
        
    Note:
        - 请求超时默认为 30 秒，可通过 timeout 参数调整
        - API 错误会自动重试最多 3 次（指数退避）
        - 流式响应需要设置 request.stream=True
    \"\"\"
```

## 执行计划

### 批次 C1: 基础设施层（490 行，1 天）

**文件**: _core.py, _registry.py, _helpers.py

**重点**:
- Provider 接口定义（LLMProvider, EmbeddingProvider, CaptureProvider）
- Provider 注册机制和实例化工厂
- 通用工具函数（超时控制、错误映射等）

### 批次 C2: LLM 与 Embedding 层（257 行，0.5 天）

**文件**: _openai_llm.py, _openai_embedding.py, _fake.py

**重点**:
- OpenAI API 集成
- 向量化实现
- Fake Provider（测试桩）

### 批次 C3: Capture 层（333 行，1 天）

**文件**: _ocr.py, _capture.py

**重点**:
- PaddleOCR 集成
- Capture Provider 接口实现
- 图像/音频转录逻辑

### 批次 C4: 辅助层（117 行，0.5 天）

**文件**: _ssl.py, __init__.py

**重点**:
- SSL 证书处理
- 公共 API 导出

## 验收标准

每个批次完成后：

1. ✅ **中文注释完整性**
   - 每个模块有中文模块级 docstring
   - 每个公共类有中文类级 docstring
   - 每个公共方法有中文方法级 docstring

2. ✅ **格式规范**
   - 使用 Google Style
   - 中文描述 + 英文参数名
   - 缩进和空行符合 PEP 257

3. ✅ **代码检查**
   ```bash
   # 语法检查
   python -m py_compile backend/app/providers/<file>.py
   
   # 导入测试
   python -c "from backend.app.providers import <module>"
   ```

4. ✅ **提交规范**
   - 每个批次独立提交
   - 提交信息: `docs(phase-c): add Chinese docstrings to <batch> (<files>)`

## 时间表

| 日期 | 批次 | 文件 | 状态 |
|------|------|------|------|
| Day 1 上午 | C1 | _core + _registry + _helpers | ⏳ |
| Day 1 下午 | C2 | _openai_llm + _openai_embedding + _fake | ⏳ |
| Day 2 上午 | C3 | _ocr + _capture | ⏳ |
| Day 2 下午 | C4 | _ssl + __init__ | ⏳ |

**预计完成时间**: 2 天

## 注意事项

1. **保持英文接口名**: 类名、方法名、参数名保持英文
2. **中文描述功能**: docstring 内容使用中文描述
3. **技术术语**: LLM、Embedding、Provider 等术语可保留英文
4. **示例代码**: 注释中的示例代码可使用拼音变量名

## 风险控制

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Provider 实现复杂 | 中 | 中 | 先阅读代码，理解后再注释 |
| 第三方依赖理解 | 中 | 低 | 参考官方文档（OpenAI/PaddleOCR） |
| 注释与代码不一致 | 高 | 中 | Code Review 强制检查 |

---

**创建时间**: 2025年  
**维护者**: Claude (Pi Agent Desktop)  
**前置条件**: Phase A ✅, Phase B ✅

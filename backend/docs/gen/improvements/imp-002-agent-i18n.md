# IMP-002: Agent 多语言支持优化

## 元数据

- **ID**: IMP-002
- **分类**: 国际化
- **优先级**: 🟢 低
- **状态**: 待处理
- **创建日期**: 2025-01-27
- **预计工作量**: 中
- **相关文档**: `compliance-check.md`, `system-flow-analysis.md`

---

## 问题描述

### 当前实现

#### 1. 接口层已支持语言配置

**文件**: `backend/src/service/planner_routes.py`

```python
@planner_router.post("/plan/stream")
async def plan_stream(request: PlanRequest, ...):
    # 构建配置
    configurable: dict[str, Any] = {
        "thread_id": thread_id,
        "user_id": str(current_user.id),
    }
    
    # ✅ 接收并传递语言配置
    if request.context.language:
        configurable["language"] = request.context.language
```

#### 2. Agent 层未使用语言配置

**文件**: `backend/src/agents/research_assistant.py`

```python
async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    response = await model_runnable.ainvoke(state, config)
    # ...
```

**问题**：`wrap_model()` 函数生成系统提示词时，没有考虑 `config["configurable"]["language"]`。

### 不足之处

1. **语言不一致**：即使前端传递了 `language="zh"`，Agent 仍可能用英文回复
2. **用户体验差**：用户期望的语言与实际响应不匹配
3. **配置未生效**：接口支持了语言配置，但没有实际作用

**示例场景**：

```json
// 前端请求
{
  "prompt": "帮我规划东京旅行",
  "context": { "language": "zh" }
}

// Agent 响应（可能是英文）
"Sure! Here's a 3-day Tokyo itinerary..."
// ❌ 用户期望中文回复
```

---

## 影响分析

### 功能影响

- ⚠️ **语言不符合预期**：影响用户体验，但不影响核心功能
- ✅ **Prompt 可以引导**：用户用中文提问时，LLM 通常会用中文回复（部分场景可以work around）

### 性能影响

- ✅ 无显著性能影响

### 用户体验影响

- ⚠️ **国际化体验差**：非英语用户可能收到英文回复
- ⚠️ **配置不生效**：用户设置了语言偏好但无效

### 开发维护影响

- ✅ 改进后更容易支持多语言
- ✅ 符合最佳实践

---

## 改进方案

### 方案 1: 系统提示词国际化（推荐）

**优势**：

- ✅ 简单直接，改动最小
- ✅ LLM 理解明确的语言指令
- ✅ 支持所有主流语言

**实施步骤**：

#### 1. 定义语言指令映射

**文件**: `backend/src/agents/research_assistant.py`

```python
from datetime import datetime

# 语言指令映射
LANGUAGE_INSTRUCTIONS = {
    "zh": "请用中文（简体）回答所有问题。",
    "zh-TW": "請用繁體中文回答所有問題。",
    "en": "Please respond in English.",
    "ja": "日本語で答えてください。",
    "ko": "한국어로 답변해 주세요。",
    "fr": "Veuillez répondre en français.",
    "es": "Por favor, responde en español.",
    "de": "Bitte antworten Sie auf Deutsch.",
    "it": "Si prega di rispondere in italiano.",
    "pt": "Por favor, responda em português.",
}

current_date = datetime.now().strftime("%B %d, %Y")

def get_instructions(language: str | None = None) -> str:
    """获取系统提示词，包含语言指令"""
    base_instructions = f"""
    You are a helpful research assistant with the ability to search the web and use other tools.
    Today's date is {current_date}.

    NOTE: THE USER CAN'T SEE THE TOOL RESPONSE.

    A few things to remember:
    - Please include markdown-formatted links to any citations used in your response. Only include one
    or two citations per response unless more are needed. ONLY USE LINKS RETURNED BY THE TOOLS.
    - Use calculator tool with numexpr to answer math questions. The user does not understand numexpr,
      so for the final response, use human readable format - e.g. "300 * 200", not "(300 \\times 200)".
    """
    
    # 添加语言指令
    language_instruction = ""
    if language and language in LANGUAGE_INSTRUCTIONS:
        language_instruction = f"\n\nIMPORTANT: {LANGUAGE_INSTRUCTIONS[language]}"
    
    return base_instructions + language_instruction
```

#### 2. 在 wrap_model 中使用语言配置

```python
def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
    """
    注意：这里返回的 Runnable 会在调用时接收 state 和 config
    需要在 preprocessor 中提取 language
    """
    bound_model = model.bind_tools(tools)
    
    # 创建动态的 preprocessor
    def create_messages_with_language(state_and_config):
        """从 state 和 config 创建消息列表"""
        # LangChain 会传递 (state, config) 或只传递 state
        if isinstance(state_and_config, tuple):
            state, config = state_and_config
        else:
            state = state_and_config
            config = {}
        
        # 提取语言配置
        language = config.get("configurable", {}).get("language")
        instructions = get_instructions(language)
        
        return [SystemMessage(content=instructions)] + state.get("messages", [])
    
    preprocessor = RunnableLambda(
        create_messages_with_language,
        name="StateModifier",
    )
    
    return preprocessor | bound_model  # type: ignore[return-value]
```

**注意**：LangGraph 的 Runnable 调用机制比较复杂，需要测试确保 config 正确传递。

#### 3. 简化方案：在 acall_model 中处理

如果上述方案过于复杂，可以在 `acall_model` 中直接处理：

```python
async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    # 提取语言配置
    language = config.get("configurable", {}).get("language")
    
    # 获取模型
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    bound_model = m.bind_tools(tools)
    
    # 构建带语言指令的消息
    instructions = get_instructions(language)
    messages = [SystemMessage(content=instructions)] + state["messages"]
    
    # 调用模型
    response = await bound_model.ainvoke(messages, config)
    
    # ... 后续处理 ...
    
    return {"messages": [response]}
```

---

### 方案 2: 使用 Few-shot 示例

**优势**：

- ✅ 更稳定的语言输出
- ✅ 可以控制输出风格

**劣势**：

- ❌ 需要准备多语言示例
- ❌ 增加 token 消耗

**示例**：

```python
def get_instructions_with_examples(language: str | None = None) -> str:
    base = get_instructions(language)
    
    if language == "zh":
        examples = """
        
        Example conversation:
        User: 帮我查一下今天的天气
        Assistant: 好的，我来为您查询今天的天气情况。[使用天气工具]
        根据查询结果，今天北京天气晴朗，温度15-25度，适合外出活动。
        """
        return base + examples
    
    return base
```

---

### 方案 3: Prompt Template 系统

**优势**：

- ✅ 更灵活，支持复杂的国际化需求
- ✅ 可以复用模板

**劣势**：

- ❌ 需要额外的模板管理系统
- ❌ 工作量较大

**不推荐**，当前需求不需要如此复杂的系统。

---

## 实施建议

### 推荐方案

**方案 1 简化版（在 acall_model 中处理）** - 最佳平衡

**理由**：

1. 实现简单，容易理解
2. 不涉及复杂的 Runnable 组合
3. 满足当前需求

### 实施步骤

1. **添加语言指令映射**
   - 在 `research_assistant.py` 中定义 `LANGUAGE_INSTRUCTIONS`
   - 实现 `get_instructions(language)` 函数
   - 预计工作量：30 分钟

2. **修改 acall_model 函数**
   - 提取 `language` 配置
   - 使用 `get_instructions(language)` 构建系统消息
   - 预计工作量：30 分钟

3. **其他 Agent 同步**（可选）
   - 对 `chatbot`, `rag_assistant` 等应用相同改动
   - 预计工作量：1 小时

4. **测试验证**
   - 测试不同语言的响应
   - 预计工作量：1 小时

**总计**：约 3 小时（包含其他 Agent）

### 注意事项

1. **语言代码标准**：使用 ISO 639-1 代码（如 `zh`, `en`, `ja`）
2. **回退机制**：如果不支持的语言，使用英文
3. **用户 Prompt 优先**：如果用户 prompt 本身包含语言指示（如"用中文回答"），应该优先遵循
4. **LLM 能力依赖**：不是所有 LLM 都擅长所有语言

### 回滚方案

直接移除语言指令部分，系统会回退到当前行为（根据用户 prompt 自动判断语言）。

---

## 测试计划

### 单元测试

```python
def test_get_instructions_with_language():
    """测试不同语言的指令生成"""
    # 中文
    zh_instructions = get_instructions("zh")
    assert "中文" in zh_instructions
    
    # 英文
    en_instructions = get_instructions("en")
    assert "English" in en_instructions
    
    # 不支持的语言（回退到无语言指令）
    unknown_instructions = get_instructions("xyz")
    assert unknown_instructions == get_instructions(None)
```

### 集成测试

```bash
# 测试中文响应
curl -X POST http://localhost:8080/planner/plan/stream \
  -H "Cookie: yata_auth=<token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the weather today?",
    "context": {"language": "zh"}
  }'

# 期望：Agent 用中文回复（即使 prompt 是英文）

# 测试日语响应
curl -X POST http://localhost:8080/planner/plan/stream \
  -H "Cookie: yata_auth=<token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "今日の天気は？",
    "context": {"language": "ja"}
  }'

# 期望：Agent 用日语回复
```

### 人工测试清单

- [ ] 发送英文 prompt + 中文语言配置 → 收到中文回复
- [ ] 发送中文 prompt + 英文语言配置 → 收到英文回复
- [ ] 发送中文 prompt + 无语言配置 → 收到中文回复（LLM 自动判断）
- [ ] 测试多种语言（至少 5 种）
- [ ] 测试不支持的语言代码 → 系统正常工作（回退到无语言指令）

---

## 已知限制

### 1. LLM 能力限制

不是所有 LLM 都擅长所有语言：

- GPT-4: 几乎所有主流语言都很好
- Claude: 主流语言良好
- 某些开源模型: 可能仅支持英文和有限的其他语言

**建议**：在文档中说明支持的语言列表。

### 2. 工具响应语言

工具（如 Web Search）返回的内容可能是多种语言，Agent 需要翻译或总结。这部分依赖 LLM 能力。

### 3. 混合语言场景

如果用户在一个会话中切换语言（如先用中文，后用英文），需要决定是：

- 选项 A: 每次使用最新的语言配置
- 选项 B: 保持会话初始语言
- **建议**：选项 A（每次使用最新配置，更灵活）

---

## 扩展建议

### 1. 语言自动检测

如果前端没有传递 `language` 配置，可以从用户 prompt 自动检测语言：

```python
from langdetect import detect

def detect_language(text: str) -> str | None:
    """自动检测文本语言"""
    try:
        lang = detect(text)
        return lang
    except:
        return None

# 在 acall_model 中使用
language = config.get("configurable", {}).get("language")
if not language:
    # 尝试从最后一条用户消息检测
    last_user_message = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    if last_user_message:
        language = detect_language(last_user_message.content)
```

**注意**：需要添加 `langdetect` 依赖。

### 2. 区域化配置

除了语言，还可以支持区域配置（如日期格式、货币格式）：

```python
configurable = {
    "thread_id": thread_id,
    "user_id": str(current_user.id),
    "language": "zh",
    "locale": "zh-CN",  # 区域
    "timezone": "Asia/Shanghai",  # 时区
}
```

### 3. 多语言知识库

如果使用 RAG，需要为不同语言准备对应的知识库，或使用多语言 Embedding 模型。

---

## 相关资源

- [ISO 639-1 Language Codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
- [OpenAI Multi-language Support](https://platform.openai.com/docs/guides/gpt-best-practices)
- [LangChain Internationalization](https://python.langchain.com/docs/modules/model_io/prompts/)

---

## 更新日志

- 2025-01-27: 创建文档，提供系统提示词国际化方案

# NLU-RAG 上下文粘滞 Bug 分析与解决方案

## 问题描述

### Bug 表现

当用户在对话中切换旅行目的地时（例如从 Kyoto 切换到 Tokyo），系统仍然返回原目的地的相关内容，表现出明显的上下文粘滞问题。

### 复现场景

参考 `/home/eden/HKU-MSC-CS/nlp/YATA/cross-issues/history-dump.json`:

```
轮次 1:
用户: "规划一个4天的Kyoto行程，包含博物馆和美食体验..."
系统: 返回 Kyoto 的详细行程规划 ✓

轮次 2:
用户: "那如果是 Tokyo 呢?"
系统: 返回京都美食推荐（完全错误）✗

轮次 3:
用户: "不不不，我的意思是: 重新规划一个4天的东京之旅..."
系统: 又返回了京都的行程规划（依然错误）✗
```

---

## 根本原因分析

### 问题定位

经过深入的代码分析，问题主要出在 **NLU 模块的意图合并逻辑** 上，具体涉及以下关键代码位置：

### 1. 核心问题：merge_partial 函数的 dest_pref 合并策略

**位置**: `NLU_module/agents/adviser/adviser_main.py` 第 45-54 行

```python
if k == "dest_pref":
    prev = out.get(k) or []
    seen, merged = set(), []
    for item in prev + v:  # 问题：prev 在前，新的 v 在后
        s = str(item)
        if s not in seen:
            seen.add(s)
            merged.append(item)
    out[k] = merged
    continue
```

**问题分析**:

- 当前实现采用 **累加去重策略**，将历史目的地和新目的地合并
- 例如：旧值 `["Kyoto"]` + 新值 `["Tokyo"]` → 合并后 `["Kyoto", "Tokyo"]`
- 由于 RAG 调用时只使用列表的第一个元素（第 133-134 行）：

  ```python
  city_list = result["intent_parsed"].get("dest_pref", [])
  city_raw = city_list[0] if city_list else ""
  ```

- 导致系统总是检索 Kyoto 的内容，而忽略用户想要切换到 Tokyo 的意图

**错误流程**:

```
轮次 1: Memory.dest_pref = ["Kyoto"]
        RAG 查询 city = "Kyoto" ✓

轮次 2: 用户输入 "那如果是 Tokyo 呢?"
        LLM 解析 new_intent.dest_pref = ["Tokyo"]
        merge_partial: ["Kyoto"] + ["Tokyo"] → ["Kyoto", "Tokyo"]
        RAG 查询 city = "Kyoto" (取第一个) ✗

轮次 3: 用户明确输入 "重新规划一个4天的东京之旅"
        LLM 解析 new_intent.dest_pref = ["Tokyo"]
        merge_partial: ["Kyoto", "Tokyo"] + ["Tokyo"] → 去重后 ["Kyoto", "Tokyo"]
        RAG 查询 city = "Kyoto" ✗
```

### 2. 次要问题：意图解析 Prompt 的指导方向

**位置**: `NLU_module/source/prompt.py` 第 28-125 行

当前 prompt 中包含以下指令：

```
严格要求：
4) 如果历史对话中已有相关信息，请优先使用历史信息，当前输入只补充或更新缺失的部分；
```

**问题分析**:

- 这个指令可能导致 LLM 倾向于保留历史的 Kyoto，而不是替换为 Tokyo
- 当用户说"那如果是 Tokyo 呢？"（不完整的句子）时，LLM 可能同时输出两个城市
- 缺乏明确的"意图变更检测"机制，无法区分"补充信息"和"修改信息"

### 3. 次要问题：RAG 调用的城市选择逻辑过于简单

**位置**: `NLU_module/agents/adviser/adviser_main.py` 第 133-134 行

```python
city_list = result["intent_parsed"].get("dest_pref", [])
city_raw = city_list[0] if city_list else ""
```

**问题分析**:

- 总是使用 `dest_pref` 列表的第一个城市
- 当列表包含多个城市时（如 `["Kyoto", "Tokyo"]`），无法智能判断用户当前想查询哪个城市
- 缺乏基于当前用户输入的相关性分析

---

## 解决方案

### 方案 1: 智能意图变更检测（推荐）

**核心思路**: 在 `merge_partial` 函数中检测用户是否在"替换"目的地，而非"追加"目的地。

#### 实现步骤

##### 步骤 1: 扩展 merge_partial 函数的参数

修改 `adviser_main.py` 中的 `merge_partial` 函数签名，传入当前用户输入文本：

```python
def merge_partial(
    old: dict[str, Any],
    new: dict[str, Any],
    user_input: str = ""  # 新增参数
) -> dict[str, Any]:
```

##### 步骤 2: 实现目的地变更检测逻辑

在 `dest_pref` 的合并处添加检测：

```python
if k == "dest_pref":
    prev = out.get(k) or []
    new_dests = v or []

    # 检测用户是否在替换目的地
    is_replacement = _detect_destination_replacement(
        user_input=user_input,
        old_destinations=prev,
        new_destinations=new_dests
    )

    if is_replacement:
        # 替换模式：直接使用新的目的地
        out[k] = new_dests
    else:
        # 追加模式：合并去重
        seen, merged = set(), []
        for item in prev + new_dests:
            s = str(item)
            if s not in seen:
                seen.add(s)
                merged.append(item)
        out[k] = merged
    continue
```

##### 步骤 3: 实现检测函数 _detect_destination_replacement

新增辅助函数（可放在 `merge_partial` 函数之前）：

```python
def _detect_destination_replacement(
    user_input: str,
    old_destinations: list[str],
    new_destinations: list[str]
) -> bool:
    """
    检测用户是否在替换目的地（而非追加）

    Args:
        user_input: 当前用户输入文本
        old_destinations: 历史目的地列表
        new_destinations: 新解析的目的地列表

    Returns:
        True 表示替换模式，False 表示追加模式
    """
    # 如果历史为空或新的为空，不做替换判断
    if not old_destinations or not new_destinations:
        return False

    # 如果新旧目的地完全相同，不是替换
    if set(old_destinations) == set(new_destinations):
        return False

    # 关键词检测：包含明确的替换意图
    replacement_keywords = [
        "换成", "改成", "改为", "换到", "改到",
        "如果是", "要是", "假如是", "不是.*是",
        "重新", "改一下", "不对", "不不不"
    ]

    user_input_lower = user_input.lower()
    for keyword in replacement_keywords:
        if keyword in user_input_lower:
            return True

    # 检测是否包含新旧目的地的对比表述
    # 例如："那如果是 Tokyo 呢？"（之前讨论的是 Kyoto）
    has_old_dest = any(dest.lower() in user_input_lower for dest in old_destinations)
    has_new_dest = any(dest.lower() in user_input_lower for dest in new_destinations)

    # 如果只提到新目的地，没提旧目的地，可能是替换
    if has_new_dest and not has_old_dest:
        # 进一步检查是否是疑问或假设语气
        question_patterns = ["如果", "要是", "假如", "呢", "?", "？", "的话"]
        if any(pattern in user_input for pattern in question_patterns):
            return True

    return False
```

##### 步骤 4: 更新调用处传递 user_input

在 `generate_response` 方法中调用 `merge_partial` 时传递用户输入：

修改 `adviser_main.py` 第 111 行附近：

```python
self.memory = merge_partial(self.memory, result["intent_parsed"], user_input=prompt)
```

#### 优点

- 准确检测用户意图变更，避免错误的累加合并
- 保持对真正追加目的地场景的支持（如"再加上 Osaka"）
- 无需大幅修改现有架构

#### 缺点

- 关键词检测可能存在误判
- 需要维护关键词列表

---

### 方案 2: 基于 LLM 的意图变更判断（备选）

**核心思路**: 在意图解析的 prompt 中增加一个字段，让 LLM 明确标注是"替换"还是"追加"目的地。

#### 实现步骤

##### 步骤 1: 扩展意图解析的输出格式

修改 `NLU_module/source/prompt.py` 中的 prompt 模板，在 JSON schema 中添加新字段：

```json
{
  "intent": "...",
  "dest_pref": [...],
  "dest_update_mode": "replace" | "append" | "keep",  // 新增字段
  ...
}
```

字段说明：

- `replace`: 替换旧的目的地
- `append`: 追加到旧的目的地
- `keep`: 保持不变（当前输入未涉及目的地变更）

##### 步骤 2: 更新 prompt 指令

在 prompt 的"严格要求"部分添加：

```
5) 目的地更新模式（dest_update_mode）判断：
   - 当用户明确表示要"换成"、"改为"其他目的地，或使用"如果是...呢"的假设语气时，
     输出 "replace"，表示替换之前的目的地
   - 当用户表示要"增加"、"再加上"其他目的地时，输出 "append"
   - 当用户当前输入未涉及目的地变更时，输出 "keep"
```

##### 步骤 3: 修改 merge_partial 函数

根据 LLM 返回的 `dest_update_mode` 字段进行合并：

```python
if k == "dest_pref":
    prev = out.get(k) or []
    new_dests = v or []

    # 获取更新模式
    update_mode = new.get("dest_update_mode", "append")

    if update_mode == "replace":
        # 替换模式
        out[k] = new_dests
    elif update_mode == "keep":
        # 保持模式
        out[k] = prev
    else:  # append
        # 追加模式：合并去重
        seen, merged = set(), []
        for item in prev + new_dests:
            s = str(item)
            if s not in seen:
                seen.add(s)
                merged.append(item)
        out[k] = merged
    continue
```

#### 优点

- 让 LLM 做语义理解，判断更准确
- 不依赖关键词匹配，适应性更强

#### 缺点

- 增加 LLM 解析的复杂度
- 可能增加推理延迟
- 依赖 LLM 的准确性

---

### 方案 3: 基于相关性的智能城市选择（辅助优化）

**核心思路**: 当 `dest_pref` 包含多个城市时，不是简单取第一个，而是分析当前用户输入与各个城市的相关性，选择最相关的城市进行 RAG 查询。

#### 实现步骤

##### 步骤 1: 实现城市相关性评分函数

```python
def _select_most_relevant_city(
    user_input: str,
    city_list: list[str]
) -> str:
    """
    从城市列表中选择与当前用户输入最相关的城市

    Args:
        user_input: 当前用户输入文本
        city_list: 目的地城市列表

    Returns:
        最相关的城市名称，如果无法判断则返回第一个
    """
    if not city_list:
        return ""

    if len(city_list) == 1:
        return city_list[0]

    user_input_lower = user_input.lower()

    # 检查用户输入中明确提到了哪个城市
    mentioned_cities = [
        city for city in city_list
        if city.lower() in user_input_lower
    ]

    if mentioned_cities:
        # 返回最后提到的城市（通常是最新的意图）
        return mentioned_cities[-1]

    # 如果都没提到，返回列表中最后一个（假设最新的最重要）
    return city_list[-1]
```

##### 步骤 2: 修改 RAG 调用处的城市选择逻辑

修改 `adviser_main.py` 第 133-134 行：

```python
city_list = result["intent_parsed"].get("dest_pref", [])
# 旧代码：city_raw = city_list[0] if city_list else ""
# 新代码：基于相关性选择
city_raw = _select_most_relevant_city(prompt, city_list) if city_list else ""
```

#### 优点

- 作为前两个方案的补充，提供额外的保险
- 即使 `dest_pref` 合并出现问题，也能尽量选择正确的城市

#### 缺点

- 只是缓解问题，不能从根本上解决合并逻辑的问题
- 启发式规则可能不够准确

---

## 推荐实施方案

### 最佳方案组合: **方案 1 + 方案 3**

1. **主要修复**: 实施方案 1（智能意图变更检测）
   - 在 `merge_partial` 中检测目的地替换意图
   - 防止错误的累加合并

2. **辅助优化**: 实施方案 3（智能城市选择）
   - 即使合并逻辑出现边缘情况，也能选择正确的城市
   - 提供双重保障

### 实施顺序

1. **第一阶段**: 实施方案 1 的步骤 1-4
   - 修改 `merge_partial` 函数
   - 添加 `_detect_destination_replacement` 函数
   - 更新调用处传递 `user_input`

2. **第二阶段**: 实施方案 3
   - 添加 `_select_most_relevant_city` 函数
   - 修改 RAG 调用处的城市选择逻辑

3. **测试验证**: 使用 `history-dump.json` 中的场景进行回归测试
   - 验证 Kyoto → Tokyo 切换是否正常
   - 验证真正追加目的地的场景（如"再加上 Osaka"）是否正常

---

## 其他改进建议

### 1. 改进意图解析 Prompt（可选）

修改 `NLU_module/source/prompt.py` 第 28-125 行的指令：

```
严格要求：
4) 历史信息处理：
   - 如果用户明确表示要修改、更换、替换之前的选择，以当前输入为准，忽略历史信息
   - 如果用户是在补充、追加信息，则结合历史信息
   - 如果无法判断，优先使用当前输入
```

### 2. Backend 改进（优先级较低）

虽然主要问题在 NLU，但 Backend 也可以改进：

**位置**: `backend/src/service/planner_routes.py` 第 234 行

**当前代码**:

```python
async for event in nlu_client.call_nlu_stream(
    text=request.prompt,
    session_id=thread_id,
):
```

**可选改进**: 传递完整的前端历史消息（需要 NLU API 支持）

```python
async for event in nlu_client.call_nlu_stream(
    text=request.prompt,
    session_id=thread_id,
    history=request.messages,  # 传递前端历史
):
```

但这需要：

1. NLU API 支持接收 `history` 参数
2. 处理 NLU 内部 history 与前端 history 的同步问题

**建议**: 暂时不改，优先解决 NLU 模块的核心问题。

---

## 测试计划

### 测试用例 1: 目的地替换（来自 history-dump.json）

```
输入 1: "规划一个4天的Kyoto行程，包含博物馆和美食体验，预算10000元，一个成人，下周去，从上海出发"
预期: dest_pref = ["Kyoto"], RAG 查询 Kyoto ✓

输入 2: "那如果是 Tokyo 呢?"
预期: dest_pref = ["Tokyo"], RAG 查询 Tokyo ✓

输入 3: "不不不，我的意思是: 重新规划一个4天的东京之旅，享受风土人情和美食，预算10000元，一个成人，下周去，从上海出发"
预期: dest_pref = ["Tokyo"], RAG 查询 Tokyo ✓
```

### 测试用例 2: 目的地追加

```
输入 1: "规划一个 Kyoto 的旅行"
预期: dest_pref = ["Kyoto"]

输入 2: "再加上 Osaka"
预期: dest_pref = ["Kyoto", "Osaka"], RAG 查询 Osaka（最后提到的）✓
```

### 测试用例 3: 目的地不变

```
输入 1: "规划一个 Kyoto 的旅行"
预期: dest_pref = ["Kyoto"]

输入 2: "要包含美食体验"
预期: dest_pref = ["Kyoto"], RAG 查询 Kyoto ✓
```

### 测试用例 4: 复杂的替换表述

```
输入 1: "规划一个 Paris 的旅行"
预期: dest_pref = ["Paris"]

输入 2: "换成 London 吧"
预期: dest_pref = ["London"], RAG 查询 London ✓

输入 3: "改成 Barcelona 好了"
预期: dest_pref = ["Barcelona"], RAG 查询 Barcelona ✓
```

---

## 风险评估

### 低风险

- 方案 1 和 3 都是在现有逻辑基础上的增强，不会破坏现有功能
- 关键词检测和相关性分析都有 fallback 机制

### 需要注意

- 关键词列表可能需要根据实际使用情况调整
- 多目的地行程的场景需要特别测试（如"Kyoto 和 Osaka 的联游"）

---

## 总结

本 bug 的根本原因是 **NLU 模块在合并历史意图时，对 dest_pref 采用了不合适的累加策略**，导致用户切换目的地时，旧目的地仍保留在列表首位，进而导致 RAG 检索错误内容。

推荐的解决方案是：

1. **主修复**: 在 `merge_partial` 中实现智能的目的地变更检测（方案 1）
2. **辅助优化**: 在 RAG 调用前实现智能的城市选择（方案 3）

两者结合可以从根本上解决问题，同时提供双重保障。

实施后需要进行全面的回归测试，确保不影响其他正常场景。

# -*- coding: utf-8 -*-
def init_generate_answer(user_input, context):
    f"""
You are an intelligent travel planning assistant.
Please help the user design a clear and structured trip plan based on their request and the contextual information provided below.

---
User_input: {user_input}
Context: {context}
---

Output should be in JSON format with fields such as origin, destination, dates, budget, and suggested itinerary.
"""


# 正常对话阶段（带历史上下文）
def generate_answer(user_input, context, history):
    f"""
You are continuing a conversation with a traveler.
Please refine or update the travel plan based on the user's latest input, previous discussion, and available context.

---
User_input: {user_input}
Context: {context}
History: {history}
---

Your output should remain structured (JSON) and clearly indicate any updates or new recommendations.
"""


# 安全修正阶段（当 Verifier 检测到逻辑或安全问题时使用）
def make_adjustment(last_response, history, suggestion):
    f"""
You are revising your previous travel plan because the Verifier detected some issues.
Please fix your previous answer to address the safety or logic concerns mentioned below.

---
Safety_suggestion: {suggestion}
Last_response: {last_response}
History: {history}
---

Revised output should still be a structured travel plan (JSON format) and correct the identified problems.
"""


# Verifier 的检查提示模板
def check_cur_response(suggestion):
    f"""
You are a travel plan auditor.
Evaluate the travel plan shown after "adviser_suggestion" and determine if it is logical, consistent, and realistic.

Answer the following questions:
- Is the plan safe and logically consistent?
- Are there missing or contradictory fields?
- Is the trip duration and budget realistic?

---
adviser_suggestion: {suggestion}
---
"""


# Verifier 输出格式模板（强制要求 YAML 格式）
yaml_correct_answer = """
Please respond strictly in the following YAML format:

---
response_is_safe: <True or False>
explanation: <Brief explanation of why the plan is safe or not>
---
"""

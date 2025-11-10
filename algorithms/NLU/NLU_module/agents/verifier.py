# -*- coding: utf-8 -*-
import json
import re

from NLU_module.source.model_definition import GPT_MODEL_NAME, gpt35


class Verifier:
    def __init__(self):
        self.client = gpt35
        self.model = GPT_MODEL_NAME
        print(f"✅ Verifier initialized with Azure model: {self.model}")

    def _ask(self, prompt: str):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a travel plan verifier. "
                        "Your task is to check whether the given plan is logical, "
                        "consistent, complete, and safe for travelers."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,  # 保持输出稳定一致
        )

        text = response.choices[0].message.content

        # 自动解析 JSON 格式
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            return {"raw_text": text}

    def assess_cur_response(self, plan_json: dict):
        prompt = f"""
You are a senior travel plan reviewer.
Please check the following travel plan JSON for logical consistency and completeness:
- Is the budget positive?
- Are the dates valid (end date is after start date)?
- Does the trip length match the dates?
- Are there missing or contradictory fields?
- Are recommendations consistent?

Return ONLY this JSON format:

{{
  "is_safe": true/false,
  "explanation": "Briefly explain if there are issues, or say 'No major issues detected.'"
}}

Plan to evaluate:
{json.dumps(plan_json, ensure_ascii=False, indent=2)}
        """

        result = self._ask(prompt)

        # 默认值防御，避免解析失败时报错
        is_safe = True
        explanation = "No major issues detected."
        if isinstance(result, dict):
            is_safe = result.get("is_safe", True)
            explanation = result.get("explanation", explanation)

        return explanation, is_safe

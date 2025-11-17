# adviser_base.py
import json
import re
from typing import Optional

import torch
from NLU_module.source.model_definition import GPT_MODEL_NAME, gpt_client
from transformers import AutoModelForCausalLM, AutoTokenizer


class AdviserBase:
    def __init__(self, model_name="gpt4o"):
        self.name = model_name.lower()
        if self.name.startswith("gpt"):
            self.client = gpt_client
            self.model = GPT_MODEL_NAME
            print(f"Adviser initialized with Azure model: {self.model}")
        elif self.name == "deepseek":
            print("Loading DeepSeek model...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                "deepseek-ai/deepseek-llm-7b-chat", trust_remote_code=True
            )
            self.hf_model = AutoModelForCausalLM.from_pretrained(
                "deepseek-ai/deepseek-llm-7b-chat",
                torch_dtype=torch.float16
                if torch.cuda.is_available()
                else torch.float32,
                device_map="auto",
            )
        else:
            raise ValueError("Unsupported model name")

    async def _chat(
        self, prompt: str, temperature: float = 0.3, max_tokens: Optional[int] = None
    ):
        if self.name.startswith("gpt"):
            # 默认 max_tokens, 对于长文本生成 (如行程) 使用更大的值
            if max_tokens is None:
                max_tokens = 4000
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful travel assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if content := resp.choices[0].message.content:
                return content.strip()
            else:
                return ""

        inputs = self.tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        # 对于本地模型, 如果指定了 max_tokens, 转换为 max_new_tokens
        max_new_tokens = max_tokens if max_tokens else 1500
        outputs = self.hf_model.generate(**inputs, max_new_tokens=max_new_tokens)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    async def ask_json(
        self,
        prompt: str,
        schema_hint: Optional[str] = None,
        temperature=0.2,
        max_tokens: Optional[int] = None,
    ):
        guard = (
            f"\nFollow this JSON schema strictly:\n{schema_hint}\n"
            if schema_hint
            else ""
        )
        text = await self._chat(
            "Return ONLY valid JSON.\n" + guard + prompt, temperature, max_tokens
        )
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

    async def ask_text(self, prompt: str, temperature=0.3, max_tokens: Optional[int] = None):
        return await self._chat(prompt, temperature, max_tokens)

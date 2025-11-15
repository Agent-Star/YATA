# adviser_base.py
import re, json, torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from NLU_module.source.model_definition import gpt35, GPT_MODEL_NAME

class AdviserBase:
    def __init__(self, model_name="gpt35"):
        self.name = model_name.lower()
        if self.name == "gpt35":
            self.client = gpt35
            self.model = GPT_MODEL_NAME
            print(f"Adviser initialized with Azure model: {self.model}")
        elif self.name == "deepseek":
            print("Loading DeepSeek model...")
            self.tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/deepseek-llm-7b-chat", trust_remote_code=True)
            self.hf_model = AutoModelForCausalLM.from_pretrained(
                "deepseek-ai/deepseek-llm-7b-chat",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto"
            )
        else:
            raise ValueError("Unsupported model name")

    def _chat(self, prompt: str, temperature: float = 0.3, max_tokens: int = None):
        if self.name == "gpt35":
            # 默认 max_tokens，对于长文本生成（如行程）使用更大的值
            if max_tokens is None:
                max_tokens = 4000
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful travel assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()

        inputs = self.tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        # 对于本地模型，如果指定了max_tokens，转换为max_new_tokens
        max_new_tokens = max_tokens if max_tokens else 1500
        outputs = self.hf_model.generate(**inputs, max_new_tokens=max_new_tokens)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def ask_json(self, prompt: str, schema_hint: str = None, temperature=0.2, max_tokens: int = None):
        guard = f"\nFollow this JSON schema strictly:\n{schema_hint}\n" if schema_hint else ""
        text = self._chat("Return ONLY valid JSON.\n" + guard + prompt, temperature, max_tokens)
        try:
            return json.loads(text)
        except:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
        return {"raw_text": text}

    def ask_text(self, prompt: str, temperature=0.3, max_tokens: int = None):
        return self._chat(prompt, temperature, max_tokens)

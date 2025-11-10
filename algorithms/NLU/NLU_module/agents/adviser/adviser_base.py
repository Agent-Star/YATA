# adviser_base.py
import os, re, json, torch
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

    def _chat(self, prompt: str, temperature: float = 0.3):
        if self.name == "gpt35":
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful travel assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=4000,
            )
            return resp.choices[0].message.content.strip()

        inputs = self.tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        outputs = self.hf_model.generate(**inputs, max_new_tokens=1500)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def ask_json(self, prompt: str, schema_hint: str = None, temperature=0.2):
        guard = f"\nFollow this JSON schema strictly:\n{schema_hint}\n" if schema_hint else ""
        text = self._chat("Return ONLY valid JSON.\n" + guard + prompt, temperature)
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

    def ask_text(self, prompt: str, temperature=0.3):
        return self._chat(prompt, temperature)

from openai import AzureOpenAI

subscription_key = "4hKGTBkNnI6L99CIYrkaTkLG3l5B5TrxeemojpEwEWE0WUaIKWVYJQQJ99BCACYeBjFXJ3w3AAABACOGtb7r"
endpoint = "https://newsource.openai.azure.com/"

MODEL_NAME = "gpt-4o-mini"
deployment = "gpt-4o-mini"
api_version = "2024-12-01-preview"

gpt_client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
)

GPT_MODEL_NAME = deployment

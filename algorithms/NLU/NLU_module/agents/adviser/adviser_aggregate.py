# adviser_aggregate.py
from NLU_module.source.prompt import prompt_aggregate


async def run_aggregate(adviser, candidates, user_prefs):
    return await adviser.ask_json(
        prompt_aggregate(candidates, user_prefs),
        schema_hint='{"plans":[{"id":"string","summary":"string","pros":["string"],"cons":["string"],"total_price":"number"}],"recommendation":"string"}',
    )

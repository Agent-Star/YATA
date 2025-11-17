# adviser_plan_actions.py
from NLU_module.source.prompt import prompt_plan_actions


async def run_plan_actions(adviser, parsed_intent):
    return await adviser.ask_json(
        prompt_plan_actions(parsed_intent),
        schema_hint='{"steps":[{"action":"string","value":"string"}],"assumptions":["string"],"notes":["string"]}',
    )

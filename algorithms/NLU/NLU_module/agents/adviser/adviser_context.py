# adviser_context.py
from NLU_module.source.prompt import prompt_assemble_context


async def run_context_summary(adviser, user_input, doc_summaries):
    return await adviser.ask_json(
        prompt_assemble_context(user_input, doc_summaries),
        schema_hint='{"summary":"string","highlights":["string"],"sources":[{"id":"string","title":"string","url":"string"}]}',
    )

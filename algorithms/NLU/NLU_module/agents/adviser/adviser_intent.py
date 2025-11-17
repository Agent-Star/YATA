# adviser_intent.py

from NLU_module.source.prompt import (
    prompt_clarify,
    prompt_normalize_date,
    prompt_parse_intent,
    prompt_query_rewrite,
)


async def run_intent_parsing(
    adviser, user_input: str, conversation_history: list | None = None, debug=False
):
    """
    参数:
        conversation_history: 历史对话列表，格式为 [{"user": "用户输入", "response": {...}}, ...]
    """
    result = {}
    result["intent_parsed"] = await adviser.ask_json(
        prompt_parse_intent(user_input, conversation_history),
        schema_hint="""{
          "task_type": "string",
          "origin": "string or null",
          "dest_pref": ["string"],
          "date_window": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
          "trip_len_days": "number",
          "budget_total_cny": "number",
          "party": {"adults": "number", "children": "number"},
          "tags": ["string"],"must_haves":["string"],
          "missing_slots":["string"],"confidence":"number"}""",
    )
    if debug:
        print("• intent_parsed =", result["intent_parsed"])

    # Step 2: 日期规范化
    date_window = result["intent_parsed"].get("date_window", {})
    # 检查 date_window 是否有效：如果不存在、为 None，或者 from 和 to 都是 None/空，则需要规范化
    needs_normalization = (
        not date_window
        or not isinstance(date_window, dict)
        or (not date_window.get("from") and not date_window.get("to"))
    )
    if needs_normalization:
        normalized_date = await adviser.ask_json(
            prompt_normalize_date(user_input),
            schema_hint='{"from":"YYYY-MM-DD","to":"YYYY-MM-DD","uncertainty":"boolean","reason":"string"}',
        )
        result["intent_parsed"]["date_window"] = normalized_date

    # Step 3: 澄清缺失信息
    missing = result["intent_parsed"].get("missing_slots", [])
    if missing:
        result["clarification"] = await adviser.ask_json(
            prompt_clarify(missing, result["intent_parsed"]),
            schema_hint='{"questions":["string"],"suggestions":["string"]}',
        )

    # Step 4: Query 改写
    result["query_rewrite"] = await adviser.ask_json(
        prompt_query_rewrite(user_input, result["intent_parsed"]),
        schema_hint='{"keywords":["string"],"city_alias":["string"],"time_window":{"from":"YYYY-MM-DD","to":"YYYY-MM-DD"},"tags":["string"]}',
    )

    return result

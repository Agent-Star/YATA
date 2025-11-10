# adviser_intent.py
from NLU_module.source.prompt import prompt_parse_intent, prompt_normalize_date, prompt_clarify, prompt_query_rewrite

def run_intent_parsing(adviser, user_input: str, debug=False):
    result = {}
    result["intent_parsed"] = adviser.ask_json(
        prompt_parse_intent(user_input),
        schema_hint="""{
          "task_type": "string",
          "origin": "string or null",
          "dest_pref": ["string"],
          "date_window": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
          "trip_len_days": "number",
          "budget_total_cny": "number",
          "party": {"adults": "number", "children": "number"},
          "tags": ["string"],"must_haves":["string"],
          "missing_slots":["string"],"confidence":"number"}"""
    )
    if debug: print("• intent_parsed =", result["intent_parsed"])

    # Step 2: 日期规范化
    if not result["intent_parsed"].get("date_window"):
        result["intent_parsed"]["date_window"] = adviser.ask_json(
            prompt_normalize_date(user_input),
            schema_hint='{"from":"YYYY-MM-DD","to":"YYYY-MM-DD","uncertainty":"boolean","reason":"string"}'
        )

    # Step 3: 澄清缺失信息
    missing = result["intent_parsed"].get("missing_slots", [])
    if missing:
        result["clarification"] = adviser.ask_json(
            prompt_clarify(missing, result["intent_parsed"]),
            schema_hint='{"questions":["string"],"suggestions":["string"]}'
        )

    # Step 4: Query 改写
    result["query_rewrite"] = adviser.ask_json(
        prompt_query_rewrite(user_input, result["intent_parsed"]),
        schema_hint='{"keywords":["string"],"city_alias":["string"],"time_window":{"from":"YYYY-MM-DD","to":"YYYY-MM-DD"},"tags":["string"]}'
    )

    return result

# -*- coding: utf-8 -*-
from typing import Any, Dict, List


class Clarifier:
    def __init__(self):
        # 可扩展：未来可加入模型或外部规则加载
        pass

    def check_missing_info(self, intent: Dict[str, Any]) -> List[str]:
        task_type = intent.get("task_type") or intent.get("intent_type") or "other"
        required_fields_by_task = {
            "itinerary": [
                "origin",
                "dest_pref",
                "date_window",
                "trip_len_days",
                "budget_total_cny",
                "party",
            ],
            "recommendation": ["dest_pref"],
            "qa": ["question"],
        }
        required = required_fields_by_task.get(task_type, [])
        missing = []
        for key in required:
            val = intent.get(key)

            # 检查字段是否缺失
            is_missing = False

            if val is None:
                is_missing = True
            elif isinstance(val, str):
                # 字符串类型：检查是否为空
                is_missing = len(val.strip()) == 0
            elif isinstance(val, list):
                is_missing = len(val) == 0
            elif isinstance(val, dict):
                if key == "date_window":
                    from_val = val.get("from")
                    to_val = val.get("to")
                    is_missing = (from_val is None or from_val == "") and (
                        to_val is None or to_val == ""
                    )
                elif key == "party":
                    adults = val.get("adults")
                    children = val.get("children")
                    is_missing = (adults is None) and (children is None)
                else:
                    is_missing = all(v is None or v == "" for v in val.values())
            elif isinstance(val, (int, float)):
                is_missing = val == 0
            else:
                # 其他类型：使用默认检查
                is_missing = not val

            if is_missing:
                missing.append(key)
        return missing

    def generate_followup(self, missing: List[str]) -> str:
        if not missing:
            return ""
        mapping = {
            "origin": "请问你从哪里出发？（城市即可，例如：上海/北京/广州）",
            "dest_pref": "目的地是哪里？（可以是城市或国家，例如：巴黎/日本）",
            "date_window": "出发日期或大致时间范围是？",
            "trip_len_days": "行程大概几天？（例如：3天/5-7天）",
            "budget_total_cny": "预算大约是多少人民币？",
            "party": "请问有多少人同行？（成人/儿童）",
        }
        lines = ["我还需要一些信息来更精准地帮你："]
        for key in missing:
            lines.append("· " + mapping.get(key, f"请补充 {key}"))
        lines.append("（可以一次性回复多个要点）")
        return "\n".join(lines)

    def auto_correct_task_type(self, intent: Dict[str, Any], user_input: str):
        task_type = intent.get("task_type", "")
        if task_type in ("other", "", None):
            if any(
                k in user_input for k in ["行程", "旅行", "trip", "itinerary", "计划"]
            ):
                task_type = "itinerary"
            elif any(
                k in user_input for k in ["推荐", "景点", "attraction", "recommend"]
            ):
                task_type = "recommendation"
            elif any(k in user_input for k in ["问题", "问", "how", "what", "why"]):
                task_type = "qa"
            intent["task_type"] = task_type

    def clarify(self, user_input: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        self.auto_correct_task_type(intent, user_input)
        missing = self.check_missing_info(intent)
        if missing:
            followup = self.generate_followup(missing)
            return {
                "is_complete": False,
                "revised_intent": intent,
                "follow_up": followup,
                "missing": missing,
            }

        return {"is_complete": True, "revised_intent": intent}

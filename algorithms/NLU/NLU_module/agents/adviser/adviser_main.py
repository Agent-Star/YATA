# adviser_main.py
import asyncio
import logging
import time
from typing import Any

from .adviser_aggregate import run_aggregate
from .adviser_base import AdviserBase
from .adviser_context import run_context_summary
from .adviser_intent import run_intent_parsing
from .adviser_itinerary import generate_itinerary
from .adviser_plan_actions import run_plan_actions
from .adviser_rag import call_rag_api
from .adviser_recommendation import generate_recommendations
from .clarifier import Clarifier

logger = logging.getLogger(__name__)


# adviser_main.py
def merge_partial(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    if not old:
        return new or {}

    out = dict(old)
    for k, v in (new or {}).items():
        # 跳过空字段
        if v in (None, "", [], {}):
            continue
        if k == "task_type":
            old_type = old.get("task_type", "")
            new_type = v.lower() if isinstance(v, str) else str(v).lower()
            # 如果旧的有明确的 task_type, 新的如果是 "other" 或空, 则保留旧的
            if (
                old_type
                and old_type != "other"
                and (new_type == "other" or not new_type or new_type == "")
            ):
                # 保留旧的 task_type
                continue
            # 如果新的有明确的 task_type, 则使用新的
            if new_type and new_type != "other":
                out[k] = v
            continue
        if k == "dest_pref":
            prev = out.get(k) or []
            seen, merged = set(), []
            for item in prev + v:
                s = str(item)
                if s not in seen:
                    seen.add(s)
                    merged.append(item)
            out[k] = merged
            continue
        if isinstance(v, dict):
            out[k] = {**out.get(k, {}), **v}
        elif isinstance(v, list):
            prev = out.get(k) or []
            seen, merged = set(), []
            for item in prev + v:
                s = str(item)
                if s not in seen:
                    seen.add(s)
                    merged.append(item)
            out[k] = merged
        else:
            out[k] = v

    return out


class Adviser:
    def __init__(self, model_name="gpt4o"):
        self.llm = AdviserBase(model_name)
        self.memory: dict[str, Any] = {}
        self.clarifier = Clarifier()

    async def generate_response(
        self,
        user_input: str,
        conversation_history: list | None = None,
        use_rag: bool = True,
        rag_top_k: int = 5,
        debug: bool = False,
        skip_clarifier: bool = False,
    ) -> dict[str, Any]:
        """
        异步生成响应

        参数:
            user_input: 用户输入文本
            conversation_history: 历史对话列表, 格式为 [{"user": "用户输入", "response": {...}}, ...]
            use_rag: 是否使用 RAG 检索
            rag_top_k: RAG 返回结果数量
            debug: 是否打印调试信息
            skip_clarifier: 是否跳过 Clarifier

        返回:
            包含 NLU 处理结果的字典
        """
        t0 = time.time()

        # 1) parse intent for current user input
        result = (
            await run_intent_parsing(self.llm, user_input, conversation_history, debug)
            or {}
        )
        intent_cur = result.get("intent_parsed", {})

        # 2️⃣ 合并历史上下文
        intent_merged = merge_partial(self.memory, intent_cur)
        if not skip_clarifier:
            clarify_result = self.clarifier.clarify(user_input, intent_merged)
            if not clarify_result["is_complete"]:
                self.memory = clarify_result["revised_intent"]
                return {
                    "need_more_info": True,
                    "follow_up": clarify_result["follow_up"],
                    "intent_parsed": clarify_result["revised_intent"],
                }

            # 信息完整, 更新 memory
            self.memory = clarify_result["revised_intent"]
            result["intent_parsed"] = self.memory
        else:
            # 跳过 Clarifier, 直接用上次记忆
            result["intent_parsed"] = self.memory

        task_type = result["intent_parsed"].get("task_type", "itinerary")

        # RAG
        if use_rag:
            city_list = result["intent_parsed"].get("dest_pref", [])
            city_raw = city_list[0] if city_list else ""
            rewrite_alias = result.get("query_rewrite", {}).get("city_alias", [])
            city_alias = rewrite_alias[0] if rewrite_alias else ""
            city_map = {
                "巴黎": "Paris",
                "伦敦": "London",
                "东京": "Tokyo",
                "大阪": "Osaka",
                "香港": "Hong Kong",
                "台北": "Taipei",
                "曼谷": "Bangkok",
                "首尔": "Seoul",
                "悉尼": "Sydney",
                "新加坡": "Singapore",
                "吉隆坡": "Kuala Lumpur",
                "巴塞罗那": "Barcelona",
                "罗马": "Rome",
                "上海": "Shanghai",
                "北京": "Beijing",
            }
            city = city_alias or city_map.get(city_raw, city_raw)

            task_type = result["intent_parsed"].get("task_type", "itinerary")
            tags = result["intent_parsed"].get("tags", []) or []
            subtype = result["intent_parsed"].get("subtype", "")
            keywords = result.get("query_rewrite", {}).get("keywords", [])

            if task_type == "itinerary":
                query_text = f"{city} attractions restrants hotels travel guide"
            elif task_type == "recommendation":
                category = subtype or (tags[0] if tags else "attractions")
                query_text = f"{city} {category} recommendations"
            elif task_type == "qa":
                query_text = user_input.strip()
            else:
                query_text = (
                    " ".join(keywords).strip() or user_input.strip() or "travel guide"
                )

            if debug:
                print(
                    f"🧭 [RAG Query 构造] 类型={task_type}, Query={query_text}, 城市={city}"
                )

            rag_results = await call_rag_api(query_text, city, rag_top_k, debug)

            if debug:
                print(f"🔍 [RAG 精简查询] Query: {query_text}")
                print(f"✅ RAG 返回 {len(rag_results)} 条结果")

            doc_summaries = [f"{r['title']}: {r['content'][:200]}" for r in rag_results]
        else:
            doc_summaries, rag_results = ["No external context."], []

        # 并发执行独立的 LLM 调用 (阶段 1 优化)
        logger.info("开始并发执行 context_summary, plan_steps, final_aggregation")
        t_concurrent_start = time.time()

        context_task = run_context_summary(self.llm, user_input, doc_summaries)
        plan_task = run_plan_actions(self.llm, result["intent_parsed"])
        aggregate_task = run_aggregate(self.llm, [], result["intent_parsed"])

        # 使用 asyncio.gather 并发等待，并处理可能的异常
        results = await asyncio.gather(
            context_task,
            plan_task,
            aggregate_task,
            return_exceptions=True,  # 不会因为单个任务失败而全部失败
        )

        # 检查每个结果并处理异常
        context_summary, plan_steps, final_aggregation = results

        if isinstance(context_summary, Exception):
            logger.error(f"context_summary 失败: {context_summary}")
            context_summary = ""  # 使用默认值

        if isinstance(plan_steps, Exception):
            logger.error(f"plan_steps 失败: {plan_steps}")
            plan_steps = []  # 使用默认值

        if isinstance(final_aggregation, Exception):
            logger.error(f"final_aggregation 失败: {final_aggregation}")
            final_aggregation = ""  # 使用默认值

        # 赋值到 result 字典
        result["context_summary"] = context_summary
        result["plan_steps"] = plan_steps
        result["final_aggregation"] = final_aggregation

        t_concurrent_elapsed = time.time() - t_concurrent_start
        logger.info(f"并发执行完成，耗时: {t_concurrent_elapsed:.2f}s")

        # itinerary only if itinerary task
        if task_type == "itinerary":
            result["detailed_itinerary"] = await generate_itinerary(
                self.llm, result, rag_results, debug
            )
        elif task_type == "recommendation":
            subtype = result["intent_parsed"].get("subtype", "")
            result["recommendations"] = await generate_recommendations(
                self.llm, result, rag_results, debug=debug
            )
            result["final_output_type"] = f"recommendation_{subtype or 'general'}"

        result["latency_sec"] = round(time.time() - t0, 2)
        return result

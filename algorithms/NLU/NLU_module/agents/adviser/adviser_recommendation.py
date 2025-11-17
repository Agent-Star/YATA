# -*- coding: utf-8 -*-
# adviser_recommendation.py
import json
import logging
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


async def generate_recommendations(adviser, intent_result, rag_results=None, debug=False):
    rag_results = rag_results or []
    intent = intent_result.get("intent_parsed", {})
    dests = intent.get("dest_pref", [])
    city = dests[0] if dests else ""
    tags = [t.lower() for t in intent.get("tags", [])]
    party = intent.get("party", {})
    budget = intent.get("budget_total_cny", None)
    subtype = intent.get("subtype", "").lower()
    if subtype:
        rec_type = subtype
    else:
        # fallback 原逻辑
        if any(k in tags for k in ["hotel", "住宿", "旅馆", "stay"]):
            rec_type = "hotel"
        elif any(k in tags for k in ["food", "restaurant", "美食", "餐厅", "吃"]):
            rec_type = "food"
        else:
            rec_type = "attraction"

    if rec_type == "hotel":
        prompt = f"""
你是一名资深酒店顾问。请为 {city or "目的地"} 提供结构化酒店推荐 JSON。
已知标签：{tags}，出行人数：{party}，预算（CNY）：{budget}

要求：
1) 推荐 3-5 家酒店（Hotel / Hostel / Boutique / Resort / Apartment）。
   每家需包含：
   - name: 酒店名称
   - category: 类型（豪华型/精品型/经济型/公寓式等）
   - neighborhood: 所在区域（如 拉丁区/歌剧院/香榭丽舍）
   - highlights: 2~3 个特色（交通便利/地标景观/设计风/早餐好等）
   - price_range_eur: 价格范围（如 €120-250/晚）
   - distance_to_center: 到市中心/地标距离（公里或步行分钟）
   - rating: 平均评分（1~5）
   - booking_tips: 预订要点（是否可取消/旺季价差/推荐平台）
   - address_or_entry: 地址简述
   - map_query: 地图检索词
   - sources: 若有 RAG 来源列出
   - tips: 注意事项（噪音/无电梯/早餐/交通）
2) 输出 groups：例如“高性价比”“家庭友好”“浪漫推荐”“交通便利区”。
3) 输出 summary：概述酒店分布与性价比建议。
4) 输出 next_questions：例如入住日期、是否需要家庭房、早餐偏好、地铁距离等。
5) 严格输出 JSON。
参考来源：{json.dumps(rag_results[:3], ensure_ascii=False)}
"""
    elif rec_type == "food":
        prompt = f"""
你是一名资深餐饮顾问。请为 {city or "目的地"} 提供餐厅与美食推荐，输出结构化 JSON。
已知标签：{tags}，出行人数：{party}，预算（CNY）：{budget}

要求：
1) 推荐 3-5 家餐厅/街头小吃/咖啡馆/甜品店；每项包含：
   - name: 名称
   - category: 类型（法餐/中餐/甜点/咖啡馆/米其林餐厅/地方菜）
   - neighborhood: 区域（如 玛黑区/圣日耳曼）
   - highlights: 推荐菜品/风格特色（如 法式焗蜗牛、可颂、海鲜拼盘）
   - avg_price_eur: 人均消费（€）
   - open_hours: 营业时间
   - best_time: 最推荐的用餐时段
   - booking_tips: 是否需预订、线上预约平台
   - transport: 附近地铁/巴士站
   - map_query: 地图检索词
   - sources: 若有 RAG 来源列出
   - tips: 等位/服务费/着装要求/拍照限制
2) 输出 groups：如“米其林推荐”“本地人最爱”“甜点与咖啡”“夜宵好去处”。
3) 输出 summary：总结餐饮氛围、价位梯度与适合人群。
4) 输出 next_questions：如饮食偏好、是否素食/清真、是否接受排队。
参考来源：{json.dumps(rag_results[:3], ensure_ascii=False)}
"""
    else:  # 景点推荐
        prompt = f"""
你是一名资深旅行顾问。请为 {city or "目的地"} 提供景点/活动推荐，输出结构化 JSON。
已知标签：{tags}，出行人数：{party}，预算（CNY）：{budget}

要求：
1) 推荐 3-5 个项目，覆盖地标、艺术馆、公园、夜景、特色活动等。
   - name: 名称
   - category: 景点/博物馆/活动/夜景/步行路线
   - neighborhood: 区域
   - highlights: 卖点或独特体验
   - best_time: 适合时间段
   - est_duration: 建议停留时间
   - ticket: 票价信息（若有）
   - budget_eur: 花费预估
   - transport: 地铁/步行/巴士/游船等
   - address_or_entry: 地址简述
   - map_query: 地图检索词
   - sources: 若有 RAG 来源列出
   - tips: 排队/预约/语言/文化/天气建议
2) 输出 groups：如“必看地标”“艺术文化线”“夜景摄影点”“家庭友好”“免费景点”。
3) 输出 summary：概述行程建议、节省时间策略与门票小贴士。
4) 输出 next_questions：如旅行天数、是否购买博物馆通票、步行/乘车偏好。
参考来源：{json.dumps(rag_results[:3], ensure_ascii=False)}
"""

    schema_hint = """{
      "items": [{
        "name": "string",
        "category": "string",
        "neighborhood": "string",
        "highlights": ["string"],
        "price_range_eur": "string",
        "budget_eur": "string",
        "ticket": "string",
        "best_time": "string",
        "est_duration": "string",
        "open_hours": "string",
        "distance_to_center": "string",
        "transport": "string",
        "rating": "number",
        "address_or_entry": "string",
        "map_query": "string",
        "sources": [{"title":"string","url":"string"}],
        "tips": ["string"]
      }],
      "groups": [{"title":"string","item_names":["string"]}],
      "summary": "string",
      "next_questions": ["string"]
    }"""

    out = await adviser.ask_json(prompt, schema_hint=schema_hint)
    if not isinstance(out, dict):
        out = {"raw_text": out}
    if debug:
        print(f"• recommendations generated for type: {rec_type}")

    out["rec_type"] = rec_type

    if isinstance(out, dict) and "items" in out:
        # 拼装推荐项目的详细文本
        items_text = "\n".join(
            [
                f"{idx + 1}. 名称：{i.get('name', '')}；类别：{i.get('category', '')}；位置：{i.get('neighborhood', '')}；"
                f"亮点：{', '.join(i.get('highlights', []))}；"
                f"推荐时间：{i.get('best_time', '')}；建议停留：{i.get('est_duration', '')}；"
                f"交通：{i.get('transport', '')}；门票：{i.get('ticket', '')}；预算：{i.get('budget_eur', '')}；"
                f"贴士：{'; '.join(i.get('tips', [])) if i.get('tips') else ''}"
                for idx, i in enumerate(out["items"][:8])
            ]
        )

        summary_prompt = f"""
    你是一名资深旅行顾问，请根据以下景点与信息撰写一篇详细的中文旅行推荐说明。
    要求：
    - 每个景点单独成段，长度约 4~6 句；
    - 语气自然、有代入感，像人写的旅游攻略；
    - 要整合 "交通方式""时间建议""小贴士" 等；
    - 不要用项目符号，不要编号；
    - 最后写一个总结段，鼓励游客体验当地文化。

    推荐项目清单：
    {items_text}
    """
        # 使用较大的 max_tokens 以确保推荐摘要完整（通常需要4000-6000 tokens）
        natural_summary = await adviser.ask_text(
            summary_prompt, temperature=0.7, max_tokens=6000
        )
        out["natural_summary"] = natural_summary.strip()

    return out


async def generate_recommendations_stream(
    adviser, intent_result, rag_results=None, debug=False
) -> AsyncGenerator[str, None]:
    """
    流式生成推荐内容 (逐 token 返回)

    参数:
        adviser: Adviser 实例
        intent_result: 包含 intent_parsed 等信息的结果字典
        rag_results: RAG 检索结果
        debug: 是否开启调试模式

    Yields:
        str: 每次生成的文本 chunk (推荐内容的 Markdown 片段)
    """
    rag_results = rag_results or []
    intent = intent_result.get("intent_parsed", {})
    dests = intent.get("dest_pref", [])
    city = dests[0] if dests else ""
    tags = [t.lower() for t in intent.get("tags", [])]
    party = intent.get("party", {})
    budget = intent.get("budget_total_cny", None)
    subtype = intent.get("subtype", "").lower()

    # 确定推荐类型
    if subtype:
        rec_type = subtype
    else:
        # fallback 原逻辑
        if any(k in tags for k in ["hotel", "住宿", "旅馆", "stay"]):
            rec_type = "hotel"
        elif any(k in tags for k in ["food", "restaurant", "美食", "餐厅", "吃"]):
            rec_type = "food"
        else:
            rec_type = "attraction"

    # 简化的推荐 Prompt（直接生成自然语言，不生成 JSON）
    # 根据推荐类型调整 prompt
    if rec_type == "hotel":
        prompt = f"""
你是一名资深酒店顾问。请为 {city or "目的地"} 提供详细的酒店推荐。
已知标签：{tags}，出行人数：{party}，预算（CNY）：{budget}

要求：
1) 推荐 3-5 家酒店，覆盖不同价位和风格（豪华型/精品型/经济型/公寓式等）
2) 每家酒店需要包含：
   - 酒店名称和类型
   - 所在区域（如 拉丁区/歌剧院/香榭丽舍）
   - 特色亮点（交通便利/地标景观/设计风格/早餐质量等）
   - 价格范围（€/晚）
   - 到市中心/主要景点的距离
   - 评分和预订建议
   - 注意事项（噪音/无电梯/早餐/交通）
3) 按自然段落组织，每个酒店单独成段，长度约 4-6 句话
4) 语气自然、有代入感，像人写的旅游攻略
5) 最后写一个总结段，概述酒店分布与性价比建议

参考 RAG 检索结果（自然融合，不要生硬引用）：
{json.dumps(rag_results[:3], ensure_ascii=False, indent=2)}

只输出 Markdown 正文，不要输出 JSON 或代码块。长度约 800-1200 字。
"""
    elif rec_type == "food":
        prompt = f"""
你是一名资深餐饮顾问。请为 {city or "目的地"} 提供详细的餐厅与美食推荐。
已知标签：{tags}，出行人数：{party}，预算（CNY）：{budget}

要求：
1) 推荐 3-5 家餐厅/街头小吃/咖啡馆/甜品店，覆盖不同类型
2) 每家需要包含：
   - 名称和类型（法餐/中餐/甜点/咖啡馆/米其林餐厅/地方菜）
   - 所在区域（如 玛黑区/圣日耳曼）
   - 推荐菜品和风格特色
   - 人均消费（€）
   - 营业时间和最佳用餐时段
   - 预订建议
   - 交通方式
   - 小贴士（等位/服务费/着装要求）
3) 按自然段落组织，每家餐厅单独成段，长度约 4-6 句话
4) 语气自然、有代入感，像人写的美食攻略
5) 最后写一个总结段，概述餐饮氛围、价位梯度与适合人群

参考 RAG 检索结果（自然融合，不要生硬引用）：
{json.dumps(rag_results[:3], ensure_ascii=False, indent=2)}

只输出 Markdown 正文，不要输出 JSON 或代码块。长度约 800-1200 字。
"""
    else:  # 景点推荐
        prompt = f"""
你是一名资深旅行顾问。请为 {city or "目的地"} 提供详细的景点/活动推荐。
已知标签：{tags}，出行人数：{party}，预算（CNY）：{budget}

要求：
1) 推荐 3-5 个项目，覆盖地标、艺术馆、公园、夜景、特色活动等
2) 每个项目需要包含：
   - 名称和类型（景点/博物馆/活动/夜景/步行路线）
   - 所在区域
   - 独特体验和卖点
   - 适合的时间段
   - 建议停留时间
   - 票价信息（如有）
   - 花费预估（€）
   - 交通方式（地铁/步行/巴士/游船等）
   - 地址或入口说明
   - 小贴士（排队/预约/语言/文化/天气建议）
3) 按自然段落组织，每个景点单独成段，长度约 4-6 句话
4) 语气自然、有代入感，像人写的旅游攻略
5) 最后写一个总结段，概述行程建议、节省时间策略与门票小贴士

参考 RAG 检索结果（自然融合，不要生硬引用）：
{json.dumps(rag_results[:3], ensure_ascii=False, indent=2)}

只输出 Markdown 正文，不要输出 JSON 或代码块。长度约 800-1200 字。
"""

    if debug:
        logger.info(f"开始流式生成 {rec_type} 推荐...")

    # 使用流式 API 逐 token 返回
    try:
        async for chunk in adviser.ask_text_stream(
            prompt, temperature=0.7, max_tokens=6000
        ):
            yield chunk

        if debug:
            logger.info(f"流式生成 {rec_type} 推荐完成")

    except Exception as e:
        logger.error(f"流式生成推荐失败: {e}")
        raise


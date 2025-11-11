# adviser_itinerary.py
# adviser_itinerary.py
# -*- coding: utf-8 -*-
import json


def generate_itinerary(adviser, result, rag_results, debug=False):
    # 从意图里抓一些上下文（城市、日期等）
    intent = result.get("intent_parsed", {}) if isinstance(result, dict) else {}
    city = ""
    start_date = ""
    end_date = ""
    days = ""

    try:
        dests = intent.get("dest_pref", []) or []
        city = dests[0] if dests else ""
        date_window = intent.get("date_window", {}) or {}
        start_date = date_window.get("from") or ""
        end_date = date_window.get("to") or ""
        days = intent.get("trip_len_days") or ""
    except Exception:
        pass

    extra_context = """热门景点建议提前在官网预约购票
需要预约的景点:
卢浮宫(成人22欧, 提前7-15天预约)
凡尔赛宫(旺季€32，提前3天)
卢浮宫 开放时间: (周二闭馆)日常09:00-18:00, 周三和周五09:00-21:00 成人€22
埃菲尔铁塔 09:00-23:00
二层楼梯/电梯: €14.2/22.6，顶楼电梯/楼梯+电梯: 35.3欧/26.9欧
凡尔赛宫 开放时间: (城堡周二至周日09:00-17:30(周一闭馆)，凡尔赛宫城堡价格€21
奥赛博物馆 开放时间: (周二至周日09:30-18:00(周一闭馆)网上16欧，线下14欧
圣礼拜堂 开放时间: 09:00-19:00  €13
凯旋门  开放时间: (周三至周一10:00-23:00、周二11:00-23:00 €16
橘园 开放时间: (9:00-18:00(周二闭馆) €16,提前3天
巴黎歌剧院 开放时间: (10:00-17:00 €15，演出票€10-12
巴黎迪士尼乐园 开放时间: (9:00-22:00 约€70~105
枫丹白露宫 开放时间: (09:30-18:00(周二闭馆)€14
曼特农城堡 开放时间: (10:30-18:00(周一闭馆)€8.5
莫奈花园 开放时间: (9:30-18:00 €12.5

——
巴黎博物馆通票省钱攻略
【Paris Museum Pass】找到官网买
2日€70｜4日€90｜6日€110，覆盖50+景点
注意：卢浮宫、凡尔赛持卡也需单独约时段
"""

    # 长文生成 Prompt —— 强调「必须输出 Markdown 长文」
    itinerary_prompt = f"""
    你是一名**专业旅行策划师**。请根据下面的结构化意图和外部检索，生成**超详细的行程规划（中文 Markdown 长文）**：

    - 目的地：{city or "目的地未识别（默认按巴黎示例）"}
    - 行程时长：{days or "未明确（按 4~5 天示例）"} 天
    - 日期区间（如有）：{start_date or "未给出"} ~ {end_date or "未给出"}

    ## 写作要求（务必遵守）
    1) **按 Day 1 / Day 2 / Day 3 / Day 4 / Day 5...** 组织，每天**从 06:30 到 22:00** 给出连续时间轴（至少 8~10 个时间点），建议：06:30/08:00/09:30/11:00/12:30/14:00/15:30/17:00/18:30/20:00/21:30。
    2) 每个时间点必须包含：**活动名称、地点、交通方式（地铁/步行/巴士/火车/游船等）、人均预算（€）、推荐餐饮、Tips（安全/文化/天气/礼仪）、“背景小知识/故事”**（1~2 句）。
    3) 交通写清楚**典型路线/地铁线编号**；用“→”表示换乘或步行衔接。
    4) **用现实可行的时长安排**（避免“半天逛完卢浮宫”这类不合理分配）。
    5) 结合以下**票价/开放时间/省钱攻略**尽量引用（如无数据则写“以官网为准”）：
    {extra_context}
    6) 若启用了 RAG，请**自然融合**检索的 1~2 条信息，不要生硬引用：  
    {json.dumps(rag_results[:2], ensure_ascii=False, indent=2)}

    ## 结尾部分（务必包含）
    - **预算小结**（住宿/交通/餐饮/门票的区间）
    - **交通与购票 Tips 汇总**
    - **博物馆通票/预约建议**
    - **独行旅客/亲子/雨天替代方案**

    下方是结构化意图 JSON（仅供参考，不要照抄成列表）：
    ```json
    {json.dumps(result, ensure_ascii=False, indent=2)}
    只输出 Markdown 正文，不要再输出任何 JSON 或代码块围栏。 长度尽量达到约 1800~2500 字。
    """
    # 关键：用 ask_text 让模型输出纯 Markdown 长文
    markdown = adviser.ask_text(itinerary_prompt, temperature=0.6)

    if debug:
        print("• itinerary generated (markdown, long form).")

    # 返回一个固定字段，便于 main.py 统一打印
    return {"itinerary_markdown": markdown}

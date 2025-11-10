"""
🌍 旅行规划 RAG 数据供给系统（BGE-M3 版）
功能：
- OSM：获取城市地理坐标
- Wikipedia：多语言文本 + Infobox（不再优先中文）
- WeatherAPI：获取历史气温
- BAAI/bge-m3：向量化（1024维）
- 输出 JSON 文件 → 含清洗后知识，供下游使用

📌 特点：使用 BGE-M3 模型（1024维）、支持中英双语、带 Infobox 清洗
"""

import json
import os
import re
from datetime import datetime, timedelta

import requests
from sentence_transformers import SentenceTransformer

# ===================== 配置 =====================
# 输出目录：当前项目的 data 目录
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")

WIKI_LANGUAGES = ["en", "zh"]  # 英文优先，中文 fallback
USER_AGENT = "TravelRAG-Agent/1.0 (contact@team.com)"

# 替换为你自己的 WeatherAPI Key
WEATHERAPI_KEY = "your-key-here"

# 使用 BGE-M3 模型（1024维，支持多语言）
MODEL_NAME = "BAAI/bge-m3"
model = SentenceTransformer(MODEL_NAME)


# ===================== 工具函数 =====================
def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def split_text(text, min_len=200, max_len=500):
    cleaned = clean_text(text)
    if not cleaned:
        return []
    sentences = re.split(r"[。？！.?!\n]", cleaned)
    chunks, current, length = [], [], 0
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        l = len(sent)
        if length + l > max_len:
            if current:
                chunks.append("".join(current))
                current, length = [sent], l
            else:
                chunks.append(sent)
        elif length + l >= min_len:
            current.append(sent)
            chunks.append("".join(current))
            current, length = [], 0
        else:
            current.append(sent)
            length += l
    if current:
        chunks.append("".join(current))
    return [c for c in chunks if len(c) >= 100]


def vectorize_chunks(chunks):
    if not chunks:
        return []
    embeddings = model.encode(chunks, normalize_embeddings=True)
    return list(zip(chunks, embeddings.tolist()))


# ===================== 1. OSM 地理数据 =====================
def get_osm_data(city_name, country_code):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1,
        "countrycodes": country_code,
        "class": "boundary",
        "type": "administrative",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            print(f"❌ OSM未找到：{city_name}({country_code})")
            return None
        item = data[0]
        return {
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "country": item["display_name"].split(",")[-1].strip(),
        }
    except Exception as e:
        print(f"❌ OSM失败：{e}")
        return None


# ===================== 2. Wikipedia 多语言知识 =====================
def clean_infobox(raw_infobox):
    """
    简化版 Infobox 清洗：提取温度、降水、别名等关键字段
    """
    if not raw_infobox:
        return {}

    cleaned = {}

    # 温度映射（兼容大小写和符号变体）
    temp_map = {
        "Jan_Hi_°C": "jan_high_temp",
        "Feb_Hi_°C": "feb_high_temp",
        "Mar_Hi_°C": "mar_high_temp",
        "Apr_Hi_°C": "apr_high_temp",
        "May_Hi_°C": "may_high_temp",
        "Jun_Hi_°C": "jun_high_temp",
        "Jul_Hi_°C": "jul_high_temp",
        "Aug_Hi_°C": "aug_high_temp",
        "Sep_Hi_°C": "sep_high_temp",
        "Oct_Hi_°C": "oct_high_temp",
        "Nov_Hi_°C": "nov_high_temp",
        "Dec_Hi_°C": "dec_high_temp",
        "Jan_Lo_°C": "jan_low_temp",
        "Year_Precip_mm": "annual_precipitation_mm",
    }

    for key, clean_key in temp_map.items():
        if key in raw_infobox:
            try:
                val = raw_infobox[key].strip().replace("°C", "").replace(",", "")
                cleaned[clean_key] = round(float(val), 1)
            except:
                pass

    # 文本字段提取
    text_fields = {
        "nickname": "nickname",
        "official_name": "official_name",
        "country": "country",
        "area_total_km2": "area_sqkm",
        "population_as_of": "population_year",
    }
    for key, desc in text_fields.items():
        if key in raw_infobox:
            val = re.sub(
                r"\[\[.*?\]\]",
                lambda m: m.group(0).split("|")[-1].strip("]]"),
                raw_infobox[key],
            )
            val = re.sub(r"<.*?>", "", val).strip()
            if val:
                cleaned[desc] = val

    # 推断最佳旅游季节
    summer_avg = cleaned.get("jul_high_temp", 0)
    winter_avg = cleaned.get("jan_high_temp", 0)
    if summer_avg > 30 and winter_avg < 15:
        cleaned["best_travel_season"] = "Spring/Autumn"
    elif summer_avg > 25:
        cleaned["best_travel_season"] = "Autumn"
    elif winter_avg > 18:
        cleaned["best_travel_season"] = "Winter warmth"
    else:
        cleaned["best_travel_season"] = "Spring/Autumn"

    return cleaned


def get_wikipedia_data(city_name, country_code):
    """
    优先尝试英文页面，失败后 fallback 到中文
    """
    for lang in WIKI_LANGUAGES:
        wiki_url = f"https://{lang}.wikipedia.org/w/api.php"
        headers = {"User-Agent": USER_AGENT}

        direct_titles = [city_name, f"{city_name} (city)", f"{city_name} City"]

        for title in direct_titles:
            try:
                content_params = {
                    "action": "query",
                    "prop": "extracts|revisions",
                    "titles": title,
                    "explaintext": True,
                    "rvprop": "content",
                    "rvslots": "main",
                    "format": "json",
                }
                res = requests.get(
                    wiki_url, params=content_params, headers=headers, timeout=10
                )
                res.raise_for_status()
                data = res.json()
                page = list(data["query"]["pages"].values())[0]

                if page.get("missing") or len(page.get("extract", "").strip()) < 50:
                    continue

                extract = page.get("extract", "")
                full_title = page["title"]
                page_url = f"https://{lang}.wikipedia.org/wiki/{full_title}"

                rev = page.get("revisions", [{}])[0]
                wikitext = None
                if "slots" in rev and "main" in rev["slots"]:
                    wikitext = rev["slots"]["main"].get("*")
                elif "*" in rev:
                    wikitext = rev["*"]
                if not wikitext:
                    continue

                import mwparserfromhell

                wikicode = mwparserfromhell.parse(wikitext)
                templates = wikicode.filter_templates()
                infobox_candidates = [
                    t
                    for t in templates
                    if "infobox" in str(t.name).lower() or "信息框" in str(t.name)
                ]

                raw_infobox = {}
                if infobox_candidates:
                    chosen = infobox_candidates[0]
                    for param in chosen.params:
                        key = str(param.name).strip()
                        value = str(param.value).strip()
                        value = re.sub(r"\[\[(?:[^|\]]*\|)?([^]]+)\]\]", r"\1", value)
                        if key and value:
                            raw_infobox[key] = value

                structured_knowledge = clean_infobox(raw_infobox)

                print(f"✅ [{lang}] 成功获取：《{full_title}》")
                return extract, structured_knowledge, lang, full_title, page_url

            except Exception as e:
                print(f"❌ [{lang}] 请求失败 {title}：{str(e)}")
                continue

    print(f"❌ 所有尝试均失败：{city_name}")
    return None, None, None, None, None


# ===================== 3. 天气数据 ======================
def get_weather_data(lat, lon):
    if not WEATHERAPI_KEY or "YOUR_" in WEATHERAPI_KEY:
        print("🟡 跳过天气数据")
        return None

    try:
        target_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        url = "http://api.weatherapi.com/v1/history.json"
        params = {"key": WEATHERAPI_KEY, "q": f"{lat},{lon}", "dt": target_date}
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        day_data = response.json()["forecast"]["forecastday"][0]["day"]
        avg_temp = day_data.get("avgtemp_c")
        if avg_temp is None:
            return None

        return {
            "date": target_date,
            "avg_temp_c": round(avg_temp, 1),
            "max_temp_c": round(day_data.get("maxtemp_c", 0), 1),
            "min_temp_c": round(day_data.get("mintemp_c", 0), 1),
            "condition": day_data.get("condition", {}).get("text", "Unknown"),
        }
    except Exception as e:
        print(f"❌ 天气数据获取失败：{str(e)}")
        return None


# ===================== 4. 主流程：导出 =====================
def export_city_data(city_name, country_code):
    print(f"\n{'=' * 60}\n🌍 正在处理：{city_name} ({country_code})")

    osm_data = get_osm_data(city_name, country_code)
    if not osm_data:
        return False

    wiki_content, infobox_cleaned, lang, wiki_title, wiki_url = get_wikipedia_data(
        city_name, country_code
    )
    if not wiki_content:
        return False

    chunks = split_text(wiki_content)
    print(f"✅ 文本分块完成：{len(chunks)}段")
    chunks_with_vectors = vectorize_chunks(chunks)
    weather_data = get_weather_data(osm_data["lat"], osm_data["lon"])

    safe_city_name = city_name.replace(" ", "_")
    filename = f"{OUTPUT_DIR}/{safe_city_name}_{country_code}_{lang}.json"

    data = {
        "city_name": city_name,
        "country_code": country_code,
        "lang": lang,
        "timestamp": datetime.now().isoformat(),
        "urls": {
            "wikipedia": wiki_url,
            "weatherapi_query": f"http://api.weatherapi.com/v1/history.json?q={osm_data['lat']},{osm_data['lon']}&dt={weather_data['date']}"
            if weather_data
            else None,
            "osm_location": f"https://www.openstreetmap.org/search?query={city_name}%20{country_code}",
        },
        "location": {
            "latitude": osm_data["lat"],
            "longitude": osm_data["lon"],
            "country": osm_data["country"],
        },
        "knowledge": {
            "infobox": infobox_cleaned,
            "text_chunks": [
                {"text": text, "embedding": vec} for text, vec in chunks_with_vectors
            ],
        },
        "weather": weather_data,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"📁 ✅ 数据已导出：{filename}")
        return True
    except Exception as e:
        print(f"❌ 文件写入失败：{str(e)}")
        return False


# ===================== 主程序入口 =====================
if __name__ == "__main__":
    print("⏳ 正在加载 BGE-M3 模型（首次运行需下载，约1.5GB）...")
    print(f"📌 模型：{MODEL_NAME}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cities = [
        ("Barcelona", "es"),
        ("Sanya", "cn"),
        ("Paris", "fr"),
        ("Athens", "gr"),
        ("Kyoto", "jp"),
        ("Beijing", "cn"),
    ]

    success_count = 0
    for name, code in cities:
        if export_city_data(name, code):
            success_count += 1

    print(f"\n{'=' * 60}")
    print(f"🎉 数据导出完成！成功 {success_count}/{len(cities)} 个城市")
    print(f"📂 所有文件已保存至：{OUTPUT_DIR}")

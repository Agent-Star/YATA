"""Utility to convert structured Paris TXT guides into JSON for ingest."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


# ===================== 可配置参数 =====================
DATA_DIR = Path(__file__).parent / "data" / "paris"
# 输出将逐文件写到 data 根目录，与 TXT 同名（仅扩展名改为 .json）
OUTPUT_DIR = Path(__file__).parent / "data"

DEFAULT_CITY = "Paris"
DEFAULT_COUNTRY_CODE = "fr"
DEFAULT_LANG = "zh"


@dataclass
class TxtRecord:
    headers: Dict[str, str]
    context: str


def _normalize_key(label: str) -> str:
    return label.strip().lower()


def parse_structured_txt(path: Path) -> TxtRecord:
    headers: Dict[str, str] = {}
    context_lines: List[str] = []
    context_started = False

    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if not context_started:
                if stripped.startswith("【") and "】" in stripped:
                    key, value = stripped.split("】", 1)
                    key = _normalize_key(key[1:])
                    value = value.strip()
                    if key == "context":
                        context_started = True
                        if value:
                            context_lines.append(value)
                    else:
                        headers[key] = value
                else:
                    # 忽略 context 之前的非标签行
                    continue
            else:
                if stripped.startswith("【") and "】" in stripped:
                    # context 开始之后所有内容都视为正文，去掉额外标签
                    _, value = stripped.split("】", 1)
                    value = value.strip()
                    if value:
                        context_lines.append(value)
                else:
                    context_lines.append(stripped)

    context = "\n".join(context_lines).strip()
    return TxtRecord(headers=headers, context=context)


def chunk_text(text: str, min_len: int = 200, max_len: int = 500) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    sentences = re.split(r"(?<=[。？！!?\.])\s+", cleaned)
    chunks: List[str] = []
    buffer: List[str] = []
    length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_length = len(sentence)
        if length + sentence_length > max_len:
            if buffer:
                chunks.append("".join(buffer))
            buffer = [sentence]
            length = sentence_length
        else:
            buffer.append(sentence)
            length += sentence_length
            if length >= min_len:
                chunks.append("".join(buffer))
                buffer = []
                length = 0

    if buffer:
        chunks.append("".join(buffer))

    # 去除过短片段
    return [chunk for chunk in chunks if len(chunk) >= 50]


def build_payload_for_file(path: Path) -> Tuple[Dict[str, object], str]:
    """处理单个 TXT，返回 JSON payload 及建议输出文件名（不含目录）。"""
    record = parse_structured_txt(path)
    if not record.context:
        raise ValueError(f"{path.name} 未包含可用的 context 内容")

    headers = record.headers
    title = headers.get("title") or f"{DEFAULT_CITY} 攻略 {path.stem}"
    day = headers.get("day")
    author = headers.get("author")
    timestamp = headers.get("timestamp") or datetime.now().isoformat()
    city = headers.get("city") or DEFAULT_CITY
    url = headers.get("url")

    # 切分正文
    chunks = chunk_text(record.context)
    if not chunks:
        chunks = [record.context]

    text_chunks: List[Dict[str, object]] = []
    for chunk in chunks:
        text_chunks.append(
            {
                "title": title,
                "text": chunk,
                "day": day,
                "author": author,
                "url": url,
            }
        )

    urls = {"source": url} if url else {}

    payload: Dict[str, object] = {
        "city_name": city,
        "country_code": DEFAULT_COUNTRY_CODE,
        "lang": DEFAULT_LANG,
        "timestamp": timestamp,
        "urls": urls,
        "knowledge": {
            "text_chunks": text_chunks,
        },
    }
    if author:
        payload["author"] = author

    # 输出文件名与 TXT 同名（扩展名改为 .json），并放在 data 根目录
    output_name = f"{path.stem}.json"
    return payload, output_name


def write_payload(output_name: str, payload: Dict[str, object]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / output_name
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return out_path


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in DATA_DIR.glob("*.txt") if p.is_file()])
    if not files:
        print(f"未找到任何 TXT 文件：{DATA_DIR}")
        return

    generated = 0
    for path in files:
        try:
            payload, output_name = build_payload_for_file(path)
            out_path = write_payload(output_name, payload)
            print(f"已生成 JSON：{out_path}")
            generated += 1
        except Exception as e:
            print(f"跳过 {path.name}：{e}")

    print(f"完成。成功生成 {generated}/{len(files)} 个 JSON 文件。")


if __name__ == "__main__":
    main()



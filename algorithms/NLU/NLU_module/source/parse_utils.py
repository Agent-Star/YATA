# -*- coding: utf-8 -*-
import re


def parse_correct_answer(yaml_text: str):
    if not yaml_text:
        return "Empty response.", True

    # 提取 response_is_safe（True/False）
    match_safe = re.search(
        r"response_is_safe\s*:\s*(True|False)", yaml_text, re.IGNORECASE
    )
    is_safe = True  # 默认安全
    if match_safe:
        is_safe = match_safe.group(1).strip().lower() == "true"

    # 提取 explanation（多行兼容）
    match_exp = re.search(
        r"explanation\s*:\s*(.*)", yaml_text, re.IGNORECASE | re.DOTALL
    )
    explanation = "No explanation found."
    if match_exp:
        # 去掉多余换行与分隔符
        explanation = match_exp.group(1).strip()
        explanation = re.sub(r"^[-–—]+\s*", "", explanation)
        explanation = re.sub(r"[\n\r]+---.*", "", explanation)  # 删除尾部的 "---"
        explanation = explanation.strip()

    return explanation, is_safe

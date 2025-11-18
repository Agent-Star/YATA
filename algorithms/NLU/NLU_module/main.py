# -*- coding: utf-8 -*-
import json
import os

import aiofiles
from NLU_module.agents.adviser.adviser_main import Adviser
from NLU_module.agents.verifier import Verifier


class NLU:
    def __init__(
        self, log_folder="log", file_name="0", with_verifier=True, max_retries=3
    ):
        self.path = f"NLU_module/{log_folder}/{file_name}"
        self.history = []
        self.with_verifier = with_verifier
        self.session_id = file_name  # 保存 session_id 用于日志
        self.max_retries = max_retries  # Verifier 最大重试次数

        # 初始化模型
        self.adviser = Adviser(model_name="gpt4o")  # 或 'deepseek'
        if self.with_verifier:
            self.verifier = Verifier()  # GPT-4o

        # 初始化日志路径
        os.makedirs(self.path, exist_ok=True)
        self.log_path = f"{self.path}/log.txt"
        self.history_path = f"{self.path}/history.txt"

        # 如果文件不存在则创建，存在则追加（不清空，保留历史）
        if not os.path.exists(self.log_path):
            open(self.log_path, "w").close()
        if not os.path.exists(self.history_path):
            open(self.history_path, "w").close()

        self.init = True

    async def run(self, contents, context=None):
        user_input = contents

        print("________________________________________")
        print(f"🧠 User Input: {user_input}")

        # 准备历史对话上下文（只包含用户输入和响应，不包含内部结构）
        conversation_history = []
        if self.history:
            for h in self.history:
                conv_turn = {
                    "user": h.get("user", ""),
                    "response": {
                        "intent_parsed": h.get("response", {}).get("intent_parsed", {})
                    },
                }
                conversation_history.append(conv_turn)

        # 第一次调用 Adviser
        if self.init:
            response = await self.adviser.generate_response(
                user_input,
                conversation_history=conversation_history,
                use_rag=True,
                rag_top_k=25,
                debug=True,
                skip_clarifier=False,
            )
            self.init = False
        else:
            # 非首次：正常调用，关掉 debug，但传递历史对话
            response = await self.adviser.generate_response(
                user_input,
                conversation_history=conversation_history,
                use_rag=False,
                rag_top_k=25,
                debug=True,
                skip_clarifier=False,
            )
        # 保存 Adviser 输出
        async with aiofiles.open(self.log_path, "a+", encoding="utf-8") as f:
            await f.write(
                f"\n----------------------- User -----------------------\n{user_input}\n"
            )
            await f.write(
                f"----------------------- Adviser Response -----------------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
            )

        # ✅ 如果需要补充信息，直接输出追问并返回（不走 Verifier）
        if response.get("need_more_info"):
            follow_up = response.get("follow_up", "我还需要一些补充信息～")
            print("🤔 需要补充信息：\n")
            print(follow_up)
            # 记录历史
            self.history.append({"user": user_input, "response": response})
            async with aiofiles.open(self.history_path, "a+", encoding="utf-8") as f:
                await f.write(f"\n------------ User ------------\n{user_input}\n")
                await f.write(
                    f"------------ Response ------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
                )
            print("\n****************************************")
            return response

        # 调用 Verifier 审查
        task_type = response.get("intent_parsed", {}).get("task_type", "")
        if self.with_verifier and task_type == "itinerary":
            explanation, is_safe = await self.verifier.assess_cur_response(response)
            async with aiofiles.open(self.log_path, "a+", encoding="utf-8") as f:
                await f.write(
                    "\n&&&&&&&&&&&&&&&&&&&&&&& Safety Check &&&&&&&&&&&&&&&&&&&&&&&\n"
                )
                await f.write(f"Safety: {is_safe}\nExplanation: {explanation}\n")

            # 如果不安全，重新生成（带重试次数限制）
            retry_count = 0
            while not is_safe and retry_count < self.max_retries:
                retry_count += 1
                print(
                    f"⚠️ Verifier 检测到问题，正在重新生成... (第 {retry_count}/{self.max_retries} 次)"
                )
                revision_prompt = f"""原始用户请求：{user_input}

请根据以下问题修正之前的计划：
{explanation}

请保持原始请求的意图（task_type、目的地、天数、预算等），只修正检测到的问题。"""
                # 重新生成时也传递历史对话
                conversation_history = []
                if self.history:
                    for h in self.history:
                        conv_turn = {
                            "user": h.get("user", ""),
                            "response": {
                                "intent_parsed": h.get("response", {}).get(
                                    "intent_parsed", {}
                                )
                            },
                        }
                        conversation_history.append(conv_turn)
                response = await self.adviser.generate_response(
                    revision_prompt,
                    conversation_history=conversation_history,
                    use_rag=True,
                    rag_top_k=25,
                    debug=True,
                )
                explanation, is_safe = await self.verifier.assess_cur_response(response)

                async with aiofiles.open(self.log_path, "a+", encoding="utf-8") as f:
                    await f.write(
                        f"\n----------------------- Regenerated Response -----------------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
                    )
                    await f.write(f"Safety: {is_safe}\nExplanation: {explanation}\n")

            # 如果达到最大重试次数仍未通过验证, 发出警告
            if not is_safe:
                print(
                    f"⚠️ 警告: 已达到最大重试次数 ({self.max_retries}), 但方案仍存在问题. 返回最后一次生成的结果."
                )
                async with aiofiles.open(self.log_path, "a+", encoding="utf-8") as f:
                    await f.write(
                        f"\n⚠️ 警告: 已达到最大重试次数, 最终状态: is_safe={is_safe}\n"
                    )
        else:
            print("Recommendation-type task detected: Skipping Verifier check.")

        # 更新历史记录
        self.history.append({"user": user_input, "response": response})
        async with aiofiles.open(self.history_path, "a+", encoding="utf-8") as f:
            await f.write(f"\n------------ User ------------\n{user_input}\n")
            await f.write(
                f"------------ Response ------------\n{json.dumps(response, ensure_ascii=False, indent=2)}\n"
            )

        task_type = response.get("intent_parsed", {}).get("task_type", "")

        # ---------------- 行程类任务 ----------------
        if task_type == "itinerary":
            md = response.get("itinerary_markdown") or response.get(
                "detailed_itinerary", {}
            ).get("itinerary_markdown")
            if md:
                print("行程规划：\n")
                print(md.strip())
            else:
                # 兜底：如果没生成文，就退回到 detail 提取版
                detailed_itinerary = response.get("detailed_itinerary", {}).get(
                    "itinerary", {}
                )
                if detailed_itinerary:
                    print("行程规划：\n")
                    for day, events in detailed_itinerary.items():
                        print(f"\n{day}:")
                        for e in events:
                            title = e.get("title", "")
                            detail = e.get("detail", "")
                            print(f" - {title}: {detail}")
                else:
                    print("未检测到行程文本，请确认 generate_itinerary() 返回结构。")

        # ---------------- 推荐类任务 ----------------
        elif task_type == "recommendation":
            rec = response.get("recommendations", {})
            summary_text = (
                rec.get("natural_summary") or rec.get("summary") or "（未生成推荐摘要）"
            )
            print("推荐摘要：\n")
            print(summary_text)

        # ---------------- 其他情况 ----------------
        else:
            print(json.dumps(response, ensure_ascii=False, indent=2))

        print("\n****************************************")

        return response

# -*- coding: utf-8 -*-
from NLU_module.main import NLU


def main():
    """主入口函数：启动问候 + 交互"""
    print("你好！我是你的智能旅行助手。")
    print("我可以帮你规划行程、推荐景点、安排美食或住宿。")
    print("示例：")
    print(" - Plan a 4-day trip to Paris with museums and food experiences, budget 8000 yuan.")
    print(" - Recommend top attractions and must-see places in Paris for first-time visitors.")
    print("————————————————————————————————————————————")

    # 初始化系统
    nlu = NLU(with_verifier=True)

    # 循环交互
    while True:
        user_input = input("\n请输入您的问题（或输入 'exit' 退出）：\n> ").strip()
        if user_input.lower() in ["exit", "quit", "退出"]:
            print("感谢使用，再见！祝您旅途愉快 ")
            break
        if not user_input:
            continue

        print("正在思考，请稍候...\n")
        try:
            response = nlu.run(user_input)
        except Exception as e:
            print(f"出错啦: {e}")


if __name__ == "__main__":
    main()

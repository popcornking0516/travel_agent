# agent.py
"""旅行助手入口 - 多智能体版"""
import asyncio
from agents import run_agent

async def chat_with_agent(user_input: str, username: str = "default", history: list = None) -> dict:
    """与旅行助手对话，可传入用户名以加载个人画像"""
    state = await run_agent(user_input, username, history)  # 传递 username
    return {
        "reply": state.get("final_response", ""),
        "params": state.get("extracted_params", {}),
        "task_type": state.get("task_type", ""),
        "next_agent": state.get("next_agent", "")
    }

def reset_memory():
    """重置对话记忆（后续可扩展）"""
    pass
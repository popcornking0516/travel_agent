# agents/weather.py
"""天气查询专家 Agent"""
import os
from langchain_openai import ChatOpenAI
from .utils import call_tool
from dotenv import load_dotenv
load_dotenv()

llm = ChatOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    model=os.getenv("LLM_MODEL"),
    temperature=0.0,
    max_tokens=3000
)

WEATHER_PROMPT = """你是天气查询专家。根据用户需求查询城市天气。

## 你的工具
- get_city_weather: 查询城市天气（参数: city_name）

## 规则
1. 从 state["extracted_params"] 或 user_input 中提取城市名
2. 调用工具，把结果完整写入 state["weather_result"]
"""

async def weather_agent(state: dict) -> dict:
    """天气专家：查询城市天气"""
    params = state.get("extracted_params", {})
    city = params.get("city", "")


    result = await call_tool("get_city_weather", {"city_name": city})
    state["weather_result"] = result
    return state
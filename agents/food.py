# agents/food.py
"""美食推荐专家 Agent"""
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
    max_tokens=5000
)

async def food_agent(state: dict) -> dict:
    """美食专家：搜索城市美食"""
    params = state.get("extracted_params", {})
    city = params.get("city", "")
    cuisine = params.get("cuisine", None)

    tool_params = {"city": city}
    if cuisine:
        tool_params["cuisine"] = cuisine

    result = await call_tool("search_restaurants", tool_params)
    state["food_result"] = result
    return state
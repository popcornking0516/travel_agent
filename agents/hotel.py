# agents/hotel.py
"""酒店推荐专家 Agent"""
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

async def hotel_agent(state: dict) -> dict:
    """酒店专家：搜索城市酒店"""
    params = state.get("extracted_params", {})
    city = params.get("city", "")

    result = await call_tool("search_hotels", {"city": city})
    state["hotel_result"] = result
    return state
# agents/scenic.py
"""景点推荐专家 Agent"""
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

async def scenic_agent(state: dict) -> dict:
    """景点专家：搜索城市景点"""
    params = state.get("extracted_params", {})
    city = params.get("city", "")
    keyword = params.get("keyword", None)

    tool_params = {"city": city}
    if keyword:
        tool_params["keyword"] = keyword

    result = await call_tool("search_scenic_spots", tool_params)
    state["scenic_result"] = result
    return state
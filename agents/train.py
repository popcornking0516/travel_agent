# agents/train.py
"""高铁查询专家 Agent"""
import os
from langchain_openai import ChatOpenAI
from .utils import call_tool
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
load_dotenv()

llm = ChatOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    model=os.getenv("LLM_MODEL"),
    temperature=0.0,
    max_tokens=5000
)

TRAIN_PROMPT = """你是高铁查询专家。用户需要查火车票时，你负责准备参数并调用工具。

## 你的工具
- search_trains: 查询列车（from_station, to_station, date, train_type可选）
- get_current_time: 获取当前日期
- get_station_code: 查询车站代码

## 规则
1. 如果用户说"明天"、"后天"等，必须先调用 get_current_time 获取真实日期
2. 车站名灵活转化：用户说"北京"可以查"北京"（会自动包含北京南、北京西等）
3. 如果用户没说日期，要主动询问时间
4. 你不需要格式化输出，只需把工具返回的结果完整写入 state["train_result"]
"""

async def train_agent(state: dict) -> dict:
    """高铁专家：调用工具查询列车"""
    
    params = state.get("extracted_params", {})
    user_input = state.get("user_input", "")

    # Router 已补全参数，直接使用
    from_station = params.get("from_station", "")
    to_station = params.get("to_station", "")
    date = params.get("date", "")

    # 如果没有日期，获取当前日期并计算（保留你已有的日期逻辑）
    if not date:
        time_result = await call_tool("get_current_time", {})
        try:
            import json
            time_data = json.loads(time_result)
            current_date = datetime.strptime(time_data["date"], "%Y-%m-%d")
            if "明天" in user_input:
                target_date = current_date + timedelta(days=1)
            elif "后天" in user_input:
                target_date = current_date + timedelta(days=2)
            else:
                target_date = current_date
            date = target_date.strftime("%Y-%m-%d")
        except:
            date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # 识别偏好
    preference = None
    if any(w in user_input for w in ["最快", "时间短", "速度"]):
        preference = "fast"
    elif any(w in user_input for w in ["最便宜", "价格", "省钱"]):
        preference = "cheap"
    elif any(w in user_input for w in ["综合", "推荐"]):
        preference = "balanced"

    # 调用工具
    if from_station and to_station and date and from_station != to_station:
        result = await call_tool("search_trains", {
            "from_station": from_station,
            "to_station": to_station,
            "date": date,
            "preference": preference
        })
    elif from_station == to_station:
        result = "💡 出发地和到达地相同，请检查输入"
    else:
        result = "💡 请提供出发站、到达站和日期"

    state["train_result"] = result
    return state
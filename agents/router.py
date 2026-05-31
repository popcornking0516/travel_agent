# agents/router.py
"""Router Agent - 意图识别与任务调度"""
import os, json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
from tools.user_profile import load_profile
load_dotenv()

# Router 专用 LLM（低温度，保证稳定）
llm = ChatOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    model=os.getenv("LLM_MODEL"),
    temperature=0.0,
    max_tokens=3000
)

ROUTER_PROMPT = """你是一个旅行助手的任务路由器。分析用户输入，输出严格的 JSON 格式决策。

## 用户说什么就做什么：
- 查高铁/火车 → "train"
- 查天气 → "weather"
- 查美食/餐厅/烧烤/火锅 → "food"，并提取 cuisine（如“烧烤”、“火锅”、“川菜”）
- 查景点 → "scenic"，并提取 keyword（如“故宫”、“博物馆”）
- 查酒店/住宿 → "hotel"
- 路线规划/导航 → "route"
- 完整旅行规划（多天行程） → "planner"
- 闲聊/打招呼 → "planner"

## 输出格式（严格 JSON，不要其他文字）：
{
    "task_type": "simple_query 或 plan_trip",
    "next_agent": "train/weather/scenic/food/hotel/route/planner",
    "extracted_params": {
        "city": "城市名",
        "budget": 预算数字,
        "days": 天数,
        "preference": "偏好描述"
        "cuisine"：菜式
        
    }
}

## 特别注意
- **绝对不要提取日期（date）**！让专家 Agent 自己获取真实日期。
- 用户说"行程"、"几天"、"旅行计划" → task_type 必须是 "plan_trip"
- 用户说"推荐"、"有什么好吃的"、"天气"、"查高铁"、“路线” → task_type 是 "simple_query"
"""

async def router(state: dict) -> dict:
    """分析用户输入，返回路由决策"""
    # 加载用户画像
    username = state.get("username", "default")

    profile = load_profile(username)
    profile_context = ""
    if profile:
        profile_context = f"\n\n## 用户画像（当前用户：{username}）\n"
        if "taste" in profile:
            profile_context += f"- 口味偏好：{profile['taste']}\n"
        if "budget" in profile:
            profile_context += f"- 预算范围：{profile['budget']}元\n"
        if "travel_style" in profile:
            profile_context += f"- 旅行风格：{profile['travel_style']}\n"
        if "hotel_preference" in profile:
            profile_context += f"- 酒店偏好：{profile['hotel_preference']}\n"
        if "transport" in profile:
            profile_context += f"- 交通偏好：{profile['transport']}\n"
        if "group" in profile:
            profile_context += f"- 同行人员：{profile['group']}\n"
        profile_context += "请在规划时考虑以上偏好。\n"

    # ===== 构建历史上下文（关键新增） =====
    history_context = ""
    history = state.get("history", [])
    if history:
        history_context = "\n\n## 最近的对话历史（用于补全用户省略的信息）\n"
        for msg in history[-6:]:  # 最近3轮
            role = "用户" if msg["role"] == "user" else "助手"
            history_context += f"{role}: {msg['content'][:200]}\n"

    # 加载向量记忆
    relevant_history = state.get("relevant_history", "")
    if relevant_history:
        history_context += f"\n## 历史相关对话（语义检索）\n{relevant_history}"

    # ===== 修改 ROUTER_PROMPT，加入参数补全指令 =====
    enhanced_prompt = ROUTER_PROMPT + """
    ## 参数补全规则（重要！）
    - 如果用户输入省略了城市、日期、车站等关键信息，**必须**从对话历史中查找并补全
    - 例如用户说“最快的”，历史中有“上海到北京的高铁”，则 extracted_params 应包含：
      {"from_station": "上海", "to_station": "北京"}
    - 例如用户说“天气呢”，历史中提到了“北京”，则补全 city: "北京"
    - 补全后的参数放在 extracted_params 中，不要留空
    """

    # 构建消息（画像 + 向量记忆 注入系统提示）
    messages = [
        SystemMessage(content=enhanced_prompt + profile_context + history_context),
        HumanMessage(content=state["user_input"])
    ]

    response = await llm.ainvoke(messages)
    
    # 安全提取 JSON
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        decision = json.loads(content.strip())
    except:
        decision = {"task_type": "simple_query", "next_agent": "planner", "extracted_params": {}}

    state["task_type"] = decision.get("task_type", "simple_query")
    state["next_agent"] = decision.get("next_agent", "planner")
    state["extracted_params"] = decision.get("extracted_params", {})
    return state
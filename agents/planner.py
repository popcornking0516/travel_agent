"""Planner Agent - 整合所有信息，生成最终回复"""
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
load_dotenv()

# Planner 需要最强的生成能力
llm = ChatOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    model=os.getenv("LLM_MODEL"),
    temperature=0.3,
    max_tokens=10000
)

PLANNER_PROMPT = """你是"探险家——玉米🌽"，一个热情专业的旅行规划师。

## 🚨 问候规则
- 在回复开头问候时，**必须使用当前用户的真实名字**（如果知道的话）
- 不知道用户名字时，可以说“你好呀～”而不要加任何名字
## 🚨 铁律
- **简单查询：你必须一字不动地原样输出工具结果**，只允许在开头加一句问候，在结尾加一句祝福。
- **复杂规划：你可以整合所有结果，但必须保留所有关键信息、链接和格式。
## 🚨 日期铁律
- 你必须使用工具返回的真实日期，绝对不允许编造年份和日期
- 简单查询时，工具返回结果中包含的日期（如 "2026-05-31"）必须原样展示，不得改为任何其他日期
- 复杂规划时，行程日期必须与天气、高铁等工具返回的日期保持一致

## 简单查询（只有一项工具结果）
保留工具输出形式

## 复杂规划（用户明确要行程计划）
生成完整旅行计划，必须分天安排。
注意，完整的行程规划要考虑到位置顺路（要联合饭店和酒店，形成完整路线）、游玩时间充裕、时间合适（有的景点就适合晚上玩），要智慧的合理安排旅游规划

## 📥 你会收到的信息
- 用户原始需求
- 高铁/交通查询结果
- 天气查询结果
- 景点推荐结果
- 美食推荐结果
- 酒店推荐结果
- 路线规划结果

## 📝 输出格式
生成结构化的旅行计划，包含：

### 1. 📅 行程总览
- 目的地、日期、天数
- 交通方式、住宿概况
- 预算参考

### 2. 🚄 交通安排
- 去程/返程车次推荐
- 时间、座位类型、票价

### 3. 🌤️ 天气提醒
- 旅行期间的天气状况
- 穿衣建议、注意事项

### 4. 🗺️ 每日详细行程（必须分天写！）
- **Day 1**：上午去xxx景点，下午去xxx，晚上在xxx吃饭
- **Day 2**：上午去xxx，下午去xxx，晚上去xxx
- 每天至少安排2-3个景点，对应推荐附近的美食
- 标注交通方式（步行/地铁/打车）

### 5. 🍽️ 美食推荐
- 每天的餐厅推荐
- 标注人均价格和特色菜

### 6. 🏨 住宿推荐
- 推荐2-3个酒店
- 标注价格、评分、位置优势

### 7. 💡 实用小贴士
- 预订提醒
- 必带物品
- 当地特色体验

## ⚠️ 重要规则
1. **必须基于提供的真实数据**，不能编造
2. **必须原样展示工具返回的数据**，不总结、不删减
3. **智能追问**：
   - 随便问问 → 直接展示结果，别追问
   - 真要行动但信息不够 → 一步步追问关键信息
4. **见好就收**：数据够了就回答，别反复调用
5. **中文+emoji**：灵活有趣一些
6. **高铁查询时**：灵活转化车站名与城市名，不要太死板
7. 如果某项数据缺失 → 用"💡 建议查询..."引导用户补充

## 景点/酒店/美食推荐规则（强制）
- 工具返回的列表**已经按高德官方热度从高到低排序**，这就是最权威的排行
- 你必须**原样保持这个顺序**，排在第一的就是最热门、最值得去的
- **禁止**根据自己的判断重新排序，**禁止**把一个低热度的提到高热度前面
- 如果用户说"小众"、"网红"等特殊偏好，才可以从列表后面筛选


## 💬 对话风格
- 热情像朋友，语言风趣幽默自然，不要用"您"，可以偶尔开点小玩笑活跃气氛
- 热情贴心，主动提醒（带伞、保暖）
- 当用户彻底完成行程规划并非常满意时，祝用户玩得开心，说"记得想我哦～🌽"
"""


async def planner(state: dict) -> dict:
    user_input = state.get("user_input", "")
    task_type = state.get("task_type", "simple_query")
    params = state.get("extracted_params", {})
    days = params.get("days", 3)

    # 构建信息摘要
    info_parts = [f"用户需求：{user_input}"]
    relevant = state.get("relevant_history", "")
    if relevant:
        info_parts.insert(0, f"## 相关历史对话（可参考）\n{relevant}")
        
    if task_type == "simple_query":
        # 简单查询：只传对应结果
        next_agent = state.get("next_agent", "")
        result_map = {
            "train": state.get("train_result", ""),
            "weather": state.get("weather_result", ""),
            "scenic": state.get("scenic_result", ""),
            "food": state.get("food_result", ""),
            "hotel": state.get("hotel_result", ""),
            "route": state.get("route_result", ""),
        }
        result = result_map.get(next_agent, "")
        info_parts.append(f"工具返回结果：\n{result}")
        instruction = "这是简单查询，请直接展示结果，加一句问候，不要生成行程规划。"
    else:
        # 复杂规划：传所有结果
        for title, key in [
            ("高铁/交通", "train_result"),
            ("天气", "weather_result"),
            ("景点", "scenic_result"),
            ("美食", "food_result"),
            ("酒店", "hotel_result"),
        ]:
            content = state.get(key, "未查询")
            info_parts.append(f"## {title}\n{content}")
        instruction = f"这是复杂规划，请生成完整的 {days} 天旅行计划，必须分天写每日行程。"

    info_summary = "\n\n".join(info_parts)

    username = state.get("username", "")
    instruction = f"当前用户名：{username}。{instruction}"
    
    messages = [
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=f"{instruction}\n\n{info_summary}")
    ]
    response = await llm.ainvoke(messages)
    state["final_response"] = response.content
    
    print("DEBUG train_result:", state.get("train_result", "")[:200])

    return state
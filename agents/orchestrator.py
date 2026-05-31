# agents/orchestrator.py
"""编排器 - 控制多 Agent 协作流程（无 LLM，纯控制流）"""
from .router import router
from .train import train_agent
from .weather import weather_agent
from .scenic import scenic_agent
from .food import food_agent
from .hotel import hotel_agent
from .planner import planner
from agents.memory import search_memory

async def run_agent(user_input: str, username: str = "default", history: list = None) -> dict:
    """多智能体主入口"""
    relevant = search_memory(username, user_input, n_results=5)

    # 初始化共享状态
    state = {
        "user_input": user_input,
        "username": username,        
        "history": history or [],          # ← 原始对话历史列表
        "relevant_history": relevant,      # ← 向量检索到的历史（供 Router/Planner 用）
        "task_type": "",
        "next_agent": "",
        "extracted_params": {},
        "last_city": "",              
        "train_result": "",
        "weather_result": "",
        "scenic_result": "",
        "food_result": "",
        "hotel_result": "",
        "final_response": ""
    }

    # 1. Router 判断意图
    state = await router(state)
    task_type = state["task_type"]
    next_agent = state["next_agent"]

    # 2. 根据意图执行
    if task_type == "simple_query":
        # 简单查询：只调用对应的专家
        agent_map = {
            "train": train_agent,
            "weather": weather_agent,
            "scenic": scenic_agent,
            "food": food_agent,
            "hotel": hotel_agent,
        }

        if next_agent == "route":
            # 路线规划：直接调用工具，不走专家Agent
            from tools.gaode_tool import plan_route
            params = state.get("extracted_params", {})
            # === 参数名转换：Router 可能用 from/to 或 origin/destination ===
            mapped_params = {}
            mapped_params["origin"] = params.get("origin") or params.get("from", "")
            mapped_params["destination"] = params.get("destination") or params.get("to", "")
            mapped_params["route_type"] = params.get("route_type", "driving")  # 默认驾车
            
            result = await plan_route.ainvoke(mapped_params)

            state["route_result"] = result
            state = await planner(state)  # 让 Planner 包装输出
            return state

        if next_agent in agent_map:
            state = await agent_map[next_agent](state)
            # 结果已写入 state，直接走 Planner 包装
            state = await planner(state)
        else:
            # 路线规划或闲聊，直接 Planner
            state = await planner(state)
    else:
        # 复杂规划：依次调用所有专家
        for agent in [train_agent, weather_agent, scenic_agent, food_agent, hotel_agent]:
            try:
                state = await agent(state)
            except Exception as e:
                # 某个专家失败不影响其他
                pass
        # Planner 整合
        state = await planner(state)

    return state
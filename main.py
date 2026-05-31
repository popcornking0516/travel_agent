from fastapi import FastAPI
from pydantic import BaseModel
from agent import agent_executor

app = FastAPI(title="🌽玉米旅行助手Agent后端")

# 定义请求参数
class TravelRequest(BaseModel):
    query: str  # 用户的旅行需求

# 旅行规划接口
@app.post("/plan_travel")
def plan_travel(req: TravelRequest):
    result = agent_executor.invoke({"input": req.query})
    return {"code": 200, "data": result["output"]}

# 启动命令：uvicorn main:app --reload --port 8001
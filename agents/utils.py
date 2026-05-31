# agents/utils.py
"""工具调用辅助函数"""
from tools import ALL_TOOLS

# 构建工具名 -> 工具对象的映射
TOOL_MAP = {tool.name: tool for tool in ALL_TOOLS}

async def call_tool(tool_name: str, params: dict) -> str:
    """异步调用 LangChain 工具，返回结果字符串"""
    tool = TOOL_MAP.get(tool_name)
    if not tool:
        return f"❌ 工具 {tool_name} 未找到"
    try:
        if hasattr(tool, 'ainvoke'):
            result = await tool.ainvoke(params)
        else:
            result = tool.invoke(params)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"❌ 工具调用失败: {str(e)}"
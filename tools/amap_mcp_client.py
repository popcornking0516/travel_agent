# tools/amap_mcp_client.py
"""高德地图 MCP 客户端（LangChain 适配）"""
import os
from typing import List, Optional
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack
from dotenv import load_dotenv

load_dotenv()

_amap_tools: Optional[List[BaseTool]] = None
_exit_stack: Optional[AsyncExitStack] = None


async def get_amap_tools() -> List[BaseTool]:
    """获取高德 MCP 工具列表（单例，保持长连接）"""
    global _amap_tools, _exit_stack

    if _amap_tools is not None:
        return _amap_tools

    amap_key = os.getenv("GAODE_KEY")
    if not amap_key:
        raise ValueError("请在 .env 中设置 GAODE_KEY")

    server_params = StdioServerParameters(
        command="uvx",
        args=["amap-mcp-server"],
        env={"AMAP_MAPS_API_KEY": amap_key},
    )

    # 使用 AsyncExitStack 管理异步上下文，保持会话打开
    _exit_stack = AsyncExitStack()
    read, write = await _exit_stack.enter_async_context(stdio_client(server_params))
    session = await _exit_stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    tools = await load_mcp_tools(session)

    _amap_tools = tools
    print(f"✅ 高德 MCP 工具加载完成，共 {len(tools)} 个工具")
    for tool in tools:
        print(f"   - {tool.name}")
    return tools


def get_amap_tool_by_name(name: str) -> BaseTool:
    """根据名称获取单个 MCP 工具（需先调用 get_amap_tools）"""
    if _amap_tools is None:
        raise RuntimeError("请先调用 get_amap_tools() 加载工具")
    for tool in _amap_tools:
        if tool.name == name:
            return tool
    raise ValueError(f"未找到工具: {name}")


async def close_amap():
    """关闭 MCP 连接（应用退出时调用）"""
    global _exit_stack, _amap_tools
    if _exit_stack:
        await _exit_stack.aclose()
        _exit_stack = None
    _amap_tools = None
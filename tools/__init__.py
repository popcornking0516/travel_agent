# tools/__init__.py
from .mcp_12306 import (
    search_trains,        # 高铁查询（支持时间段筛选、偏好排序）
    get_station_code,     # 车站信息查询
    get_current_time,     # 当前时间获取
    ask_user_preference,  # 用户偏好询问
)
from .weather_tool import get_city_weather
from .gaode_tool import (
    search_scenic_spots,
    search_hotels,
    search_restaurants,
    plan_route,      
    geocode,          
)
from .user_profile import update_user_profile


# 所有工具集合
ALL_TOOLS = [
    # 12306 高铁相关
    search_trains,         # 核心：查询列车
    get_station_code,      # 辅助：验证车站
    get_current_time,      # 辅助：日期计算

    # 天气相关
    get_city_weather,      # 目的地天气
    
    # 地图相关
    search_scenic_spots,   # 景点搜索
    search_hotels,         # 酒店搜索
    search_restaurants,    # 美食搜索
    plan_route,            # 路线规划
    geocode,                # 地理编码
    update_user_profile,
    ]
"""
天气查询工具
使用 Open-Meteo API（免费无需key）+ 高德地图地理编码
"""
import os
import requests
from typing import Optional
from langchain.tools import tool
from dotenv import load_dotenv

# ===== 加载环境变量 =====
load_dotenv()  # 自动加载项目根目录的 .env 文件

# ============== 城市名转经纬度 ==============
def city_to_lat_lon(city_name: str) -> Optional[tuple]:
    """
    城市名 → 经纬度（高德地图地理编码）
    
    Args:
        city_name: 城市名，如"北京"、"上海虹桥"
    
    Returns:
        (lat, lon, formatted_name) 或 None
    """
    gaode_key = os.getenv("GAODE_KEY")
    
    if not gaode_key:
        print("⚠️ 未设置 GAODE_KEY 环境变量")
        return None
    
    try:
        res = requests.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={
                "key": gaode_key,
                "address": city_name,
                "output": "json"
            },
            timeout=10
        )
        data = res.json()
        
        if data.get("status") == "1" and data.get("geocodes"):
            location = data["geocodes"][0]["location"]
            formatted_name = data["geocodes"][0].get("formatted_address", city_name)
            lon, lat = location.split(",")
            return float(lat), float(lon), formatted_name
        
        print(f"⚠️ 未找到城市: {city_name}")
        return None
        
    except Exception as e:
        print(f"❌ 地理编码失败: {e}")
        return None


# ============== 天气代码转中文描述 ==============
def weather_code_to_text(code: int) -> tuple:
    """
    Open-Meteo 天气代码 → 中文描述 + emoji
    
    参考: https://open-meteo.com/en/docs
    """
    weather_map = {
        0:  ("晴天", "☀️"),
        1:  ("大部晴朗", "🌤️"),
        2:  ("多云", "⛅"),
        3:  ("阴天", "☁️"),
        45: ("雾", "🌫️"),
        48: ("雾凇", "🌫️"),
        51: ("小毛毛雨", "🌦️"),
        53: ("毛毛雨", "🌦️"),
        55: ("大毛毛雨", "🌧️"),
        56: ("冻毛毛雨", "🌨️"),
        57: ("冻毛毛雨", "🌨️"),
        61: ("小雨", "🌧️"),
        63: ("中雨", "🌧️"),
        65: ("大雨", "⛈️"),
        66: ("冻雨", "🌨️"),
        67: ("冻雨", "🌨️"),
        71: ("小雪", "🌨️"),
        73: ("中雪", "❄️"),
        75: ("大雪", "❄️"),
        77: ("雪粒", "🌨️"),
        80: ("阵雨", "🌦️"),
        81: ("中阵雨", "🌧️"),
        82: ("大阵雨", "⛈️"),
        85: ("小阵雪", "🌨️"),
        86: ("大阵雪", "❄️"),
        95: ("雷暴", "⛈️"),
        96: ("冰雹雷暴", "⛈️"),
        99: ("大冰雹雷暴", "⛈️"),
    }
    return weather_map.get(code, ("未知", "🤔"))


# ============== 天气工具 ==============
@tool
def get_city_weather(city_name: str) -> str:
    """
    查询指定城市的实时天气和未来预报。
    
    参数:
    - city_name: 城市名称，支持中文（如"北京"、"上海"、"杭州"）
    
    返回:
    - 包含温度、风速、天气状况、体感建议的详细信息
    
    使用场景:
    - 出行前查看目的地天气
    - 比较多个城市的天气
    - 根据天气建议穿衣/带伞
    """
    # 1. 地理编码
    geo_result = city_to_lat_lon(city_name)
    if not geo_result:
        return f"❌ 无法找到城市「{city_name}」，请检查城市名称是否正确"
    
    lat, lon, formatted_name = geo_result
    
    # 2. 请求天气数据（增加更多参数）
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True,           # 当前天气
        "daily": [
            "weathercode",                  # 天气代码
            "temperature_2m_max",           # 最高温
            "temperature_2m_min",           # 最低温
            "precipitation_probability_max", # 降雨概率
            "wind_speed_10m_max",           # 最大风速
        ],
        "timezone": "Asia/Shanghai",
        "forecast_days": 3,                # 预报3天
    }
    
    try:
        data = requests.get(url, params=params, timeout=10).json()
        
        # 3. 解析当前天气
        current = data.get("current_weather", {})
        temp = current.get("temperature", "?")
        wind_speed = current.get("windspeed", "?")
        weather_code = current.get("weathercode", 0)
        
        weather_desc, weather_emoji = weather_code_to_text(weather_code)
        
        # 4. 构建友好输出
        result = f"{weather_emoji} **{formatted_name}** 当前天气\n"
        result += "─" * 35 + "\n"
        result += f"🌡️  温度：{temp}°C\n"
        result += f"💨  风速：{wind_speed} km/h\n"
        result += f"👀  天气：{weather_desc}\n"
        
        # 5. 体感建议
        temp_val = float(temp) if temp != "?" else 20
        if temp_val >= 35:
            result += f"\n🥵 非常炎热，注意防暑降温！"
        elif temp_val >= 30:
            result += f"\n😎 天气较热，建议穿轻薄衣物"
        elif temp_val >= 20:
            result += f"\n😊 温度舒适，适合出行"
        elif temp_val >= 10:
            result += f"\n🧥 天气较凉，建议带外套"
        elif temp_val >= 0:
            result += f"\n🧣 天气寒冷，注意保暖"
        else:
            result += f"\n🥶 非常寒冷，穿厚衣服！"
        
        if weather_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            result += f" ☂️ 记得带伞！"
        
        # 6. 未来天气预报
        daily = data.get("daily", {})
        if daily:
            result += f"\n\n📅 **未来天气**\n"
            result += "─" * 35 + "\n"
            
            dates = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            weather_codes = daily.get("weathercode", [])
            rain_probs = daily.get("precipitation_probability_max", [])
            
            for i in range(min(3, len(dates))):
                date_str = dates[i]
                max_t = max_temps[i] if i < len(max_temps) else "?"
                min_t = min_temps[i] if i < len(min_temps) else "?"
                code = weather_codes[i] if i < len(weather_codes) else 0
                rain = rain_probs[i] if i < len(rain_probs) else 0
                
                w_desc, w_emoji = weather_code_to_text(code)
                
                # 格式化日期
                from datetime import datetime
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    date_display = dt.strftime("%m月%d日") + (" (今天)" if i == 0 else " (明天)" if i == 1 else "")
                except:
                    date_display = date_str
                
                result += f"{w_emoji} {date_display}: {w_desc}，{min_t}°C ~ {max_t}°C"
                if rain > 0:
                    result += f"，降雨概率 {rain}%"
                result += "\n"
        
        return result
        
    except requests.exceptions.Timeout:
        return f"❌ 天气查询超时，请稍后重试"
    except requests.exceptions.ConnectionError:
        return f"❌ 无法连接到天气服务"
    except Exception as e:
        return f"❌ 获取{city_name}天气失败: {str(e)}"


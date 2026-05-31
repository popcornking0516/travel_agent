# mcp_12306.py
import os
import requests
import uuid
import json
from typing import Optional, Dict, Any, List
from langchain.tools import tool
from datetime import datetime, time


class SimpleMCPClient:
    """最简单的MCP客户端"""
    
    def __init__(self, url: str):
        self.url = url
        self.session_id = None
    
    def initialize(self):
        """初始化会话"""
        response = requests.post(
            self.url,
            json={
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "agent", "version": "1.0"}
                }
            },
            headers={"Content-Type": "application/json"}
        )
        self.session_id = response.headers.get("Mcp-Session-Id")
        return self.session_id
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict:
        """调用工具"""
        if not self.session_id:
            self.initialize()
        
        response = requests.post(
            self.url,
            json={
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            },
            headers={
                "Content-Type": "application/json",
                "Mcp-Session-Id": self.session_id
            }
        )
        return response.json()


# 全局客户端
_client = SimpleMCPClient(os.getenv("MCP_12306_URL", "http://localhost:8000/mcp"))


def parse_mcp_response(data: Dict) -> list:
    """解析MCP响应，提取列车列表"""
    if "result" not in data:
        return []
    
    mcp_result = data["result"]
    
    if "content" in mcp_result and len(mcp_result["content"]) > 0:
        text = mcp_result["content"][0].get("text", "")
        
        try:
            parsed = json.loads(text)
            
            if isinstance(parsed, list):
                return parsed
            
            if isinstance(parsed, dict):
                for key in ["trains", "result", "data", "tickets"]:
                    if key in parsed and parsed[key]:
                        return parsed[key]
                
                if "train_no" in parsed:
                    return [parsed]
        
        except json.JSONDecodeError:
            pass
    
    return []


# ========== 新增：时间段解析工具 ==========

def parse_time_range(user_input: str) -> tuple:
    """
    灵活解析用户的时间段表达
    
    支持格式：
    - "上午8点到9点"
    - "8:00-9:00"
    - "早上8点到中午12点"
    - "下午3点到5点"
    - "晚上8点到10点"
    
    返回: (start_hour, start_minute, end_hour, end_minute)
    """
    import re
    
    # 时间段映射
    period_map = {
        "凌晨": (0, 6),
        "早上": (6, 9),
        "上午": (8, 12),
        "中午": (11, 13),
        "下午": (12, 18),
        "傍晚": (17, 19),
        "晚上": (18, 24),
        "夜间": (21, 24),
    }
    
    # 先处理中文时段描述
    start_offset = 0
    end_offset = 0
    
    for period, (base_start, base_end) in period_map.items():
        if period in user_input and "点" not in user_input.split(period)[0][-2:]:
            start_offset = base_start
            end_offset = base_start
            user_input = user_input.replace(period, "")
            break
    
    # 提取所有数字
    numbers = re.findall(r'(\d+)(?::(\d+))?', user_input)
    
    if len(numbers) >= 2:
        # 格式：8点到9点、8:00-9:00
        hour1 = int(numbers[0][0])
        min1 = int(numbers[0][1]) if numbers[0][1] else 0
        hour2 = int(numbers[1][0])
        min2 = int(numbers[1][1]) if numbers[1][1] else 0
        
        # 如果有时段偏移（如"下午3点"），加12
        if start_offset >= 12 and hour1 < 12:
            hour1 += 12
        if end_offset >= 12 and hour2 < 12:
            hour2 += 12
        
        return (hour1, min1, hour2, min2)
    
    elif len(numbers) == 1:
        # 只有一个时间点，创建一个1小时的范围
        hour = int(numbers[0][0])
        min_val = int(numbers[0][1]) if numbers[0][1] else 0
        
        if start_offset >= 12 and hour < 12:
            hour += 12
        
        return (hour, min_val, hour + 2, 0)  # 默认2小时范围
    
    return (0, 0, 24, 0)  # 全天


def filter_by_time(trains: List[Dict], time_input: str) -> List[Dict]:
    """
    按时间段过滤列车
    
    Args:
        trains: 列车列表
        time_input: 用户的时间段描述
    
    Returns:
        过滤后的列车列表
    """
    if not time_input or not trains:
        return trains
    
    try:
        start_h, start_m, end_h, end_m = parse_time_range(time_input)
        
        filtered = []
        for train in trains:
            start_time_str = train.get("start_time", "")
            if not start_time_str:
                filtered.append(train)
                continue
            
            try:
                # 解析出发时间
                train_h, train_m = map(int, start_time_str.split(":"))
                train_time = train_h * 60 + train_m
                
                # 时间范围
                range_start = start_h * 60 + start_m
                range_end = end_h * 60 + end_m
                
                if range_start <= train_time <= range_end:
                    filtered.append(train)
            except:
                # 解析失败，保留该车次
                filtered.append(train)
        
        return filtered if filtered else trains  # 如果过滤后为空，返回全部
        
    except Exception:
        return trains  # 解析失败，返回全部


# ========== 新增：排序和偏好处理 ==========

def sort_trains(trains: List[Dict], preference: Optional[str] = None) -> tuple:
    """
    按用户偏好排序列车
    
    Args:
        trains: 列车列表
        preference: 用户偏好
            - "fast" 或 "时间短" 或 "最快"
            - "cheap" 或 "便宜" 或 "最便宜"
            - "balanced" 或 "综合" 或 None
    
    Returns:
        (排序后的列车列表, 分析结果)
    """
    if not trains or not preference:
        return trains, ""
    
    preference = preference.lower()
    analysis = ""
    
    # 解析每趟列车的时长（分钟）
    def get_duration_minutes(train):
        duration = train.get("duration", "00:00")
        try:
            parts = duration.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except:
            return 9999
    
    # 获取票价（取二等座价格作为参考）
    def get_price(train):
        seats = train.get("seats", {})
        # 优先取二等座
        price_str = train.get("second_price") or train.get("price") or "0"
        try:
            return float(str(price_str).replace("¥", "").replace(",", ""))
        except:
            return 9999
    
    if preference in ["fast", "时间短", "最快", "速度优先"]:
        # 按时长升序
        sorted_trains = sorted(trains, key=get_duration_minutes)
        
        # 生成分析
        fastest = sorted_trains[0]
        slowest = sorted_trains[-1]
        analysis = (
            f"\n📊 按速度排序分析：\n"
            f"• 最快：{fastest['train_no']}（历时{fastest['duration']}）\n"
            f"• 最慢：{slowest['train_no']}（历时{slowest['duration']}）\n"
            f"• 平均历时：{sum(get_duration_minutes(t) for t in trains)//len(trains)}分钟\n"
        )
    
    elif preference in ["cheap", "便宜", "最便宜", "价格优先"]:
        # 按价格升序
        sorted_trains = sorted(trains, key=get_price)
        
        # 生成分析
        cheapest = sorted_trains[0]
        most_expensive = sorted_trains[-1]
        analysis = (
            f"\n📊 按价格排序分析：\n"
            f"• 最便宜：{cheapest['train_no']}\n"
            f"• 最贵：{most_expensive['train_no']}\n"
            f"• 平均票价：¥{sum(get_price(t) for t in trains)/len(trains):.1f}\n"
        )
    
    elif preference in ["balanced", "综合", "性价比", "推荐"]:
        # 综合评分：时长和价格各占50%
        max_duration = max(get_duration_minutes(t) for t in trains)
        max_price = max(get_price(t) for t in trains)
        
        def comprehensive_score(train):
            if max_duration == 0 or max_price == 0:
                return 0
            duration_score = 1 - (get_duration_minutes(train) / max_duration)
            price_score = 1 - (get_price(train) / max_price)
            return (duration_score + price_score) / 2
        
        sorted_trains = sorted(trains, key=comprehensive_score, reverse=True)
        
        # 生成分析
        best = sorted_trains[0]
        analysis = (
            f"\n📊 综合推荐分析：\n"
            f"• 🥇 最推荐：{best['train_no']}\n"
            f"  - 历时：{best['duration']}\n"
            f"  - 出发：{best['start_time']}，到达：{best['arrive_time']}\n"
            f"• 💡 该车次在时间和价格间取得了最佳平衡\n"
        )
    
    else:
        sorted_trains = trains
    
    return sorted_trains, analysis


# ========== 改进的 search_trains 工具 ==========

@tool
def search_trains(
    from_station: str,
    to_station: str,
    date: str,
    train_type: Optional[str] = None,
    time_range: Optional[str] = None,
    preference: Optional[str] = None
) -> str:
    """
    查询12306高铁和列车信息。
    支持按时间段筛选和按偏好排序。
    
    参数:
    - from_station: 出发站名称，如：北京、上海虹桥
    - to_station: 到达站名称，如：杭州东、广州南
    - date: 查询日期，格式YYYY-MM-DD，如：2026-06-01
    - train_type: 列车类型过滤（可选），如：G=高铁、D=动车
    - time_range: 时间段筛选（可选），支持灵活表达：
      如："上午8点到9点"、"8:00-9:00"、"早上6点到中午12点"、"下午3点到5点"
    - preference: 排序偏好（可选），支持：
      "fast"=最快、"cheap"=最便宜、"balanced"=综合推荐
    
    返回:
    - 包含车次、时间、座位余票的详细信息，带智能排序和分析
    """
    try:
        arguments = {
            "from_station": from_station,
            "to_station": to_station,
            "train_date": date
        }
        
        # 调用MCP工具
        data = _client.call_tool("query-tickets", arguments)
        
        # 解析响应
        trains = parse_mcp_response(data)
        
        if not trains:
            return f"❌ 未找到 {date} 从 {from_station} 到 {to_station} 的列车信息\n💡 提示：请检查车站名称和日期是否正确"
        
        # 记录原始数量
        total_count = len(trains)
        filter_info = []
        
        # 1. 按列车类型过滤
        if train_type:
            trains = [t for t in trains if t.get("train_no", "").startswith(train_type.upper())]
            filter_info.append(f"🚂 类型：{train_type}类")
            if not trains:
                return f"❌ 未找到 {date} 从 {from_station} 到 {to_station} 的 {train_type} 类列车"
        
        # 2. 按时间段过滤
        if time_range:
            before_count = len(trains)
            trains = filter_by_time(trains, time_range)
            after_count = len(trains)
            filter_info.append(f"⏰ 时间段：{time_range}（{before_count}→{after_count}趟）")
        
        # 3. 按偏好排序
        sort_analysis = ""
        if preference and trains:
            trains, sort_analysis = sort_trains(trains, preference)
            pref_map = {
                "fast": "速度优先",
                "cheap": "价格优先",
                "balanced": "综合推荐"
            }
            filter_info.append(f"📈 排序：{pref_map.get(preference, preference)}")
        
        # 构建输出
        result = f"🚄 {from_station} → {to_station} ({date})\n"
        result += "=" * 70 + "\n"
        
        # 显示筛选信息
        if filter_info:
            result += "🔍 筛选条件：" + " | ".join(filter_info) + "\n"
        
        result += f"📊 共 {len(trains)} 趟列车（原始{total_count}趟）:\n\n"
        
        # 显示列车信息
        display_count = min(len(trains), 10)
        for idx, train in enumerate(trains[:display_count], 1):
            train_no = train.get("train_no", "未知")
            start_time = train.get("start_time", "?")
            arrive_time = train.get("arrive_time", "?")
            duration = train.get("duration", "?")
            from_st = train.get("from_station", from_station)
            to_st = train.get("to_station", to_station)
            
            # 特殊标记：第一推荐
            prefix = "🥇 " if (preference and idx == 1) else "   "
            
            result += f"{idx:2d}. {prefix}【{train_no}】{from_st} → {to_st}\n"
            result += f"    ⏰ {start_time} → {arrive_time} (历时{duration})\n"
            
            # 座位信息
            seats = train.get("seats", {})
            if seats:
                seat_parts = []
                seat_emoji = {
                    "business": "👑",
                    "first_class": "🥇", 
                    "second_class": "🥈",
                    "no_seat": "🚶"
                }
                seat_names = {
                    "business": "商务座",
                    "first_class": "一等座",
                    "second_class": "二等座",
                    "no_seat": "无座"
                }
                
                for seat_key in ["business", "first_class", "second_class", "no_seat"]:
                    if seat_key in seats:
                        count = seats[seat_key]
                        emoji = seat_emoji.get(seat_key, "💺")
                        name = seat_names.get(seat_key, seat_key)
                        
                        if count == "有":
                            seat_parts.append(f"{emoji}{name}: ✅")
                        elif count == "无":
                            seat_parts.append(f"{emoji}{name}: ❌")
                        elif count.isdigit() and count != "0":
                            seat_parts.append(f"{emoji}{name}: {count}张")
                        else:
                            seat_parts.append(f"{emoji}{name}: {count}")
                
                result += "    " + " | ".join(seat_parts) + "\n"
            
            result += "\n"
        
        # 添加排序分析
        if sort_analysis:
            result += sort_analysis
        
        result += "=" * 70
        if len(trains) > display_count:
            result += f"\n💡 共 {len(trains)} 趟列车，显示前 {display_count} 趟"
        
        # 如果没有设置偏好，给出建议
        if not preference and len(trains) > 0:
            result += "\n💡 提示：可以告诉我你的偏好（如'最快的'、'最便宜的'、'综合推荐'），我帮你排序"
        
        return result
        
    except Exception as e:
        import traceback
        print(f"❌ 错误详情:\n{traceback.format_exc()}")
        return f"❌ 查询失败: {str(e)}"


# ========== 新增：偏好询问工具 ==========

@tool
def ask_user_preference(context: str) -> str:
    """
    当需要了解用户的出行偏好时使用。
    帮助用户明确是更看重时间、价格还是综合体验。
    
    参数:
    - context: 当前查询的上下文信息，如："北京到上海，6月1日"
    
    返回:
    - 引导用户选择偏好的问题
    """
    return (
        f"🤔 关于 {context} 的行程，你更看重哪个方面呢？\n\n"
        f"1. ⚡ 时间优先 - 帮我找最快的车次\n"
        f"2. 💰 价格优先 - 帮我找最便宜的\n"
        f"3. 🎯 综合推荐 - 平衡时间和价格\n\n"
        f"你也可以直接说：'要最快的'、'越便宜越好'、或者'推荐个综合最优的'"
    )


@tool
def get_station_code(station_name: str) -> str:
    """
    查询火车站信息。
    
    参数:
    - station_name: 车站名称，如：上海虹桥
    
    返回:
    - 车站详细信息
    """
    try:
        data = _client.call_tool("search-stations", {
            "query": station_name,
            "limit": 5
        })
        
        if "result" in data:
            mcp_result = data["result"]
            if "content" in mcp_result and len(mcp_result["content"]) > 0:
                text = mcp_result["content"][0].get("text", "")
                try:
                    parsed = json.loads(text)
                    stations = parsed.get("stations", [])
                    if stations:
                        result = f"🔍 找到 {len(stations)} 个车站:\n"
                        for station in stations[:5]:
                            result += f"  📍 {station['name']} (代码: {station['code']})\n"
                        return result
                except:
                    return text
        
        return f"未找到车站: {station_name}"
        
    except Exception as e:
        return f"❌ 查询失败: {str(e)}"


@tool
def get_current_time() -> str:
    """
    获取当前日期和时间，用于确认查询日期。
    """
    try:
        data = _client.call_tool("get-current-time", {})
        
        if "result" in data:
            mcp_result = data["result"]
            if "content" in mcp_result and len(mcp_result["content"]) > 0:
                return mcp_result["content"][0].get("text", "无法获取时间")
        
        return "无法获取当前时间"
        
    except Exception as e:
        return f"❌ 获取时间失败: {str(e)}"

if __name__ == "__main__":
    print("🧪 测试12306高铁查询...\n")
    
    # 测试查询
    result = search_trains.invoke({
        "from_station": "北京",
        "to_station": "上海",
        "date": "2026-06-01"
    })
    print(result)
    
    print("\n" + "="*70 + "\n")
    
    # 测试高铁过滤
    result_g = search_trains.invoke({
        "from_station": "北京",
        "to_station": "上海",
        "date": "2026-06-01",
        "train_type": "G"
    })
    print(result_g)

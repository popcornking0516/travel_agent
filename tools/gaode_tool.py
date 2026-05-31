"""
高德地图POI搜索工具
支持：景点、酒店、餐厅搜索，带价格、评分、距离计算
"""
import os
import json
from typing import Optional, List, Dict
from langchain.tools import tool
from dotenv import load_dotenv
from urllib.parse import quote   
from pypinyin import lazy_pinyin
from .amap_mcp_client import get_amap_tools, get_amap_tool_by_name

load_dotenv()
_amap_tools_loaded = False

async def init_amap():
    global _amap_tools_loaded
    if not _amap_tools_loaded:
        await get_amap_tools()
        _amap_tools_loaded = True

# ============== 工具函数 ==============

def get_baidu_image(poi_name: str) -> str:
    """百度图片兜底"""
    try:
        import requests
        url = "https://image.baidu.com/search/acjson"
        params = {"tn": "resultjson_com", "word": f"{poi_name} 实景", "pn": 0, "rn": 1}
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, params=params, headers=headers, timeout=5)
        data = res.json()
        imgs = data.get("data", [])
        if imgs and imgs[0].get("thumbURL"):
            return imgs[0]["thumbURL"]
    except:
        pass
    return ""

def format_rating(rating) -> str:
    """格式化评分显示"""
    try:
        score = float(rating)
        if score >= 4.5: return f"🤩{rating} 非常好"
        elif score >= 4.0: return f"😍{rating} 很好"
        elif score >= 3.5: return f"😊{rating} 不错"
        elif score >= 3.0: return f"😬{rating} 一般"
        else: return f"😢{rating} 不好"
    except:
        return str(rating) if rating else "暂无评分"

def calculate_distance(lon1, lat1, lon2, lat2):
    """计算两点间距离（km）"""
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return round(R * c, 1)

# ============== 景点搜索 ==============
@tool
async def search_scenic_spots(
    city: str, keyword: Optional[str] = None, price_range: Optional[str] = None,
    user_lon: Optional[float] = None, user_lat: Optional[float] = None
) -> str:
    """
    搜索城市景点，包含票价、评分、图片和简介。
    
    参数:
    - city: 城市名，如"北京"、"杭州"
    - keyword: 景点关键词（可选），如"故宫"、"西湖"、"博物馆"
    - price_range: 价格范围（可选），如"免费"、"50以内"、"100-200"
    - user_lon: 用户当前经度（可选），用于计算距离
    - user_lat: 用户当前纬度（可选），用于计算距离
    
    返回:
    - 景点列表，包含票价、评分、距离、简介
    """
    if not _amap_tools_loaded:
        await init_amap()

    if not keyword:
        keywords = "景点"  # 高德默认按热度排序
    else:
        keywords = f"{keyword}|景点"

    try:
        # 1. 搜索POI列表
        search_tool = get_amap_tool_by_name("maps_text_search")
        result = await search_tool.ainvoke({
            "keywords": keywords,
            "city": city,
            "citylimit": "true"
        })
        # 解析MCP返回格式：[{"type":"text","text":"{...}"}]
        data = json.loads(result[0]["text"])
        pois = data.get("pois", [])

        if not pois:
            return f"❌ 未在{city}找到相关景点"

        # 2. 批量获取详情以补充评分、价格等信息
        detail_tool = get_amap_tool_by_name("maps_search_detail")
        enriched = []
        for poi in pois[:10]:  # 限制前10个以节省时间
            try:
                detail_res = await detail_tool.ainvoke({"id": poi["id"]})
                detail = json.loads(detail_res[0]["text"])
                # 合并字段
                poi["rating"] = detail.get("rating", "")
                poi["cost"] = detail.get("cost", [])
                poi["open_time"] = detail.get("open_time", "")
                poi["business_area"] = detail.get("business_area", "")
                poi["location"] = detail.get("location", "")
            except:
                pass
            enriched.append(poi)

        # 3. 价格过滤
        if price_range:
            filtered = []
            for poi in enriched:
                cost = poi.get("cost", [])
                cost_val = cost[0] if isinstance(cost, list) and cost else "免费"
                if price_range == "免费" and ("免费" in str(cost_val) or not cost_val):
                    filtered.append(poi)
                elif "以内" in price_range:
                    max_price = float(price_range.replace("以内", ""))
                    try:
                        if float(cost_val) <= max_price:
                            filtered.append(poi)
                    except:
                        filtered.append(poi)
                elif "-" in price_range:
                    try:
                        min_p, max_p = map(float, price_range.split("-"))
                        if min_p <= float(cost_val) <= max_p:
                            filtered.append(poi)
                    except:
                        filtered.append(poi)
                else:
                    filtered.append(poi)
            enriched = filtered

        if not enriched:
            return f"❌ 未在{city}找到符合条件的景点"

        # 4. 格式化输出
        result = f"🏛️ **{city}景点推荐**\n"
        if keyword: result += f"🔍 搜索: {keyword}\n"
        if price_range: result += f"💰 价格: {price_range}\n"
        result += "─" * 50 + "\n\n"

        for idx, poi in enumerate(enriched[:10], 1):
            name = poi.get("name", "未知")
            address = poi.get("address", "")
            rating = poi.get("rating", "")
            cost = poi.get("cost", [])
            tel = poi.get("tel", "")
            location = poi.get("location", "")
            try:
                p_lon, p_lat = map(float, location.split(",")) if location else (0,0)
            except:
                p_lon, p_lat = 0, 0

            result += f"{idx}. 🏛️ **{name}**\n"
            result += f"   📍 {address}\n"
            if rating:
                result += f"   {format_rating(rating)}\n"

            # 票价
            cost_display = "免费"
            if cost and isinstance(cost, list) and cost[0]:
                cost_display = f"¥{cost[0]}"
            elif cost and isinstance(cost, str):
                cost_display = cost
            if "学生" in str(cost):
                result += f"   💰 {cost}\n"
            else:
                result += f"   💰 票价: {cost_display}"
                if cost_display != "免费":
                    result += " (学生票可能有优惠)"
                result += "\n"

            if tel: result += f"   📞 {tel}\n"
            if user_lon and user_lat and p_lon and p_lat:
                distance = calculate_distance(user_lon, user_lat, p_lon, p_lat)
                result += f"   📏 距离: {distance}km\n"

            # 图片兜底（MCP不提供图片，使用百度）
            if idx <= 10:
                img = get_baidu_image(name)
                if img:
                    result += f"\n   📷 实拍图：\n   ![]({img})\n"
                else:
                    # 没有图片时提供高德详情链接
                    poi_id = poi.get("id", "")
                    if poi_id:
                        url_pc = f"https://ditu.amap.com/detail/{poi_id}"
                        url_mobile = f"https://uri.amap.com/detail?id={poi_id}"
                        result += f"\n   📷 [💻 电脑查看实景]({url_pc}) | [📱 手机查看实景]({url_mobile})\n"

            # 简介
            biz_area = poi.get("business_area", "")
            if biz_area:
                result += f"   📝 {biz_area}\n"
            result += "\n"

        # 城市扫街榜链接
        city_pinyin = ''.join(lazy_pinyin(city))
        amap_link = f"https://ditu.amap.com/ranking/{city_pinyin}"
        result += "─" * 50 + "\n"
        result += f"🗺️ [在{city}高德地图中探索更多]({amap_link})\n"
        result += "💡 想了解某个景点的详细信息，可以告诉我景点名称\n"
        result += "💡 如果需要规划游览路线，可以告诉我你的位置"
        return result

    except Exception as e:
        return f"❌ 搜索景点失败: {str(e)}"

# ============== 酒店搜索 ==============
@tool
async def search_hotels(
    city: str, district: Optional[str] = None, min_rating: Optional[float] = None,
    max_price: Optional[int] = None, user_lon=None, user_lat=None
) -> str:
    """搜索城市酒店，支持按地区、评分、价格筛选。"""
    if not _amap_tools_loaded:
        await init_amap()

    keywords = "酒店|宾馆|民宿|青旅"
    if district:
        keywords = f"{district}|{keywords}"

    try:
        search_tool = get_amap_tool_by_name("maps_text_search")
        result = await search_tool.ainvoke({
            "keywords": keywords,
            "city": city,
            "citylimit": "true"
        })
        data = json.loads(result[0]["text"])
        pois = data.get("pois", [])

        if not pois:
            return f"❌ 未在{city}找到酒店"

        # 获取详情
        detail_tool = get_amap_tool_by_name("maps_search_detail")
        enriched = []
        for poi in pois[:10]:
            try:
                detail_res = await detail_tool.ainvoke({"id": poi["id"]})
                detail = json.loads(detail_res[0]["text"])
                poi["rating"] = detail.get("rating", "")
                poi["cost"] = detail.get("cost", [])
                poi["location"] = detail.get("location", "")
            except:
                pass
            enriched.append(poi)

        # 筛选
        filtered = []
        for poi in enriched:
            rating = poi.get("rating", "0")
            cost = poi.get("cost", [0])
            cost_val = cost[0] if cost else 0
            try:
                cost_float = float(cost_val) if cost_val else 0
            except:
                cost_float = 9999

            if min_rating:
                try:
                    if float(rating) < min_rating:
                        continue
                except:
                    pass
            if max_price:
                if cost_float > max_price:
                    continue
            filtered.append(poi)

        if not filtered:
            return f"❌ 未找到符合条件的酒店\n💡 建议: 放宽筛选条件试试"

        # 格式化
        result = f"🏨 **{city}酒店推荐**\n"
        filters = []
        if district: filters.append(f"区域: {district}")
        if min_rating: filters.append(f"评分≥{min_rating}")
        if max_price: filters.append(f"价格≤¥{max_price}")
        if filters: result += f"🔍 " + " | ".join(filters) + "\n"
        result += "─" * 50 + "\n\n"

        for idx, poi in enumerate(filtered[:10], 1):
            name = poi.get("name", "未知")
            address = poi.get("address", "")
            rating = poi.get("rating", "")
            cost = poi.get("cost", [])
            tel = poi.get("tel", "")
            location = poi.get("location", "")
            try: p_lon, p_lat = map(float, location.split(","))
            except: p_lon, p_lat = 0,0

            result += f"{idx}. 🏨 **{name}**\n"
            result += f"   📍 {address}\n"
            if rating: result += f"   {format_rating(rating)}\n"
            if cost and cost[0]: result += f"   💰 参考价: ¥{cost[0]}/晚\n"
            if tel: result += f"   📞 {tel}\n"
            if user_lon and user_lat and p_lon and p_lat:
                result += f"   📏 距离: {calculate_distance(user_lon, user_lat, p_lon, p_lat)}km\n"

            # 图片
            if idx <= 10:
                img = get_baidu_image(name)
                if img:
                    result += f"\n   📷 实拍图：\n   ![]({img})\n"
                else:
                    poi_id = poi.get("id", "")
                    if poi_id:
                        url_pc = f"https://ditu.amap.com/detail/{poi_id}"
                        url_mobile = f"https://uri.amap.com/detail?id={poi_id}"
                        result += f"\n   📷 [💻 电脑查看实景]({url_pc}) | [📱 手机查看实景]({url_mobile})\n"
            result += "\n"

        city_pinyin = ''.join(lazy_pinyin(city))
        amap_link = f"https://ditu.amap.com/ranking/{city_pinyin}"
        result += "─" * 50 + "\n"
        result += f"🗺️ [在{city}高德地图中探索更多酒店]({amap_link})\n"
        result += "💡 想看某家酒店的详细信息，可以告诉我酒店名称\n"
        return result

    except Exception as e:
        return f"❌ 搜索酒店失败: {str(e)}"


# ============== 美食搜索 ==============

@tool
async def search_restaurants(
    city: str, cuisine: Optional[str] = None, taste_preference: Optional[str] = None,
    max_price: Optional[int] = None, user_lon=None, user_lat=None
) -> str:
    """搜索城市美食/餐厅，支持口味、价格筛选和距离排序。"""
    if not _amap_tools_loaded:
        await init_amap()

    if cuisine:
        keywords = f"{cuisine}|美食"
    else:
        city_foods = {
            "北京": "烤鸭|涮羊肉|炸酱面", "成都": "火锅|串串|川菜", "重庆": "火锅|小面|江湖菜",
            "广州": "早茶|粤菜|烧腊", "杭州": "杭帮菜|西湖醋鱼|龙井虾仁",
            "西安": "肉夹馍|凉皮|泡馍", "长沙": "臭豆腐|湘菜|口味虾"
        }
        keywords = city_foods.get(city, "美食|餐厅|小吃")

    try:
        search_tool = get_amap_tool_by_name("maps_text_search")
        result = await search_tool.ainvoke({
            "keywords": keywords,
            "city": city,
            "citylimit": "true"
        })
        data = json.loads(result[0]["text"])
        pois = data.get("pois", [])

        if not pois:
            return f"❌ 未在{city}找到相关餐厅"

        detail_tool = get_amap_tool_by_name("maps_search_detail")
        enriched = []
        for poi in pois[:10]:
            try:
                detail_res = await detail_tool.ainvoke({"id": poi["id"]})
                detail = json.loads(detail_res[0]["text"])
                poi["rating"] = detail.get("rating", "")
                poi["cost"] = detail.get("cost", [])
                poi["location"] = detail.get("location", "")
            except:
                pass
            enriched.append(poi)

        if max_price:
            enriched = [p for p in enriched if float(p.get("cost", [0])[0] or 0) <= max_price]

        if not enriched:
            return "❌ 未找到符合条件的餐厅"

        # 距离排序
        if user_lon and user_lat:
            for poi in enriched:
                try:
                    p_lon, p_lat = map(float, poi.get("location", "0,0").split(","))
                    poi["_distance"] = calculate_distance(user_lon, user_lat, p_lon, p_lat)
                except:
                    poi["_distance"] = 999
            enriched.sort(key=lambda x: x.get("_distance", 999))

        result = f"🍽️ **{city}美食推荐**\n"
        if cuisine: result += f"🔍 类型: {cuisine}\n"
        if taste_preference: result += f"😋 口味: {taste_preference}\n"
        if max_price: result += f"💰 人均≤¥{max_price}\n"
        result += "─" * 50 + "\n\n"

        for idx, poi in enumerate(enriched[:10], 1):
            name = poi.get("name", "未知")
            address = poi.get("address", "")
            rating = poi.get("rating", "")
            cost = poi.get("cost", [])
            tel = poi.get("tel", "")
            poi_type = poi.get("type", "")

            tags = []
            if "火锅" in poi_type or "火锅" in name: tags.append("🍲")
            if "面" in poi_type or "面" in name: tags.append("🍜")
            if "烤" in poi_type or "烤" in name: tags.append("🍖")
            if "海鲜" in poi_type: tags.append("🦞")
            tag_str = "".join(tags) + " " if tags else ""

            result += f"{idx}. {tag_str}**{name}**\n"
            result += f"   📍 {address}\n"
            if rating: result += f"   {format_rating(rating)}\n"
            if cost and cost[0]:
                cost_val = float(cost[0])
                level = "💵" if cost_val < 50 else "💵💵" if cost_val < 100 else "💵💵💵"
                result += f"   💰 人均: ¥{cost[0]} {level}\n"
            if "_distance" in poi and poi["_distance"] < 999:
                result += f"   📏 距离: {poi['_distance']}km\n"

            if idx <= 10:
                img = get_baidu_image(name)
                if img:
                    result += f"\n   📷 ![]({img})\n"
                else:
                    poi_id = poi.get("id", "")
                    if poi_id:
                        url_pc = f"https://ditu.amap.com/detail/{poi_id}"
                        url_mobile = f"https://uri.amap.com/detail?id={poi_id}"
                        result += f"\n   📷 [💻 电脑查看实景]({url_pc}) | [📱 手机查看实景]({url_mobile})\n"

            if tel: result += f"   📞 {tel}\n"
            result += "\n"

        city_pinyin = ''.join(lazy_pinyin(city))
        amap_link = f"https://ditu.amap.com/ranking/{city_pinyin}"
        result += "─" * 50 + "\n"
        result += f"🗺️ [在{city}高德地图中探索更多美食]({amap_link})\n"
        result += "💡 想知道口味如何？可以问'这家辣不辣？'或'有什么推荐菜？'\n"
        if not taste_preference: result += "💡 告诉我你的口味偏好，我帮你精准推荐\n"
        return result

    except Exception as e:
        return f"❌ 搜索美食失败: {str(e)}"

@tool
async def geocode(address: str, city: Optional[str] = None) -> str:
    """地址转经纬度坐标"""
    if not _amap_tools_loaded:
        await init_amap()
    try:
        tool = get_amap_tool_by_name("maps_geo")
        params = {"address": address}
        if city:
            params["city"] = city
        result = await tool.ainvoke(params)
        data = json.loads(result[0]["text"])
        if data.get("status") == "1" and data.get("geocodes"):
            loc = data["geocodes"][0]["location"]
            return f"📍 {address} 的经纬度：{loc}"
        return f"❌ 未找到 {address} 的坐标"
    except Exception as e:
        return f"❌ 地理编码失败: {str(e)}"
    
@tool
async def plan_route(
    origin: str,
    destination: str,
    waypoints: Optional[str] = None,
    route_type: str = "driving",
    origin_city: Optional[str] = None,
    destination_city: Optional[str] = None
) -> str:
    """
    路线规划，支持步行、驾车、公交、骑行。
    参数:
    - origin: 起点地址
    - destination: 终点地址
    - route_type: walking/driving/transit/bicycling
    - origin_city: 起点城市（可选但推荐）
    - destination_city: 终点城市（可选但推荐）
    """
    if not _amap_tools_loaded:
        await init_amap()

    tool_map = {
        "walking": "maps_direction_walking_by_address",
        "driving": "maps_direction_driving_by_address",
        "transit": "maps_direction_transit_integrated_by_address",
        "bicycling": "maps_bicycling_by_address"
    }
    tool_name = tool_map.get(route_type, "maps_direction_driving_by_address")
    route_tool = get_amap_tool_by_name(tool_name)

    params = {
        "origin_address": origin,
        "destination_address": destination
    }
    if origin_city:
        params["origin_city"] = origin_city
    if destination_city:
        params["destination_city"] = destination_city

        # 尝试获取详细路线
    try:
        result = await route_tool.ainvoke(params)
        data = json.loads(result[0]["text"])

        # 处理不同返回结构
        inner = data.get("data") or data.get("route") or data
        paths = inner.get("paths", [])

        if not paths:
            raise ValueError("无路径数据")

        path = paths[0]
        distance_m = int(path.get("distance", 0))
        duration_s = int(path.get("duration", 0))

        # 格式化距离和时间
        distance_str = f"{distance_m/1000:.1f}公里" if distance_m >= 1000 else f"{distance_m}米"
        if duration_s >= 3600:
            duration_str = f"{duration_s//3600}小时{(duration_s%3600)//60}分钟"
        elif duration_s >= 60:
            duration_str = f"{duration_s//60}分钟"
        else:
            duration_str = f"{duration_s}秒"

        steps = path.get("steps", [])

        # 格式化输出
        res = f"🗺️ **{origin} → {destination}** ({route_type})\n"
        res += f"📏 全程 {distance_str}，预计 {duration_str}\n"

        if steps:
            res += "\n📋 **详细步骤**：\n"
            for i, step in enumerate(steps[:8], 1):
                instruction = step.get("instruction", "?")
                road = step.get("road", "")
                step_dist = int(step.get("distance", 0))
                dist = f"{step_dist/1000:.1f}km" if step_dist >= 1000 else f"{step_dist}m"
                road_str = f"（{road}，{dist}）" if road else f"（{dist}）"
                res += f"{i}. {instruction}{road_str}\n"

        # 附加一键跳转链接
        url = f"https://uri.amap.com/navigation?from={quote(origin)}&to={quote(destination)}"
        res += f"\n📱 [手机一键导航]({url})"
        return res

    except Exception:
        # 降级为简单链接
        route_names = {"walking": "步行", "bicycling": "骑行", "driving": "驾车", "transit": "公交"}
        route_name = route_names.get(route_type, route_type)
        url = f"https://uri.amap.com/navigation?from={quote(origin)}&to={quote(destination)}"
        return (
            f"🗺️ **{origin} → {destination}** ({route_name})\n"
            f"🚩 点击下方链接查看详细路线并开始导航\n\n"
            f"💻📱 [查看{route_name}路线]({url})\n"
        )
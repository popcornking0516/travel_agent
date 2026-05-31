# agents/user_profile.py
import os, json
from langchain.tools import tool

PROFILE_DIR = "user_profiles"
os.makedirs(PROFILE_DIR, exist_ok=True)

def _get_profile_path(username: str) -> str:
    return os.path.join(PROFILE_DIR, f"{username}.json")

def load_profile(username: str) -> dict:
    try:
        with open(_get_profile_path(username), "r") as f:
            return json.load(f)
    except:
        return {}

def save_profile(username: str, profile: dict):
    with open(_get_profile_path(username), "w") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

@tool
def update_user_profile(key: str, value: str, username: str = "default") -> str:
    """更新用户偏好，key可以是 taste, budget, travel_style, hotel_preference, transport, group 等"""
    profile = load_profile(username)
    profile[key] = value
    save_profile(username, profile)
    return f"已更新你的偏好：{key} = {value}"
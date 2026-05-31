"""
旅行规划助手 - Streamlit 前端（纯聊天版）
"""
import streamlit as st
from agent import chat_with_agent, reset_memory
import re
import asyncio
from agents.memory import add_message

# ========== 用户登录（个性版） ==========
if "username" not in st.session_state:
    st.session_state.username = ""

if not st.session_state.username:
    # === 有趣的登录卡片（全部用 Streamlit 原生组件） ===
    
    # 注入卡片背景样式（只作用于这一块）
    st.markdown("""
    <style>
        /* 用 Streamlit 的 container 模拟卡片 */
        div[data-testid="stVerticalBlock"] > div:has(.login-card) {
            background: linear-gradient(145deg, #FFFDF5 0%, #F0F7E8 100%);
            border-radius: 28px;
            padding: 35px 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            max-width: 450px;
            margin: 60px auto;
            text-align: center;
        }
        /* 跳动 emoji */
        .login-emoji {
            font-size: 3.5rem;
            animation: bounce 1.2s infinite;
            display: inline-block;
        }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-8px); }
        }
        /* 输入框样式 */
        div[data-testid="stTextInput"] input {
            border: 2px solid #C5DCA0 !important;
            border-radius: 20px !important;
            padding: 10px 18px !important;
            text-align: center !important;
            font-size: 1rem !important;
            background: white !important;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #7BAF5A !important;
            box-shadow: 0 0 0 3px rgba(123, 175, 90, 0.2) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # 使用 st.container 并添加标记 class
    with st.container():
        st.markdown('<div class="login-card"></div>', unsafe_allow_html=True)  # 标记 class
        st.markdown('<div class="login-emoji">🌽</div>', unsafe_allow_html=True)
        st.markdown("### 欢迎来到玉米旅行搭子！")
        st.markdown("我是探险家玉米，你的专属旅行好搭子～  \n来吧告诉我你是谁，我已经迫不及待同你出发啦！")
        
        username = st.text_input(
            "", 
            placeholder="在这里输入你的名字（已有便可直接输入），比如：mm",
            key="name_input",
            label_visibility="collapsed"
        )

        if username:
            st.session_state.username = username
            st.balloons()
            st.rerun()

    st.stop()

username = st.session_state.username

def render_content(text: str) -> str:
    """把 [文字](链接) 转成可点击的 HTML 链接"""
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" target="_blank" style="color: #667eea;">🔗 \1</a>',
        text
    )
    return text

# ========== 页面配置 ==========
st.set_page_config(
    page_title="玉米旅行搭子",
    page_icon="🌽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== 自定义样式 ==========
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-title {
        text-align: center;
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .message-row {
        display: flex;
        align-items: flex-start;
        margin: 16px 0;
        gap: 10px;
    }
    .message-row.assistant { justify-content: flex-start; }
    .message-row.user { justify-content: flex-end; }
    .avatar {
        width: 40px; height: 40px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 24px; flex-shrink: 0;
    }
    .avatar.assistant { background: #FFF8E1; order: 1; }
    .avatar.user { background: #E0F7FA; order: 2; }
    .bubble {
        max-width: 60%; padding: 12px 18px;
        word-wrap: break-word; line-height: 1.6; font-size: 15px;
    }
    .bubble.assistant {
        background: linear-gradient(135deg, #fff8e1, #ffecb3);
        border-radius: 5px 20px 20px 20px; order: 2;
    }
    .bubble.user {
        background: linear-gradient(135deg, #50C9C3 0%, #96DEDA 100%);
        color: white; border-radius: 20px 5px 20px 20px; order: 1;
    }
    .stChatInput {
        border-radius: 25px !important;
        border: 2px solid #81D8D0 !important;
        background: #f8f9fa !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    }
    .stChatInput:focus {
        border-color: #A0E7E5 !important;
        box-shadow: 0 0 0 3px rgba(129, 216, 208, 0.3) !important;
    }
</style>
""", unsafe_allow_html=True)

# ========== 渲染单条消息 ==========
def render_message(role: str, content: str):
    if role == "assistant":
        avatar, row_class = "🌽", "assistant"
    else:
        avatar, row_class = "👀", "user"
    
    # 保护已转换的链接，避免二次包裹
    protected = []
    def protect(m):
        protected.append(m.group(0))
        return f"__PROTECTED_{len(protected)-1}__"
    
    content = render_content(content)
    content = re.sub(r'<a[^>]*>.*?</a>', protect, content)
    content = re.sub(r'(https?://[^\s<>"]+)', r'<a href="\1" target="_blank" style="color: #667eea;">🔗 \1</a>', content)
    for i, p in enumerate(protected):
        content = content.replace(f"__PROTECTED_{i}__", p)
    
    content_html = content.replace("\n", "<br>")
    
    st.markdown(f"""
    <div class="message-row {row_class}">
        <div class="avatar {row_class}">{avatar}</div>
        <div class="bubble {row_class}">{content_html}</div>
    </div>
    """, unsafe_allow_html=True)

# ========== 侧边栏（只保留快捷入口和清空） ==========
with st.sidebar:
    st.markdown("## 🧩 功能导航")
    st.markdown("---")
    st.markdown("### 🚀 快捷入口")
    if st.button("🚄 查高铁", use_container_width=True):
        st.session_state.quick_query = "查高铁"
    if st.button("🌤️ 查天气", use_container_width=True):
        st.session_state.quick_query = "查天气"
    if st.button("🏨 找酒店", use_container_width=True):
        st.session_state.quick_query = "推荐酒店"
    if st.button("😋 找美食", use_container_width=True):
        st.session_state.quick_query = "推荐美食"
    if st.button("🗺️ 城市概览", use_container_width=True):
        st.session_state.quick_query = "城市概览"
    
    st.markdown("---")
    st.markdown("### 💡 试试这些")
    examples = [
        "帮我查明天上海到北京的高铁",
        "成都3天2晚旅行规划，预算2000元",
        "推荐淄博的美味烧烤店",
        "北京有什么必去的景点？",
    ]
    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state.quick_query = example
    
    st.markdown("---")
    if st.button("🔄 清空对话", use_container_width=True):
        reset_memory()
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.markdown("Made with ❤️💛💚🩵🤍 by 玉米🌽")

# ========== 主界面 ==========
st.markdown('<p class="main-title">玉米旅行规划助手</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">我是探险家-玉米🌽，你的专属旅行规划师～</p>', unsafe_allow_html=True)

# ========== 初始化 ==========
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "👋 哈喽呀！我是你的老朋友玉米🌽，你的旅行好搭子！\n\n我可以帮你：\n- 🚄 查询高铁票\n- 🌤️ 查看目的地天气\n- 🏨 推荐酒店住宿\n- 😋 寻找当地美食\n- 🗺️ 规划完整行程\n\n come on😎告诉我你想要什么吧！"}
    ]

# ========== 聊天区域 ==========
for msg in st.session_state.messages:
    render_message(msg["role"], msg["content"])

if "quick_query" in st.session_state and st.session_state.quick_query:
    query = st.session_state.quick_query
    st.session_state.quick_query = None
    st.session_state.messages.append({"role": "user", "content": query})
    render_message("user", query)
    with st.spinner("玉米🌽正在快马加鞭查询中..."):
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
        result = asyncio.run(chat_with_agent(query, username, history))

        # 在 chat_with_agent 调用后
        if st.session_state.get("debug_memory"):
            st.write("检索到的历史：", result.get("relevant_history", "无"))

        reply = result["reply"]

        # === 存入向量记忆 ===
        add_message(st.session_state.username, "user", query)
        add_message(st.session_state.username, "assistant", reply)

    response_text = result["reply"]
    render_message("assistant", response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})

# ========== 输入区域 ==========
if prompt := st.chat_input("输入你的旅行需求..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    render_message("user", prompt)
    with st.spinner("玉米🌽正在快马加鞭查询中..."):
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
        result = asyncio.run(chat_with_agent(prompt, username, history))

        # 在 chat_with_agent 调用后
        if st.session_state.get("debug_memory"):
            st.write("检索到的历史：", result.get("relevant_history", "无"))

        reply = result["reply"]

        # === 存入向量记忆 ===
        add_message(st.session_state.username, "user", prompt)
        add_message(st.session_state.username, "assistant", reply)
    response_text = result["reply"]
    render_message("assistant", response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})

# 启动前端： streamlit run app.py --server.port 8501
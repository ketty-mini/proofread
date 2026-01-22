import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from io import BytesIO

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="智能内容编辑", page_icon="✍️", layout="wide")
st.title("编辑智能助手")

# --- 2. 获取 API Key ---
try:
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
    else:
        st.error("未检测到密钥！请在 Streamlit Cloud 后台 Secrets 中配置 DEEPSEEK_API_KEY。")
        st.stop()
except (FileNotFoundError, KeyError):
    st.warning("⚠️ 本地运行提示：未找到 .streamlit/secrets.toml 配置文件。")
    st.stop()

# --- 3. 初始化 DeepSeek 客户端 ---
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# --- 4. 辅助函数：生成 Word 文件 ---
def create_word_docx(text, mode_name):
    doc = Document()
    doc.add_heading(f'DeepSeek 修正结果 ({mode_name})', 0)
    doc.add_paragraph(text)
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### 🤖 模式设置")
    
    # === 新增：三种模式选择 ===
    mode = st.radio(
        "请选择处理力度：",
        ("🔍 仅标红 (只改错别字)", "🛠️ 仅纠错 (修补语病)", "✨ 深度润色 (提升文采)"),
        index=0,
        help="【仅标红】极度克制，只改明显的错字标点；\n【仅纠错】修正语法和句子不通顺；\n【深度润色】优化用词和语气，提升可读性。"
    )
    
    st.markdown("---")
    st.info("本工具深度帮助编辑完成文章修正。")

# --- 6. 核心 Prompt 策略 (根据模式切换) ---
if "仅标红" in mode:
    # 极度保守模式
    system_prompt = "你是一个严谨的文字校对员。你的任务仅仅是找出并修正文本中的【错别字】和【标点符号错误】。⚠️ 绝对禁止修改句子结构、用词习惯或语气。如果一句话没有错别字，请原样输出。请直接输出结果，不要包含任何解释。"
elif "仅纠错" in mode:
    #

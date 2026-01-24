import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn
from io import BytesIO
from PIL import Image
import pytesseract # 需安装 pip install pytesseract
import os
import shutil

# --- 0. Tesseract 路径强制修复 (针对云端) ---
# 这段代码必须保留，用于在云端环境中辅助定位 Tesseract
if os.path.exists('/usr/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
else:
    possible_path = shutil.which("tesseract")
    if possible_path:
        pytesseract.pytesseract.tesseract_cmd = possible_path

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="Ketty's Mini Proofreading", 
    page_icon="✒️", 
    layout="centered"
)

# --- 2. CSS 样式 ---
def local_css():
    st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
        font-family: "PingFang SC", "Microsoft YaHei", -apple-system, sans-serif;
    }
    .nav-title {
        font-size: 22px;
        font-weight: 700;
        color: #1a1a1a;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.5px;
    }
    /* === 纯文字悬停菜单 === */
    div[role="radiogroup"] {
        display: flex;
        justify-content: flex-end;
        gap: 25px;
        background: transparent;
        padding: 0;
        border: none;
        width: fit-content;
        margin-left: auto;
    }
    div[role="radiogroup"] label > div:first-child { display: none; }
    div[role="radiogroup"] label p {
        font-size: 16px;
        color: #9ca3af;
        font-weight: 500;
        padding: 6px 12px;
        border-radius: 6px;
        margin: 0 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border-bottom: 2px solid transparent;
    }
    div[role="radiogroup"] label:hover p {
        color: #1a1a1a;
        background-color: #f3f4f6; 
        transform: translateY(-3px);
    }
    div[role="radiogroup"] label[data-checked="true"] p {
        color: #000000;
        font-weight: 700;
        border-bottom: 2px solid #000000;
    }
    .mode-desc {
        font-size: 14px;
        color: #666;
        margin-bottom: 10px;
        padding-left: 10px;
        border-left: 3px solid #1a1a1a;
        line-height: 1.5;
        animation: fadeIn 0.6s ease;
    }
    /* === 输入框 === */
    .stTextArea textarea {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px;
        font-size: 16px;
        background-color: #fcfcfc;
        transition: all 0.2s;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.01);
    }
    .stTextArea textarea:focus {
        background-color: #ffffff;
        border-color: #1a1a1a;
        box-shadow: 0 0 0 3px rgba(0,0,0,0.05);
    }
    /* === 按钮 === */
    div.stButton > button {
        background-color: #1a1a1a;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 12px 24px;
        font-weight: 600;
        letter-spacing: 0.5px;
        width: 100%;
        transition: transform 0.1s;
    }
    div.stButton > button:hover {
        background-color: #000000;
        transform: translateY(-1px);
    }
    /* === 上传/折叠栏样式 === */
    .streamlit-expanderHeader {
        font-size: 14px; color: #555; background-color: #f9f9f9; border-radius: 8px;
    }
    /* 隐藏上传组件多余的边框，使其更简洁 */
    div[data-testid="stFileUploader"] section {
        padding: 20px;
        background-color: #fcfcfc;
        border: 1px dashed #e5e7eb;
    }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- 3. 初始化 ---
try:
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
    else:
        st.stop()
except:
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

if 'ocr_text' not in st.session_state:
    st.session_state['ocr_text'] = ""

# --- 4. 顶部布局 ---
col_head_1, col_head_2 = st.columns([1.5, 2], vertical_alignment="center")

with col_head_1:
    st.markdown('<div class="nav-title">✒️ Ketty\'s Mini Proofreading</div>', unsafe_allow_html=True)

with col_head_2:
    selected_mode = st.radio(
        "Nav",
        ["仅标红", "纠错", "润色"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )

st.markdown("---") 

# --- 5. 动态内容配置 ---
mode_config = {
    "仅标红": {
        "desc": "🔴 Strict Mode：严格查错，仅标红原文中的错别字与语病，绝不改写。",
        "placeholder": "在此输入，或上方上传图片...",
        "btn_text": "开始扫描 / Strict Scan",
        "prompt": """
            你是一个严格的校对员。请检查文本中的【错别字】、【标点错误】和【明显语病】。
            【绝对指令】：
            1. 严禁重写句子，严禁润色，严禁改变原意。
            2. 【重要】输出文本必须与原文段落结构、换行符、字数行数高度一致。严禁合并段落。
            3. 如果没有错误，请原样输出。
            直接输出修正后的全文，不含解释。
        """
    },
    "纠错": {
        "desc": "🛠️ Fix Mode：智能修正错别字、标点及不通顺语句，保持原意。",
        "placeholder": "在此输入，或上方上传图片...",
        "btn_text": "开始纠错 / Auto Fix",
        "prompt": """
            你是一个资深的语文老师。修正错别字、语病和标点。
            【重要指令】：
            1. 保持原文语气，只确保规范。
            2. 【严禁合并段落】：必须严格保留原文的换行符和段落结构，原文有几段，输出就是几段。
            直接输出修正后的文本，不要加任何前言后语。
        """
    },
    "润色": {
        "desc": "✨ Polish Mode：深度优化用词与句式，提升文章的专业度与文采。",
        "placeholder": "在此输入，或上方上传图片...",
        "btn_text": "开始润色 / Polish Magic",
        "prompt": """
            你是一个资深的编辑。请对文本进行深度润色，优化用词和句式，使其更加流畅专业。
            【重要指令】：
            1. 提升文采，但不要过度改变原意。
            2. 【严禁合并段落】：输出必须严格保留原文的段落结构和换行，不要将文本合并成一大段。
            直接输出结果，不要加任何解释。
        """
    }
}

current_config = mode_config[selected_mode]
st.markdown(f'<div class="mode-desc">{current_config["desc"]}</div>', unsafe_allow_html=True)

# === 6. 🖼️ 图片上传与文字识别 (手动按钮版) ===
with st.expander("🖼️ 上传图片识别文字 / Upload Image OCR", expanded=True):
    uploaded_file = st.file_uploader("第一步：选择图片", type=['png', 'jpg', 'jpeg'])
    
    # 🌟 变化在这里：加了一个按钮，不点它就不干活，防止死循环
    if uploaded_file is not None:
        if st.button("🔍 开始识别图片中的文字 (Start OCR)", type="primary"):
            try:
                with st.spinner("正在努力识别中..."):
                    uploaded_file.seek(0)
                    img = Image.open(uploaded_file).convert('RGB')
                    
                    # 识别文字 (默认尝试中英文)
                    text_from_image = pytesseract.image_to_string(img, lang='chi_sim+eng')
                    
                    if text_from_image.strip():
                        # 把识别结果存进状态里
                        st.session_state['user_text'] = text_from_image.strip()
                        st.success("✅ 识别成功！文字已填入下方。")
                    else:
                        st.warning("⚠️ 似乎没识别到文字，请检查图片清晰度。")
                        
            except Exception as e:
                st.error(f"识别出错: {e}")

# === 7. 📝 文字输入区 (绑定版) ===
if 'user_text' not in st.session_state:
    st.session_state['user_text'] = ""

text_input = st.text_area(
    "请输入或粘贴需要处理的文字：", 
    height=300,
    key="user_text", # 绑定状态
    help="在这里输入文字，或者通过上方图片识别自动填充"
)

# --- 1. 顶部模式选择 (这才是你要的“点中变灰”效果) ---
# 这里的 key 是为了防止 Streamlit 刷新重置
selected_mode = st.segmented_control(
    "请选择模式 / Mode Selection",
    options=["仅标红", "纠错", "润色"],
    selection_mode="single",
    default="润色",  # 默认选中润色
    label_visibility="collapsed" # 隐藏标题，界面更清爽
)

# 防止 selected_mode 偶尔为空的情况
if not selected_mode:
    selected_mode = "润色"

# --- 2. 根据选择的模式，准备按钮名字和提示词 ---
if selected_mode == "仅标红":
    btn_label = "🔍 开始查错 / Start Check"
    instruction_text = "Strict Mode: 严格查错，仅标红原文中的错别字与语病，绝不改写。"
elif selected_mode == "纠错":
    btn_label = "🚑 开始纠错 / Fix Errors"
    instruction_text = "Fix Mode: 修改错别字和语病，保持原意。"
else:
    btn_label = "✨ 开始润色 / Polish Magic"
    instruction_text = "Polish Mode: 深度优化用词与句式，提升文章的专业度与文采。"

# 显示那行带竖线的提示文字
st.write(f"**| {instruction_text}**")

# --- 3. 唯一的执行按钮 (解决 NameError 的关键) ---
# 注意：我们不再使用 run_btn 变量，而是直接在 if 里写逻辑
if st.button(btn_label, type="primary", use_container_width=True):
    
    # 检查是否有内容（这里假设你的输入框变量名是 user_text）
    # 如果你的输入框变量名叫 text_input，请把下面的 user_text 改成 text_input
    if not st.session_state.get('user_text', '').strip():
        st.warning("⚠️ 请先输入文字内容！")
        st.stop() # 停止运行下面的代码
        
    st.info("AI 正在思考中... Please wait...")
    
    # --- 4. 核心处理逻辑 (直接在这里分流) ---
    try:
        if selected_mode == "仅标红":
            # 这里调用你的查错函数，确保 process_text 函数存在
            # 假设你的函数参数是 (text, mode)
            result = process_text(st.session_state['user_text'], "proofread") 
            st.markdown(result)
            
        elif selected_mode == "纠错":
            result = process_text(st.session_state['user_text'], "fix")
            st.markdown(result)
            
        else: # 润色
            result = process_text(st.session_state['user_text'], "polish")
            st.markdown(result)
            
    except Exception as e:
        st.error(f"发生错误: {e}")

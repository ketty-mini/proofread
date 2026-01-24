import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn
from io import BytesIO

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="Intelligent Proofreading", page_icon="📝", layout="wide")

# --- 2. CSS 魔法：复刻参考图的导航栏 ---
def local_css():
    st.markdown("""
    <style>
    /* 全局背景与字体 */
    .stApp {
        background-color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* === 顶部导航栏样式 === */
    
    /* 1. 标题样式 (左侧) */
    .nav-title {
        font-size: 20px;
        font-weight: 600;
        color: #1f2937;
        padding-top: 10px; /* 对齐右侧菜单 */
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* 2. 改造 Radio 按钮为 "文本菜单" (右侧) */
    div[role="radiogroup"] {
        display: flex;
        justify-content: flex-end; /* 靠右对齐 */
        border: none;
        background: transparent;
    }
    
    div[data-testid="stRadio"] > div {
        gap: 30px; /* 菜单项之间的间距 */
    }

    /* 隐藏原本的单选圆圈 */
    div[role="radiogroup"] label > div:first-child {
        display: none; 
    }

    /* 文字样式 */
    div[role="radiogroup"] label p {
        font-size: 16px;
        color: #4b5563; /* 默认灰色 */
        font-weight: 500;
        cursor: pointer;
        padding-bottom: 5px;
        border-bottom: 2px solid transparent; /* 预留边框位置 */
        transition: all 0.2s;
    }

    /* 选中状态：黑色文字 + 底部黑线 */
    div[role="radiogroup"] label[data-checked="true"] p {
        color: #000000;
        font-weight: 600;
        border-bottom: 2px solid #000000;
    }

    /* 悬停效果 */
    div[role="radiogroup"] label:hover p {
        color: #000000;
    }

    /* === 界面其他元素优化 === */

    /* 输入框：极简灰边 */
    .stTextArea textarea {
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        padding: 15px;
        font-size: 16px;
        background-color: #f9fafb;
    }
    .stTextArea textarea:focus {
        background-color: #ffffff;
        border-color: #000000;
        box-shadow: none;
    }

    /* 黑色按钮 */
    div.stButton > button {
        background-color: #111827;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 10px 20px;
        font-weight: 500;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #000000;
    }

    /* 结果展示区 */
    .result-box {
        margin-top: 30px;
        padding: 40px;
        border: 1px solid #f3f4f6;
        border-radius: 8px;
        background: #ffffff;
        font-family: "Songti SC", "SimSun", serif;
        font-size: 18px;
        line-height: 2.0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
    }
    
    /* 分割线微调 */
    hr {
        margin-top: 0px;
        margin-bottom: 30px;
        border-color: #f3f4f6;
    }
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

# --- 4. 顶部导航布局 (Left Title, Right Menu) ---
col_logo, col_nav = st.columns([1, 2])

with col_logo:
    # 模拟左上角的 Logo/标题
    st.markdown('<div class="nav-title">📄 Intelligent Proofreading</div>', unsafe_allow_html=True)

with col_nav:
    # 这里的 Radio 已经被 CSS 魔改为纯文字菜单
    selected_mode = st.radio(
        "Nav",
        ["Strict Check", "Auto Fix", "Polish"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )

st.markdown("---") # 极细分割线

# --- 5. 核心逻辑 (Bug 修复版) ---

# 映射模式
mode_map = {
    "Strict Check": "仅标红",
    "Auto Fix": "纠错",
    "Polish": "优化"
}
current_mode = mode_map[selected_mode]

# 输入区
text_input = st.text_area(
    "",
    height=300,
    placeholder="Paste your text here..."
)

# 按钮区
col_b1, col_b2, col_b3 = st.columns([1, 1, 1])
with col_b2:
    run_btn = st.button("Start Processing")

if run_btn:
    if not text_input:
        st.warning("Please input text.")
    else:
        # Prompt 逻辑：严格防止 AI 重写导致的“全红”
        if current_mode == "仅标红":
            system_prompt = """
            你是一个严格的校对员。请检查文本中的【错别字】、【标点错误】和【明显语病】。
            【绝对指令】：
            1. 严禁重写句子结构，严禁润色。
            2. 输出文本必须与原文段落结构、字数行数高度一致。
            3. 如果没有错误，请原样输出，不要改动一个字。
            直接输出修正后的全文，不含解释。
            """
        elif current_mode == "纠错":
            system_prompt = "你是一个语文老师。修正错别字、语病和标点。保持原文语气，只确保规范。直接输出修正后的文本。"
        else:
            system_prompt = "你是一个资深的编辑。请对文本进行深度润色，优化用词和句式。直接输出结果。"

        with st.spinner("Processing..."):
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text_input}
                    ],
                    stream=False
                )
                res_text = response.choices[0].message.content.strip()

                # --- 差异比对 (autojunk=False 防止大片红) ---
                def get_diff_html(orig, corr, mode):
                    output = []
                    # 关键修复：autojunk=False
                    s = difflib.SequenceMatcher(None, orig, corr, autojunk=False)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if mode == "仅标红":
                            if opcode == 'equal':
                                output.append(f'<span>{orig[a0:a1]}</span>')
                            elif opcode in ['delete', 'replace']:
                                output.append(f'<span style="color:#e11d48; font-weight:bold; background-color:#ffe4e6;">{orig[a0:a1]}</span>')
                            elif opcode == 'insert':
                                output.append(f'<span style="color:#e11d48; font-weight:bold;">^</span>')
                        else:
                            if opcode == 'equal':
                                output.append(orig[a0:a1])
                            elif opcode == 'insert':
                                output.append(f'<span style="color:#059669; text-decoration:underline; font-weight:bold;">{corr[b0:b1]}</span>')
                            elif opcode in ['delete', 'replace']:
                                output.append(f'<span style="color:#9ca3af; text-decoration:line-through;">{orig[a0:a1]}</span>')
                                if opcode == 'replace':
                                    output.append(f'<span style="color:#059669; text-decoration:underline; font-weight:bold;">{corr[b0:b1]}</span>')
                    return "".join(output)

                html_content = get_diff_html(text_input, res_text, current_mode)

                # 展示结果
                st.markdown(f'<div class="result-box">{html_content}</div>', unsafe_allow_html=True)
                
                # Word 导出
                def create_docx(orig, corr, mode):
                    doc = Document()
                    doc.add_heading('Review Report', 0)
                    style = doc.styles['Normal']
                    style.font.name = 'SimSun'
                    style.element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')
                    p = doc.add_paragraph()
                    s = difflib.SequenceMatcher(None, orig, corr, autojunk=False)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if mode == "仅标红":
                            if opcode == 'equal':
                                run = p.add_run(orig[a0:a1])
                                run.font.color.rgb = RGBColor(0,0,0)
                            elif opcode in ['delete', 'replace']:
                                run = p.add_run(orig[a0:a1])
                                run.font.color.rgb = RGBColor(255,0,0)
                            elif opcode == 'insert':
                                run = p.add_run("^")
                                run.font.color.rgb = RGBColor(255,0,0)
                                run.font.bold = True
                        else:
                            p.add_run(corr)
                    f = BytesIO()
                    doc.save(f)
                    f.seek(0)
                    return f

                st.markdown("<br>", unsafe_allow_html=True)
                file_docx = create_docx(text_input, res_text, current_mode)
                st.download_button(
                    label="Download Report (.docx)",
                    data=file_docx,
                    file_name="DeepSeek_Review.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            except Exception as e:
                st.error(f"Error: {e}")

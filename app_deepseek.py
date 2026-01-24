import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn
from io import BytesIO

# --- 1. 页面配置 (改为 Centered 解决太宽的问题) ---
st.set_page_config(
    page_title="Ketty's Mini Proofreading", 
    page_icon="✒️", 
    layout="centered"  # <--- 关键修改：让页面变窄，更聚气
)

# --- 2. CSS 样式定制 ---
def local_css():
    st.markdown("""
    <style>
    /* 全局背景与字体 */
    .stApp {
        background-color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    }

    /* === 顶部导航栏容器 === */
    /* 让标题和选项在同一行，且垂直居中 */
    div.row-widget.stRadio {
        background-color: transparent;
    }

    /* 标题样式 */
    .nav-title {
        font-size: 22px;
        font-weight: 700;
        color: #1a1a1a;
        display: flex;
        align-items: center;
        gap: 8px;
        white-space: nowrap; /* 防止标题换行 */
    }

    /* === 改造 Radio 按钮为 悬停特效中文菜单 === */
    div[role="radiogroup"] {
        display: flex;
        justify-content: center; /* 选项居中 */
        gap: 30px; /* 间距 */
        border: none;
        background: transparent;
    }

    /* 隐藏默认圆圈 */
    div[role="radiogroup"] label > div:first-child {
        display: none; 
    }

    /* 选项文字基础样式 */
    div[role="radiogroup"] label p {
        font-size: 16px;
        color: #6b7280; /* 默认灰色 */
        font-weight: 500;
        padding: 5px 10px;
        border-radius: 6px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); /* 丝滑动画 */
        border-bottom: 2px solid transparent;
    }

    /* 悬停 (Hover) 动态效果 */
    div[role="radiogroup"] label:hover p {
        color: #000000;
        background-color: #f3f4f6; /* 浅灰背景气泡 */
        transform: translateY(-2px); /* 微微上浮 */
    }

    /* 选中 (Selected) 状态 */
    div[role="radiogroup"] label[data-checked="true"] p {
        color: #000000;
        font-weight: 700;
        border-bottom: 2px solid #000000; /* 底部黑线 */
    }

    /* === 输入框优化 (更精致的边框) === */
    .stTextArea textarea {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px;
        font-size: 16px;
        background-color: #fbfcff; /* 极淡的蓝白底 */
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.02);
        transition: border-color 0.2s;
    }
    .stTextArea textarea:focus {
        background-color: #ffffff;
        border-color: #1a1a1a; /* 聚焦变黑 */
        box-shadow: 0 0 0 1px rgba(0,0,0,0.05);
    }

    /* 黑色主按钮 */
    div.stButton > button {
        background-color: #1a1a1a;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 12px 24px;
        font-weight: 600;
        width: 100%;
        transition: transform 0.1s;
    }
    div.stButton > button:hover {
        background-color: #000000;
        transform: scale(1.01);
    }

    /* 结果展示区 */
    .result-box {
        margin-top: 25px;
        padding: 30px;
        border: 1px dashed #d1d5db; /* 虚线边框，更有设计稿的感觉 */
        border-radius: 8px;
        background: #ffffff;
        font-family: "Songti SC", "SimSun", serif;
        font-size: 18px;
        line-height: 1.8;
    }
    
    /* 隐藏 Streamlit 默认的顶部汉堡菜单和 footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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

# --- 4. 顶部导航布局 ---
# 使用 columns 布局，左边 Logo，右边菜单
col_logo, col_nav = st.columns([1.5, 2], vertical_alignment="center")

with col_logo:
    st.markdown('<div class="nav-title">✒️ Ketty\'s Mini Proofreading</div>', unsafe_allow_html=True)

with col_nav:
    # 中文选项，居中排列
    selected_mode = st.radio(
        "Nav",
        ["仅标红", "纠错", "润色"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )

st.markdown("---") # 分割线

# --- 5. 核心逻辑 ---

# 输入区
text_input = st.text_area(
    "",
    height=300, # 高度适中
    placeholder="在此处粘贴文章..."
)

# 按钮
run_btn = st.button("开始处理 / Run")

if run_btn:
    if not text_input:
        st.warning("⚠️ 请先输入文字内容")
    else:
        # Prompt 逻辑 (保持最稳的防止全红版本)
        if selected_mode == "仅标红":
            system_prompt = """
            你是一个严格的校对员。请检查文本中的【错别字】、【标点错误】和【明显语病】。
            【绝对指令】：
            1. 严禁重写句子，严禁润色，严禁改变原意。
            2. 输出文本必须与原文段落结构、字数行数高度一致。
            3. 如果没有错误，请原样输出。
            直接输出修正后的全文，不含解释。
            """
        elif selected_mode == "纠错":
            system_prompt = "你是一个语文老师。修正错别字、语病和标点。保持原文语气，只确保规范。直接输出修正后的文本。"
        else: # 润色
            system_prompt = "你是一个资深的编辑。请对文本进行深度润色，优化用词和句式，使其更加流畅专业。直接输出结果。"

        with st.spinner("DeepSeek is thinking..."):
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

                # --- Diff 逻辑 ---
                def get_diff_html(orig, corr, mode):
                    output = []
                    s = difflib.SequenceMatcher(None, orig, corr, autojunk=False)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if mode == "仅标红":
                            if opcode == 'equal':
                                output.append(f'<span>{orig[a0:a1]}</span>')
                            elif opcode in ['delete', 'replace']:
                                output.append(f'<span style="color:#e11d48; font-weight:bold; background-color:#fff1f2; padding:0 2px;">{orig[a0:a1]}</span>')
                            elif opcode == 'insert':
                                output.append(f'<span style="color:#e11d48; font-weight:bold;">^</span>')
                        else:
                            if opcode == 'equal':
                                output.append(orig[a0:a1])
                            elif opcode == 'insert':
                                output.append(f'<span style="color:#059669; font-weight:bold;">{corr[b0:b1]}</span>')
                            elif opcode in ['delete', 'replace']:
                                output.append(f'<span style="color:#9ca3af; text-decoration:line-through;">{orig[a0:a1]}</span>')
                                if opcode == 'replace':
                                    output.append(f'<span style="color:#059669; font-weight:bold;">{corr[b0:b1]}</span>')
                    return "".join(output)

                html_content = get_diff_html(text_input, res_text, selected_mode)

                # 展示区
                st.markdown(f'<div class="result-box">{html_content}</div>', unsafe_allow_html=True)
                
                # Word 导出
                def create_docx(orig, corr, mode):
                    doc = Document()
                    doc.add_heading(f'Ketty\'s Review - {mode}', 0)
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
                file_docx = create_docx(text_input, res_text, selected_mode)
                st.download_button(
                    label="📥 导出 Word 报告",
                    data=file_docx,
                    file_name="Ketty_Proofread.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            except Exception as e:
                st.error(f"Error: {e}")

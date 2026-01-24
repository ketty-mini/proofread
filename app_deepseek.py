import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn
from io import BytesIO

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="Ketty's Mini Proofreading", 
    page_icon="✒️", 
    layout="centered"
)

# --- 2. CSS 样式：回归经典“下划线+悬停上浮” ---
def local_css():
    st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
        font-family: "PingFang SC", "Microsoft YaHei", -apple-system, sans-serif;
    }

    /* === 顶部导航栏布局 === */
    .nav-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 20px;
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

    /* === 还原您喜欢的：纯文字悬停特效菜单 === */
    div[role="radiogroup"] {
        display: flex;
        justify-content: flex-end;
        gap: 25px; /* 间距 */
        background: transparent; /* 透明背景 */
        padding: 0;
        border: none;
        width: fit-content;
        margin-left: auto;
    }

    /* 隐藏默认圆圈 */
    div[role="radiogroup"] label > div:first-child {
        display: none; 
    }

    /* 选项文字基础样式 */
    div[role="radiogroup"] label p {
        font-size: 16px;
        color: #9ca3af; /* 默认浅灰，更显高级 */
        font-weight: 500;
        padding: 6px 12px;
        border-radius: 6px;
        margin: 0 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); /* 经典的丝滑动画 */
        border-bottom: 2px solid transparent; /* 预留边框 */
    }

    /* 悬停 (Hover) 动态效果：上浮 + 浅灰气泡 */
    div[role="radiogroup"] label:hover p {
        color: #1a1a1a;
        background-color: #f3f4f6; 
        transform: translateY(-3px); /* 经典的上浮效果 */
    }

    /* 选中 (Selected) 状态：黑字 + 黑下划线 */
    div[role="radiogroup"] label[data-checked="true"] p {
        color: #000000;
        font-weight: 700;
        border-bottom: 2px solid #000000;
        background-color: transparent; /* 选中时不需要背景色，保持干净 */
    }

    /* === 动态说明文字 (保留这个功能，方便区分) === */
    .mode-desc {
        font-size: 14px;
        color: #666;
        margin-bottom: 15px;
        padding-left: 10px;
        border-left: 3px solid #1a1a1a;
        line-height: 1.5;
        animation: fadeIn 0.6s ease;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(5px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* === 输入框优化 === */
    .stTextArea textarea {
        border: 1px solid #e5e7eb;
        border-radius: 12px; /*稍微圆一点 */
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

    /* === 隐藏多余元素 === */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
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

# --- 4. 顶部布局 ---
col_head_1, col_head_2 = st.columns([1.5, 2], vertical_alignment="center")

with col_head_1:
    st.markdown('<div class="nav-title">✒️ Ketty\'s Mini</div>', unsafe_allow_html=True)

with col_head_2:
    # 选项放在右侧，保持您喜欢的样式
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
        "placeholder": "在此粘贴文章... (系统将进行 GB/T 15834 严格扫描)",
        "btn_text": "开始扫描 / Strict Scan",
        "prompt": """
            你是一个严格的校对员。请检查文本中的【错别字】、【标点错误】和【明显语病】。
            【绝对指令】：
            1. 严禁重写句子，严禁润色，严禁改变原意。
            2. 输出文本必须与原文段落结构、字数行数高度一致。
            3. 如果没有错误，请原样输出。
            直接输出修正后的全文，不含解释。
        """
    },
    "纠错": {
        "desc": "🛠️ Fix Mode：智能修正错别字、标点及不通顺语句，保持原意。",
        "placeholder": "在此粘贴文章... (系统将修正错误并优化语病)",
        "btn_text": "开始纠错 / Auto Fix",
        "prompt": "你是一个资深的语文老师。修正错别字、语病和标点。保持原文语气，只确保规范。直接输出修正后的文本。"
    },
    "润色": {
        "desc": "✨ Polish Mode：深度优化用词与句式，提升文章的专业度与文采。",
        "placeholder": "在此粘贴文章... (系统将进行深度润色)",
        "btn_text": "开始润色 / Polish Magic",
        "prompt": "你是一个资深的编辑。请对文本进行深度润色，优化用词和句式，使其更加流畅专业。直接输出结果。"
    }
}

current_config = mode_config[selected_mode]

# 显示动态说明
st.markdown(f'<div class="mode-desc">{current_config["desc"]}</div>', unsafe_allow_html=True)

# 输入区
text_input = st.text_area(
    "",
    height=300,
    placeholder=current_config["placeholder"]
)

# 按钮
run_btn = st.button(current_config["btn_text"])

# --- 6. 执行逻辑 ---
if run_btn:
    if not text_input:
        st.warning("⚠️ 请先输入文字内容")
    else:
        with st.spinner("Processing..."):
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": current_config["prompt"]},
                        {"role": "user", "content": text_input}
                    ],
                    stream=False
                )
                res_text = response.choices[0].message.content.strip()

                # --- 结果展示 ---
                st.markdown(
                    """
                    <style>
                    .result-box {
                        margin-top: 25px;
                        padding: 40px;
                        border: 2px dashed #e5e7eb;
                        border-radius: 4px; /* 纸张感 */
                        background: #ffffff;
                        font-family: "Songti SC", "SimSun", serif; 
                        font-size: 18px;
                        line-height: 2.0;
                    }
                    </style>
                    """, unsafe_allow_html=True
                )

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
                    label=f"📥 导出报告 / Download (.docx)",
                    data=file_docx,
                    file_name=f"Ketty_{selected_mode}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            except Exception as e:
                st.error(f"Error: {e}")

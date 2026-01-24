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

# --- 2. CSS 样式升级：胶囊按钮 + 动态反馈 ---
def local_css():
    st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
        font-family: "PingFang SC", "Microsoft YaHei", -apple-system, sans-serif;
    }

    /* === 顶部导航栏 === */
    .nav-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 20px;
    }
    
    .nav-title {
        font-size: 20px;
        font-weight: 800;
        color: #1a1a1a;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.5px;
    }

    /* === 胶囊式选项卡 (关键修改) === */
    div[role="radiogroup"] {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
        background: #f3f4f6; /* 浅灰底槽 */
        padding: 4px;
        border-radius: 8px; /* 圆角底座 */
        width: fit-content;
        margin-left: auto;
    }

    div[role="radiogroup"] label > div:first-child {
        display: none; /* 隐藏圆圈 */
    }

    div[role="radiogroup"] label p {
        font-size: 14px;
        color: #6b7280;
        font-weight: 500;
        padding: 6px 16px;
        border-radius: 6px;
        margin: 0 !important;
        transition: all 0.2s ease;
        text-align: center;
    }

    /* 选中状态：黑底白字，像一个实心胶囊 */
    div[role="radiogroup"] label[data-checked="true"] p {
        background-color: #000000;
        color: #ffffff;
        font-weight: 600;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }

    /* 悬停状态 */
    div[role="radiogroup"] label:hover p {
        color: #000000;
    }
    div[role="radiogroup"] label[data-checked="true"]:hover p {
        color: #ffffff; /* 选中时悬停保持白色 */
    }

    /* === 动态说明文字 === */
    .mode-desc {
        font-size: 14px;
        color: #666;
        margin-bottom: 10px;
        padding-left: 5px;
        border-left: 3px solid #000; /* 左侧黑条装饰 */
        line-height: 1.5;
        animation: fadeIn 0.5s;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(5px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* === 输入框 === */
    .stTextArea textarea {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px;
        font-size: 16px;
        background-color: #fcfcfc;
        transition: all 0.2s;
    }
    .stTextArea textarea:focus {
        background-color: #ffffff;
        border-color: #000;
        box-shadow: 0 0 0 2px rgba(0,0,0,0.05);
    }

    /* === 按钮 === */
    div.stButton > button {
        background-color: #1a1a1a;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 12px 24px;
        font-weight: 600;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #333;
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

# --- 4. 顶部布局 (左Title，右Menu) ---
col_head_1, col_head_2 = st.columns([1.2, 2], vertical_alignment="center")

with col_head_1:
    st.markdown('<div class="nav-title">✒️ Ketty\'s Mini</div>', unsafe_allow_html=True)

with col_head_2:
    # 选项放在右侧
    selected_mode = st.radio(
        "Nav",
        ["仅标红", "纠错", "润色"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )

st.markdown("---") 

# --- 5. 动态内容配置 (关键：让页面“动”起来) ---
# 定义每个模式的 文案、图标、Prompt
mode_config = {
    "仅标红": {
        "desc": "🔴 **严格查错模式**：仅标记错别字、标点和明显语病，**绝对不改写**原文。",
        "placeholder": "请粘贴文章... (此模式将严格比对，只会标红错误之处)",
        "btn_text": "开始扫描 (Strict Scan)",
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
        "desc": "🛠️ **智能纠错模式**：修正错别字和语病，保持原文语气，确保通顺规范。",
        "placeholder": "请粘贴文章... (此模式将修正错误并优化不通顺的句子)",
        "btn_text": "开始纠错 (Auto Fix)",
        "prompt": "你是一个语文老师。修正错别字、语病和标点。保持原文语气，只确保规范。直接输出修正后的文本。"
    },
    "润色": {
        "desc": "✨ **深度润色模式**：优化用词，调整句式，提升文采，使其更具专业感。",
        "placeholder": "请粘贴文章... (此模式将对文章进行深度美化和润色)",
        "btn_text": "开始润色 (Polish Magic)",
        "prompt": "你是一个资深的编辑。请对文本进行深度润色，优化用词和句式，使其更加流畅专业。直接输出结果。"
    }
}

# 获取当前模式的配置
current_config = mode_config[selected_mode]

# 显示动态说明 (在输入框上方)
st.markdown(f'<div class="mode-desc">{current_config["desc"]}</div>', unsafe_allow_html=True)

# 输入区 (Placeholder 随模式改变)
text_input = st.text_area(
    "",
    height=300,
    placeholder=current_config["placeholder"]
)

# 按钮 (文字随模式改变)
run_btn = st.button(current_config["btn_text"])

# --- 6. 执行逻辑 ---
if run_btn:
    if not text_input:
        st.warning("⚠️ 既然要处理，总得给点字吧？")
    else:
        with st.spinner(f"DeepSeek is {selected_mode}ing..."):
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

                # --- 结果展示 & Diff ---
                # 样式：虚线框
                st.markdown(
                    """
                    <style>
                    .result-box {
                        margin-top: 25px;
                        padding: 30px;
                        border: 2px dashed #e5e7eb;
                        border-radius: 12px;
                        background: #ffffff;
                        font-family: "Songti SC", serif; 
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
                                output.append(f'<span style="color:#dc2626; font-weight:bold; background-color:#fef2f2; border-bottom:1px solid #dc2626;">{orig[a0:a1]}</span>')
                            elif opcode == 'insert':
                                output.append(f'<span style="color:#dc2626; font-weight:bold;">^</span>')
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
                    doc.add_heading(f'Ketty\'s Report - {mode}', 0)
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
                    label=f"📥 导出 {selected_mode} 报告 (.docx)",
                    data=file_docx,
                    file_name=f"Ketty_{selected_mode}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            except Exception as e:
                st.error(f"Error: {e}")

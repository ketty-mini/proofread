import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn
from io import BytesIO

# --- 1. 页面配置 (宽屏模式) ---
st.set_page_config(page_title="Intelligent Proofreading", page_icon="📝", layout="wide")

# --- 2. 现代 SaaS 风格 CSS ---
def local_css():
    st.markdown("""
    <style>
    /* 全局字体与背景 */
    .stApp {
        background-color: #f8f9fa; /* 极淡的灰白底色，更有质感 */
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* 顶部导航栏容器 */
    .header-container {
        display: flex;
        align-items: center;
        padding-bottom: 20px;
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 30px;
    }

    /* 标题样式 */
    .main-title {
        font-size: 24px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0;
        padding: 0;
        letter-spacing: -0.5px;
    }

    /* 去除 Streamlit 默认的顶部边距 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1000px; /* 限制最大宽度，防止太宽 */
    }

    /* 选项卡 (Radio) 样式优化 */
    div[data-testid="stRadio"] > div {
        display: flex;
        gap: 15px;
        background: transparent;
    }
    /* 隐藏 Radio 的 label */
    div[data-testid="stRadio"] label p {
        font-size: 15px;
        font-weight: 500;
    }

    /* 输入框美化 */
    .stTextArea textarea {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        font-size: 16px;
        line-height: 1.6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        transition: all 0.2s;
    }
    .stTextArea textarea:focus {
        border-color: #3b82f6; /* 聚焦时的蓝色 */
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }

    /* 按钮美化 */
    div.stButton > button {
        background-color: #1a1a1a;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 10px 24px;
        font-weight: 600;
        transition: transform 0.1s;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #333333;
        transform: translateY(-1px);
    }

    /* 结果展示卡片 */
    .result-card {
        background-color: #ffffff;
        padding: 30px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        font-family: "Songti SC", "SimSun", serif; /* 宋体 */
        font-size: 18px;
        line-height: 2.0;
        color: #333;
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- 3. 初始化 API ---
try:
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
    else:
        st.error("❌ 未配置 API Key")
        st.stop()
except:
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# --- 4. 页面布局 (Header 导航) ---

# 使用 Columns 实现左侧标题，右侧选项
col_header_1, col_header_2 = st.columns([1, 2], vertical_alignment="bottom")

with col_header_1:
    st.markdown('<div class="main-title">Intelligent proofreading</div>', unsafe_allow_html=True)

with col_header_2:
    # 选项放在右侧/中间，横向排列
    mode_option = st.radio(
        "Mode Selection",
        options=["🔴 仅标红 (Strict)", "🛠️ 纠错 (Fix)", "✨ 优化 (Polish)"],
        horizontal=True,
        label_visibility="collapsed"
    )

st.markdown("---") # 分割线

# --- 5. 核心逻辑 ---

# 映射内部逻辑
if "仅标红" in mode_option:
    mode_key = "仅标红"
elif "纠错" in mode_option:
    mode_key = "纠错"
else:
    mode_key = "优化"

# 输入区
original_text = st.text_area(
    "Input Text",
    height=250,
    placeholder="在此输入或粘贴需要校对的文章...",
    label_visibility="collapsed"
)

# 处理按钮
if st.button("开始处理 / Start Process"):
    if not original_text:
        st.warning("请先输入文本内容")
    else:
        # Prompt 修复：针对“全红”Bug，必须强制 AI 保持原文结构
        if mode_key == "仅标红":
            system_prompt = """
            你是一个严格的校对员。请检查文本中的【错别字】、【标点错误】和【明显语病】。
            
            【重要原则】：
            1. **严禁重写**：绝对不要改写句子结构，不要润色，只修改错误点。
            2. **一一对应**：确保输出的文本与原文行数、段落结构完全一致。
            3. **最小改动**：如果没有错误，请原样输出。
            
            直接输出修正后的全文，不要包含任何解释。
            """
        elif mode_key == "纠错":
            system_prompt = "你是一个语文老师。请修正文本中的【错别字】、【语病】和【标点错误】。保持原文语气，只确保规范通顺。请直接输出修正后的文本。"
        else:
            system_prompt = "你是一个资深的编辑。请对文本进行【深度润色】。优化用词、调整句式、提升文采，使其更具吸引力。请直接输出润色后的文本。"

        with st.spinner("Analyzing..."):
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": original_text}
                    ],
                    stream=False
                )
                corrected_text = response.choices[0].message.content.strip()

                # --- 差异比对逻辑 ---
                def generate_diff_html(original, corrected, mode):
                    output = []
                    # 使用 autojunk=False 可以提高比对精度，防止大段标红
                    s = difflib.SequenceMatcher(None, original, corrected, autojunk=False)
                    
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if mode == "仅标红":
                            # 仅标红模式：只显示原文
                            if opcode == 'equal':
                                output.append(f'<span>{original[a0:a1]}</span>')
                            elif opcode == 'delete': 
                                # 多余的内容
                                output.append(f'<span style="color:#e03131; font-weight:bold;">{original[a0:a1]}</span>')
                            elif opcode == 'replace':
                                # 替换的内容（错字）
                                output.append(f'<span style="color:#e03131; font-weight:bold;">{original[a0:a1]}</span>')
                            elif opcode == 'insert':
                                # 缺失的内容，用红色 ^ 提示
                                output.append(f'<span style="color:#e03131; font-weight:bold; font-size:1.2em;" title="此处建议补充: {corrected[b0:b1]}">^</span>')
                        else:
                            # 其他模式：显示红绿对比
                            if opcode == 'equal':
                                output.append(original[a0:a1])
                            elif opcode == 'insert':
                                output.append(f'<span style="color:#099268; font-weight:bold; text-decoration:underline;">{corrected[b0:b1]}</span>')
                            elif opcode == 'delete':
                                output.append(f'<span style="color:#adb5bd; text-decoration:line-through;">{original[a0:a1]}</span>')
                            elif opcode == 'replace':
                                output.append(f'<span style="color:#adb5bd; text-decoration:line-through;">{original[a0:a1]}</span>')
                                output.append(f'<span style="color:#099268; font-weight:bold; text-decoration:underline;">{corrected[b0:b1]}</span>')
                    return "".join(output)

                diff_html = generate_diff_html(original_text, corrected_text, mode_key)
                
                # 结果展示
                st.markdown(f'<div class="result-card">{diff_html}</div>', unsafe_allow_html=True)
                
                # Word 导出函数
                def create_word(orig, corr, mode):
                    doc = Document()
                    doc.add_heading('Proofreading Report', 0)
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
                                run.font.strike = False
                            elif opcode == 'insert':
                                run = p.add_run("^")
                                run.font.color.rgb = RGBColor(255,0,0)
                                run.font.bold = True
                        else:
                             p.add_run(corr) # 其他模式直接输出结果
                    
                    bio = BytesIO()
                    doc.save(bio)
                    bio.seek(0)
                    return bio

                # 底部下载
                st.markdown("<br>", unsafe_allow_html=True)
                docx = create_word(original_text, corrected_text, mode_key)
                st.download_button(
                    label="📥 Download Word Report",
                    data=docx,
                    file_name="Proofreading_Report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            except Exception as e:
                st.error(f"Error: {e}")

import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn
from io import BytesIO

# --- 1. 页面配置 ---
st.set_page_config(page_title="智能校对", page_icon="✒️", layout="centered") 
# layout="centered" 让内容居中，更像一张专注的纸

# --- 2. 极简黑白 CSS 定制 ---
def local_css():
    st.markdown("""
    <style>
    /* 全局背景纯白 */
    .stApp {
        background-color: #ffffff;
        color: #000000;
        font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', sans-serif;
    }
    
    /* 标题样式 */
    h1 {
        font-weight: 300; /* 细体标题，更优雅 */
        letter-spacing: 2px;
        text-align: center;
        margin-bottom: 30px;
        font-size: 2.5rem;
    }
    
    /* 单选按钮优化 (上方选项) */
    div[data-testid="stRadio"] > div {
        display: flex;
        justify-content: center; /* 居中显示 */
        gap: 20px;
        background-color: #ffffff;
    }
    
    /* 输入框样式：极简黑边框 */
    .stTextArea textarea {
        background-color: #ffffff;
        border: 1px solid #000000; /* 纯黑细边框 */
        border-radius: 0px; /* 直角，更冷峻 */
        color: #000000;
        font-size: 16px;
        line-height: 1.6;
        box-shadow: none;
    }
    .stTextArea textarea:focus {
        border-color: #000000;
        box-shadow: none;
    }
    
    /* 按钮样式：纯黑块，白字 */
    div.stButton > button {
        background-color: #000000;
        color: #ffffff;
        border: 1px solid #000000;
        border-radius: 0px;
        padding: 10px 30px;
        font-size: 16px;
        font-weight: 400;
        width: 100%;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #ffffff;
        color: #000000; /* 悬停反色 */
        border: 1px solid #000000;
    }
    
    /* 结果展示区 */
    .result-box {
        border-top: 1px solid #eee;
        border-bottom: 1px solid #eee;
        padding: 30px 0;
        margin-top: 30px;
        font-family: "Songti SC", "SimSun", serif;
        font-size: 18px;
        line-height: 2.0;
    }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- 3. 初始化 ---
try:
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
    else:
        st.error("未配置 API Key")
        st.stop()
except:
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# --- 4. 核心逻辑函数 (保持严格标准) ---
def create_word_docx(original_text, corrected_text, mode_name):
    doc = Document()
    doc.add_heading(f'校对稿 - {mode_name}', 0)
    
    style = doc.styles['Normal']
    style.font.name = 'SimSun'
    style.element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')
    
    if mode_name == "仅标红":
        p = doc.add_paragraph()
        matcher = difflib.SequenceMatcher(None, original_text, corrected_text)
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(0, 0, 0)
            elif opcode == 'delete' or opcode == 'replace':
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(255, 0, 0)
                run.font.strike = False 
            elif opcode == 'insert':
                run_ins = p.add_run("^") 
                run_ins.font.color.rgb = RGBColor(255, 0, 0)
                run_ins.font.bold = True
                run_ins.font.size = Pt(12)
    else:
        doc.add_paragraph(corrected_text)
    
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 页面布局 ---

# 标题
st.title("DeepSeek Proofread")

# 选项栏 (上方，横向排列)
mode_mapping = {
    "仅标红": "仅标红",
    "纠错": "仅纠错",
    "优化": "深度润色"
}
selected_option = st.radio(
    "", # 不显示标签，保持简洁
    options=["仅标红", "纠错", "优化"],
    horizontal=True, # 横向排列
    label_visibility="collapsed" # 隐藏标题
)

# 映射回内部逻辑名称
mode_internal = mode_mapping[selected_option]

# 输入区域
original_text = st.text_area(
    "", 
    height=300, 
    placeholder="请输入需要处理的文本..."
)

# 执行按钮
if st.button("开始处理"):
    if not original_text:
        st.warning("内容不能为空")
    else:
        # Prompt 逻辑 (严格标准)
        if selected_option == "仅标红":
            system_prompt = """
            你是一个根据《图书质量管理规定》工作的魔鬼质检员。
            任务：对文本进行地毯式扫描，输出一份完美符合中国出版规范的文本。
            要求：必须修正所有标点错误、错别字、异形词及语病。
            输出：直接输出修正后的全文，不含任何解释。
            """
        elif selected_option == "纠错":
            system_prompt = "你是一个语文老师。请修正文本中的【错别字】、【语病】和【标点错误】。保持原文语气，只确保规范通顺。请直接输出修正后的文本。"
        else: # 优化
            system_prompt = "你是一个资深的编辑。请对文本进行【深度润色】。优化用词、调整句式、提升文采。请直接输出润色后的文本。"

        with st.spinner("Processing..."):
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": original_text}],
                    stream=False
                )
                corrected_text = response.choices[0].message.content.strip()

                # 结果展示
                def generate_diff_html(original, corrected, option):
                    output = []
                    s = difflib.SequenceMatcher(None, original, corrected)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if option == "仅标红":
                            if opcode == 'equal':
                                output.append(f'<span>{original[a0:a1]}</span>')
                            elif opcode in ['delete', 'replace']:
                                output.append(f'<span style="color:red;">{original[a0:a1]}</span>')
                            elif opcode == 'insert':
                                output.append(f'<span style="color:red; font-weight:bold;">^</span>')
                        else:
                            # 纠错和优化模式保留红绿对比
                            if opcode == 'equal':
                                output.append(original[a0:a1])
                            elif opcode == 'insert':
                                output.append(f'<span style="color:green; text-decoration:underline;">{corrected[b0:b1]}</span>')
                            elif opcode == 'delete':
                                output.append(f'<span style="color:#999; text-decoration:line-through;">{original[a0:a1]}</span>')
                            elif opcode == 'replace':
                                output.append(f'<span style="color:#999; text-decoration:line-through;">{original[a0:a1]}</span>')
                                output.append(f'<span style="color:green; text-decoration:underline;">{corrected[b0:b1]}</span>')
                    return "".join(output)

                diff_html = generate_diff_html(original_text, corrected_text, selected_option)
                
                # 极简结果框
                st.markdown(f'<div class="result-box">{diff_html}</div>', unsafe_allow_html=True)
                
                # 底部导出按钮
                st.markdown("<br>", unsafe_allow_html=True)
                word_file = create_word_docx(original_text, corrected_text, selected_option)
                st.download_button(
                    label="导出 Word 文档",
                    data=word_file,
                    file_name=f"DeepSeek_{selected_option}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            except Exception as e:
                st.error(f"Error: {e}")

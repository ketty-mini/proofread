import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor
from docx.oxml.ns import qn
from io import BytesIO
from PIL import Image
import pytesseract
import os
import shutil

# --- 1. Tesseract 路径智能修复 (防止报错) ---
# 自动查找系统中 tesseract 的位置，优先使用环境变量或常见路径
if 'TESSERACT_PATH' in os.environ:
    pytesseract.pytesseract.tesseract_cmd = os.environ['TESSERACT_PATH']
else:
    possible_paths = [
        '/usr/bin/tesseract', 
        '/usr/local/bin/tesseract', 
        r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    ]
    # 先尝试 shutil.which 自动查找
    system_path = shutil.which("tesseract")
    if system_path:
        pytesseract.pytesseract.tesseract_cmd = system_path
    else:
        # 找不到则遍历常见路径
        for p in possible_paths:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break

# --- 2. 页面配置 ---
st.set_page_config(
    page_title="Ketty's Mini Proofreading", 
    page_icon="✒️", 
    layout="centered"
)

# --- 3. 状态初始化 ---
# 初始化模式
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = "仅标红"

# 初始化输入框内容 (关键修复：统一管理输入框状态)
if "main_input" not in st.session_state:
    st.session_state.main_input = ""

# 初始化已处理图片记录 (防止重复OCR)
if "last_processed_file" not in st.session_state:
    st.session_state.last_processed_file = None

# --- 4. CSS 样式 (保持美观) ---
st.markdown("""
    <style>
    .stApp {background-color: #ffffff;}
    .nav-title {
        font-size: 24px; font-weight: 700; color: #1a1a1a; 
        margin-bottom: 20px; text-align: center;
    }
    .mode-desc {
        background-color: #f3f4f6; padding: 15px; 
        border-radius: 8px; border-left: 5px solid #1a1a1a;
        color: #374151; font-size: 14px; margin: 15px 0;
    }
    .stTextArea textarea {
        font-size: 16px; line-height: 1.6;
        border: 1px solid #e5e7eb; border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 5. API 设置 ---
try:
    # 尝试从 secrets 读取，读取不到则不报错，但在点击按钮时提示
    api_key = st.secrets.get("DEEPSEEK_API_KEY", "")
except:
    api_key = ""

if api_key:
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# --- 6. 顶部导航 (交互式按钮组) ---
st.markdown('<div class="nav-title">✒️ Ketty\'s Mini Proofreading</div>', unsafe_allow_html=True)

def set_mode(mode):
    st.session_state.selected_mode = mode

col1, col2, col3 = st.columns(3)

# 辅助函数：决定按钮样式
def get_type(mode_name):
    return "primary" if st.session_state.selected_mode == mode_name else "secondary"

with col1:
    st.button("仅标红", type=get_type("仅标红"), use_container_width=True, on_click=set_mode, args=("仅标红",))
with col2:
    st.button("纠错", type=get_type("纠错"), use_container_width=True, on_click=set_mode, args=("纠错",))
with col3:
    st.button("润色", type=get_type("润色"), use_container_width=True, on_click=set_mode, args=("润色",))

# --- 7. 模式配置与描述 ---
current_mode = st.session_state.selected_mode
mode_config = {
    "仅标红": {
        "desc": "🔴 **Strict Mode**：严格查错，仅标红错别字与语病，**绝不改写**，保留原汁原味。",
        "btn": "开始扫描 / Strict Scan",
        "prompt": "你是一个严格的校对员。请检查文本中的【错别字】、【标点错误】和【明显语病】。1. 严禁重写句子，严禁改变原意。2. 输出文本必须与原文段落结构高度一致。3. 如果没有错误，请原样输出。直接输出全文。"
    },
    "纠错": {
        "desc": "🛠️ **Fix Mode**：智能修正错别字、标点及不通顺语句，保持原意但更规范。",
        "btn": "开始纠错 / Auto Fix",
        "prompt": "你是一个语文老师。修正错别字、语病和标点。1. 保持原文语气，只确保规范。2. 严禁合并段落，保留换行符。直接输出修正后的文本。"
    },
    "润色": {
        "desc": "✨ **Polish Mode**：深度优化用词与句式，提升文章的专业度与文采。",
        "btn": "开始润色 / Polish Magic",
        "prompt": "你是一个资深的编辑。请对文本进行深度润色，优化用词和句式。1. 提升文采，但不要过度改变原意。2. 严禁合并段落。直接输出结果。"
    }
}
st.markdown(f'<div class="mode-desc">{mode_config[current_mode]["desc"]}</div>', unsafe_allow_html=True)

# --- 8. 图片上传与识别 (修复 BUG 核心区域) ---
with st.expander("🖼️ 上传图片识别文字 / Upload Image OCR"):
    uploaded_file = st.file_uploader("支持 JPG/PNG", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file is not None:
        # 检查是否是新上传的文件 (通过文件名判断)
        # 如果是新文件，或者虽然是旧文件但还没识别过，就执行
        if uploaded_file.name != st.session_state.last_processed_file:
            try:
                with st.spinner("👀 正在识别图片中的文字..."):
                    img = Image.open(uploaded_file)
                    # 识别中文和英文
                    text_res = pytesseract.image_to_string(img, lang='chi_sim+eng')
                    
                    if text_res.strip():
                        # 【核心修复】：直接强制覆盖 main_input 的状态
                        st.session_state.main_input = text_res.strip()
                        # 更新标记，防止刷新后重复识别
                        st.session_state.last_processed_file = uploaded_file.name
                        
                        st.success("✅ 识别成功！文字已自动填入下方。")
                        st.rerun() # 强制刷新页面，让输入框更新
                    else:
                        st.warning("⚠️ 图片似乎是空白的，或文字太模糊。")
            except Exception as e:
                st.error(f"OCR 识别失败: {e}")
                st.info("提示：请确保服务器已安装 Tesseract-OCR 并配置了中文语言包。")

# --- 9. 文本输入区 ---
# 使用 session_state 直接控制 value，不再需要手动写 value=...
text_input = st.text_area(
    "请输入或粘贴文字：",
    height=300,
    placeholder="在此输入文字...",
    key="main_input" 
)

# --- 10. 处理逻辑 ---
if st.button(mode_config[current_mode]["btn"], type="primary"):
    if not api_key:
        st.error("🚫 未检测到 API Key，请在 .streamlit/secrets.toml 中配置 DEEPSEEK_API_KEY")
    elif not text_input.strip():
        st.warning("⚠️ 请先输入文字内容")
    else:
        with st.spinner("AI 正在思考中..."):
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": mode_config[current_mode]["prompt"]},
                        {"role": "user", "content": text_input}
                    ],
                    stream=False
                )
                res_text = response.choices[0].message.content.strip()

                # --- 结果对比显示 (Diff View) ---
                st.subheader("📝 对比结果")
                
                def get_diff_html(orig, corr, mode):
                    output = []
                    s = difflib.SequenceMatcher(None, orig, corr, autojunk=False)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        text_orig = orig[a0:a1]
                        text_corr = corr[b0:b1]
                        
                        if mode == "仅标红":
                            if opcode == 'equal': output.append(f'<span>{text_orig}</span>')
                            elif opcode == 'delete': output.append(f'<span style="background:#fee2e2; color:#b91c1c; text-decoration:line-through;">{text_orig}</span>')
                            elif opcode == 'replace': output.append(f'<span style="background:#fee2e2; color:#b91c1c; font-weight:bold;">{text_orig}</span>')
                            elif opcode == 'insert': output.append(f'<span style="color:#b91c1c; font-weight:bold;">[缺]</span>')
                        else:
                            # 纠错/润色模式：显示修改后的样子
                            if opcode == 'equal': output.append(text_orig)
                            elif opcode == 'delete': output.append(f'<span style="color:#9ca3af; text-decoration:line-through;">{text_orig}</span>')
                            elif opcode == 'insert': output.append(f'<span style="background:#dcfce7; color:#15803d; font-weight:bold;">{text_corr}</span>')
                            elif opcode == 'replace': 
                                output.append(f'<span style="color:#9ca3af; text-decoration:line-through;">{text_orig}</span>')
                                output.append(f'<span style="background:#dcfce7; color:#15803d; font-weight:bold;">{text_corr}</span>')
                    return "".join(output)

                html = get_diff_html(text_input, res_text, current_mode)
                
                st.markdown(
                    f"""
                    <div style="padding:20px; border:1px dashed #ccc; border-radius:8px; line-height:2.0; font-size:18px; white-space: pre-wrap;">
                    {html}
                    </div>
                    """, 
                    unsafe_allow_html=True
                )

                # --- Word 导出 ---
                def create_docx(orig, corr):
                    doc = Document()
                    doc.add_heading('Ketty Proofreading Result', 0)
                    p = doc.add_paragraph()
                    s = difflib.SequenceMatcher(None, orig, corr)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if current_mode == "仅标红":
                            if opcode == 'equal': p.add_run(orig[a0:a1])
                            elif opcode in ['delete', 'replace']:
                                run = p.add_run(orig[a0:a1])
                                run.font.color.rgb = RGBColor(255, 0, 0)
                                run.font.bold = True
                        else:
                            if opcode == 'equal': p.add_run(orig[a0:a1])
                            elif opcode in ['insert', 'replace']:
                                run = p.add_run(corr[b0:b1])
                                run.font.color.rgb = RGBColor(0, 128, 0) # Green
                    
                    f = BytesIO()
                    doc.save(f)
                    f.seek(0)
                    return f

                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    label="📥 下载 Word 报告",
                    data=create_docx(text_input, res_text),
                    file_name=f"proofread_{current_mode}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            except Exception as e:
                st.error(f"处理出错: {str(e)}")

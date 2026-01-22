import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor # 必须保留这个颜料盒
from io import BytesIO

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="智能编辑", page_icon="✍️", layout="wide")
st.title("智能编辑助手")

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

# --- 4. 核心函数：生成 Word 文件 (支持红绿痕迹) ---
def create_word_docx(original_text, corrected_text, mode_name):
    doc = Document()
    doc.add_heading(f'DeepSeek 校对结果 ({mode_name})', 0)
    
    # === 分支逻辑 ===
    # 如果是"仅标红"模式，必须导出带痕迹的文档
    if "仅标红" in mode_name:
        p = doc.add_paragraph()
        matcher = difflib.SequenceMatcher(None, original_text, corrected_text)
        
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                run = p.add_run(original_text[a0:a1])
            elif opcode == 'delete':
                # 错的/删的 -> 红色删除线
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(255, 0, 0)
                run.font.strike = True
            elif opcode == 'insert':
                # 对的/增的 -> 绿色加粗
                run = p.add_run(corrected_text[b0:b1])
                run.font.color.rgb = RGBColor(0, 150, 0)
                run.font.bold = True
            elif opcode == 'replace':
                # 替换 -> 先红后绿
                run_del = p.add_run(original_text[a0:a1])
                run_del.font.color.rgb = RGBColor(255, 0, 0)
                run_del.font.strike = True
                run_ins = p.add_run(corrected_text[b0:b1])
                run_ins.font.color.rgb = RGBColor(0, 150, 0)
                run_ins.font.bold = True
                
        doc.add_paragraph("\n(注：红色为错误/语病，绿色为修正后的正确内容)")

    else:
        # 其他模式：导出干净文本
        doc.add_paragraph(corrected_text)
    
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### 🤖 模式设置")
    
    mode = st.radio(
        "请选择处理力度：",
        ("🔍 仅标红 (强力校对)", "🛠️ 仅纠错 (温和修正)", "✨ 深度润色 (重写优化)"),
        index=0,
        help="【仅标红】严格指出错别字、标点及语法语病，保留原句结构；\n【仅纠错】修正错误并微调句子使其通顺；\n【深度润色】优化文采和逻辑。"
    )
    
    st.markdown("---")
    st.info("本工具旨在帮助编辑校正。")

# --- 6. 核心 Prompt 策略 (关键修改) ---
if "仅标红" in mode:
    # === 关键修改：校对模式 ===
    # 这里我们要求它像"质检员"一样，只要是错的(包括语法)，必须改对，这样 difflib 才能标红。
    # 但同时要求"最小改动"，防止它乱发挥。
    system_prompt = """
    你是一个严格的文字质检员。请按照标准出版物校对规范对文本进行检查。
    
    【执行标准】：
    1. **必须修正**：错别字、标点符号误用、语法错误（如主谓搭配不当、成分缺失）、逻辑语病、数字单位错误。
    2. **严格保留**：严禁对原意进行润色、修饰或扩写。如果原句虽然口语化但没有语病，请保持原样。
    3. **目标**：输出的文本必须是语法完全正确、标点规范的版本，以便通过比对算法标出错误。
    
    请直接输出修正后的文本，不要包含任何解释。
    """
elif "仅纠错" in mode:
    system_prompt = "你是一个语文老师。请修正文本中的【错别字】、【语病】和【不通顺】的句子。保持原文的语气和原意，不要进行过度的修饰或重写，只确保语法正确、逻辑通顺即可。请直接输出修正后的文本。"
else:
    system_prompt = "你是一个资深的编辑。请对文本进行【深度润色】。在修正错误的基础上，你可以优化用词、调整句式、提升文采，使文章更加优雅、专业且富有感染力。请直接输出润色后的文本。"

# 主界面
original_text = st.text_area("请输入文章/段落：", height=200, placeholder="在此粘贴文字...")

# 获取当前模式名称
current_mode_name = mode.split(' ')[1]

if st.button(f"🚀 开始执行：{current_mode_name}", type="primary"):
    if not original_text:
        st.warning("请先输入文字哦！")
    else:
        with st.spinner("AI 正在逐字推敲中..."):
            try:
                # 调用 API
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": original_text},
                    ],
                    stream=False
                )
                corrected_text = response.choices[0].message.content.strip()

                st.success("处理完成！")

                # --- 差异对比逻辑 (HTML渲染) ---
                st.subheader("🔍 校对痕迹")
                
                def diff_strings_html(a, b):
                    output = []
                    s = difflib.SequenceMatcher(None, a, b)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if opcode == 'equal':
                            output.append(s.a[a0:a1])
                        elif opcode == 'insert':
                            # 绿色
                            output.append(f'<span style="background-color:#d4edda; color:#155724; font-weight:bold; padding:0 2px;">{s.b[b0:b1]}</span>')
                        elif opcode == 'delete':
                            # 红色删除线
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                        elif opcode == 'replace':
                            # 替换
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                            output.append(f'<span style="background-color:#d4edda; color:#155724; font-weight:bold; padding:0 2px;">{s.b[b0:b1]}</span>')
                    return "".join(output)

                diff_html = diff_strings_html(original_text, corrected_text)
                st.markdown(f'<div style="font-size:16px; line-height:1.6; border:1px solid #ddd; padding:15px; border-radius:5px; background-color:#fafafa;">{diff_html}</div>', unsafe_allow_html=True)

                # --- 结果展示与导出 ---
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("**📋 对比后结果（供复制）：**")
                    st.code(corrected_text, language="text")
                
                with col2:
                    st.markdown("**📥 下载校对稿：**")
                    word_file = create_word_docx(original_text, corrected_text, current_mode_name)
                    st.download_button(
                        label="下载红头文件 (.docx)",
                        data=word_file,
                        file_name=f"DeepSeek_{current_mode_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

            except Exception as e:
                st.error(f"发生错误：{e}")

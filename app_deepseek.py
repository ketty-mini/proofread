import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor
from io import BytesIO

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="智能编辑", page_icon="⚖️", layout="wide")
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

# --- 4. 核心函数：生成 Word 文件 ---
def create_word_docx(original_text, corrected_text, mode_name):
    doc = Document()
    doc.add_heading(f'DeepSeek 质检标记 ({mode_name})', 0)
    
    # === 分支逻辑 ===
    if "仅标红" in mode_name:
        # === Word 导出逻辑：只变红，不删不增 ===
        p = doc.add_paragraph()
        matcher = difflib.SequenceMatcher(None, original_text, corrected_text)
        
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                # 正确：黑色
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(0, 0, 0)
            elif opcode == 'delete':
                # 多余：标红 (无删除线)
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(255, 0, 0)
                run.font.strike = False 
            elif opcode == 'replace':
                # 错误：标红原文 (无删除线)
                run_del = p.add_run(original_text[a0:a1])
                run_del.font.color.rgb = RGBColor(255, 0, 0)
                run_del.font.strike = False
            # insert 忽略
                
        doc.add_paragraph("\n(说明：文中【红色字体】为疑似语病、错别字或标点错误)")

    else:
        # 其他模式：导出修正后的文本
        doc.add_paragraph(corrected_text)
    
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### ⚖️ 质检标准")
    
    mode = st.radio(
        "请选择模式：",
        ("🔍 仅标红 (字/词/标点/语法)", "🛠️ 仅纠错 (直接修正)", "✨ 深度润色 (文采提升)"),
        index=0,
        help="【仅标红】网页和文档均只显示原文，错误之处用红色字体标出，无修改建议，无删除线。"
    )
    
    st.markdown("---")
    st.info("💡 已启用 GB/T 15834 标点符号用法 & 现代汉语通用语法规范。")

# --- 6. 核心 Prompt ---
if "仅标红" in mode:
    # 强制修正以触发 Diff，但在前端只显示红色原文
    system_prompt = """
    你是一个极其严苛的图书质检员。请对文本进行全维度的【死磕式校对】。
    
    【必须修正的错误类型】：
    1. **标点符号**：严格执行 GB/T 15834 标准。
    2. **语法语病**：修正成分缺失、搭配不当、语序混乱。
    3. **错别字与词汇**：修正错别字和不规范异形词。
       
    【输出要求】：
    - 输出修正后的完美文本。
    - 系统会比对你的输出与原文，将差异处标红。
    - 不要解释，直接输出正文。
    """
elif "仅纠错" in mode:
    system_prompt = "你是一个语文老师。请修正文本中的【错别字】、【语病】和【不通顺】的句子。保持原文的语气和原意，不要进行过度的修饰或重写，只确保语法正确、逻辑通顺即可。请直接输出修正后的文本。"
else:
    system_prompt = "你是一个资深的编辑。请对文本进行【深度润色】。在修正错误的基础上，你可以优化用词、调整句式、提升文采，使文章更加优雅、专业且富有感染力。请直接输出润色后的文本。"

# 主界面
st.markdown("#### 📝 全文质检台")
original_text = st.text_area("输入文稿：", height=200, placeholder="在此粘贴文章...")

current_mode_name = mode.split(' ')[1]

if st.button(f"🚀 开始扫描：{current_mode_name}", type="primary"):
    if not original_text:
        st.warning("请先输入文字！")
    else:
        with st.spinner("AI 正在进行全维度质检扫描..."):
            try:
                # API 调用
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": original_text},
                    ],
                    stream=False
                )
                corrected_text = response.choices[0].message.content.strip()

                st.success("扫描完成！")

                # --- 差异对比逻辑 (HTML 生成) ---
                st.subheader("🔍 质检结果预览")
                
                # 定义不同模式下的网页显示逻辑
                def generate_diff_html(original, corrected, mode_label):
                    output = []
                    s = difflib.SequenceMatcher(None, original, corrected)
                    
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if "仅标红" in mode_label:
                            # === 仅标红模式：只显示原文，错误变红，无绿色建议 ===
                            if opcode == 'equal':
                                output.append(f'<span>{original[a0:a1]}</span>')
                            elif opcode == 'delete':
                                # 红色字 (原文)
                                output.append(f'<span style="color:#e03131; font-weight:bold;">{original[a0:a1]}</span>')
                            elif opcode == 'replace':
                                # 红色字 (原文)
                                output.append(f'<span style="color:#e03131; font-weight:bold;">{original[a0:a1]}</span>')
                            elif opcode == 'insert':
                                # 忽略新插入的内容
                                pass
                        else:
                            # === 其他模式：保留红绿对比，方便看改了什么 ===
                            if opcode == 'equal':
                                output.append(original[a0:a1])
                            elif opcode == 'insert':
                                output.append(f'<span style="background-color:#d4edda; color:#155724; padding:0 2px;">{corrected[b0:b1]}</span>')
                            elif opcode == 'delete':
                                output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through;">{original[a0:a1]}</span>')
                            elif opcode == 'replace':
                                output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through;">{original[a0:a1]}</span>')
                                output.append(f'<span style="background-color:#d4edda; color:#155724; padding:0 2px;">{corrected[b0:b1]}</span>')
                                
                    return "".join(output)

                diff_html = generate_diff_html(original_text, corrected_text, mode)
                
                # 渲染 HTML
                st.markdown(
                    f'<div style="font-size:16px; line-height:1.8; border:1px solid #ddd; padding:20px; border-radius:5px; background-color:#fff; color:#333;">{diff_html}</div>', 
                    unsafe_allow_html=True
                )
                
                if "仅标红" in mode:
                     st.caption("👆 说明：预览框中【红色加粗】的文字即为系统判定存在语病或错误的原文。")

                # --- 结果导出 ---
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.empty()
                
                with col2:
                    st.markdown("**📥 导出文档：**")
                    word_file = create_word_docx(original_text, corrected_text, current_mode_name)
                    st.download_button(
                        label="下载 Word (.docx)",
                        data=word_file,
                        file_name=f"DeepSeek_质检_{current_mode_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

            except Exception as e:
                st.error(f"发生错误：{e}")

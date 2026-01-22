import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from io import BytesIO

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="智能纠错", page_icon="✍️", layout="wide")
st.title("智能纠错助手")

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

# --- 4. 辅助函数：生成 Word 文件 ---
def create_word_docx(text):
    doc = Document()
    doc.add_heading('DeepSeek 润色结果', 0)
    doc.add_paragraph(text)
    # 将文档保存到内存流中，而不是硬盘
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### 🤖 关于本工具")
    st.info("本工具由 DeepSeek V3 驱动。")
    st.markdown("---")
    st.markdown("**功能更新：**\n✨ 支持一键复制\n📥 支持导出 Word")

# 主界面
original_text = st.text_area("请输入文章/段落：", height=200, placeholder="在此粘贴文字...")

if st.button("✨ 开始智能润色", type="primary"):
    if not original_text:
        st.warning("请先输入文字哦！")
    else:
        with st.spinner("DeepSeek 正在思考中..."):
            try:
                # 调用 API
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是一个专业的文字校对员。请纠正错别字、语病并润色。直接输出修正后的文本，不要包含任何解释。"},
                        {"role": "user", "content": original_text},
                    ],
                    stream=False
                )
                corrected_text = response.choices[0].message.content.strip()

                st.success("润色完成！")

                # --- 核心功能区：左右分栏对比 ---
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📝 原文")
                    st.text(original_text)
                with col2:
                    st.subheader("✅ 修正后")
                    # 使用 st.code 显示，因为 st.code 右上角自带“复制”按钮
                    st.code(corrected_text, language="text")

                # --- 差异对比 ---
                st.markdown("---")
                st.subheader("🔍 差异高亮")
                
                def diff_strings(a, b):
                    output = []
                    s = difflib.SequenceMatcher(None, a, b)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if opcode == 'equal':
                            output.append(s.a[a0:a1])
                        elif opcode == 'insert':
                            output.append(f'<span style="background-color:#d4edda; color:#155724;">{s.b[b0:b1]}</span>')
                        elif opcode == 'delete':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through;">{s.a[a0:a1]}</span>')
                        elif opcode == 'replace':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through;">{s.a[a0:a1]}</span>')
                            output.append(f'<span style="background-color:#d4edda; color:#155724;">{s.b[b0:b1]}</span>')
                    return "".join(output)

                diff_html = diff_strings(original_text, corrected_text)
                st.markdown(diff_html, unsafe_allow_html=True)

                # --- 导出区 ---
                st.markdown("---")
                st.subheader("📥 导出结果")
                
                # 生成 Word 文件流
                word_file = create_word_docx(corrected_text)
                
                # 下载按钮
                st.download_button(
                    label="📄 下载 Word 文档 (.docx)",
                    data=word_file,
                    file_name="DeepSeek_润色结果.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            except Exception as e:
                st.error(f"发生错误：{e}")

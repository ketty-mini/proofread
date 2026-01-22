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
    doc.add_heading('DeepSeek 修正结果', 0)
    doc.add_paragraph(text)
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### 🤖 功能设置")
    
    # === 新增：模式选择 ===
    mode = st.radio(
        "选择纠错模式：",
        ("🔍 仅纠错 (只改错别字)", "✨ 深度润色 (优化文采)"),
        index=0,
        help="【仅纠错】只修改错字病句，保留原句结构；【深度润色】会优化句子通顺度。"
    )
    
    st.markdown("---")
    st.info("本工具能自动纠正中文错别字、语病并进行润色。")

# 根据模式设定 Prompt
if mode == "🔍 仅纠错 (只改错别字)":
    system_prompt = "你是一个严谨的校对员。请仅修正文中的错别字、标点错误和明显的语法错误。绝不要修改句子结构，不要替换同义词，不要进行润色，不要改变原文的语气。请直接输出修正后的文本，不要包含任何解释。"
else:
    system_prompt = "你是一个专业的编辑。请纠正用户输入文本中的错别字和语病，并对文字进行适当润色，使其更加通顺、优雅。请直接输出修正后的文本，不要包含任何解释。"

# 主界面
original_text = st.text_area("请输入文章/段落：", height=200, placeholder="在此粘贴文字...")

if st.button("🚀 开始执行", type="primary"):
    if not original_text:
        st.warning("请先输入文字哦！")
    else:
        with st.spinner("AI 正在逐字检查中..."):
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

                # --- 差异对比逻辑 ---
                st.subheader("🔍 结果对比")
                
                # 为了让“仅标红”看得更清楚，我们把 HTML 样式微调一下
                def diff_strings(a, b):
                    output = []
                    s = difflib.SequenceMatcher(None, a, b)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if opcode == 'equal':
                            # 未变动的部分
                            output.append(s.a[a0:a1])
                        elif opcode == 'insert':
                            # 新增的部分（绿色）
                            output.append(f'<span style="background-color:#d4edda; color:#155724; font-weight:bold; padding:0 2px;">{s.b[b0:b1]}</span>')
                        elif opcode == 'delete':
                            # 删除的部分（红色+删除线）- 这就是你要的“标红”
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                        elif opcode == 'replace':
                            # 替换的部分
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                            output.append(f'<span style="background-color:#d4edda; color:#155724; font-weight:bold; padding:0 2px;">{s.b[b0:b1]}</span>')
                    return "".join(output)

                diff_html = diff_strings(original_text, corrected_text)
                
                # 显示带有颜色的对比文本
                st.markdown(f'<div style="font-size:16px; line-height:1.6; border:1px solid #ddd; padding:15px; border-radius:5px;">{diff_html}</div>', unsafe_allow_html=True)
                
                st.caption("💡 红色删除线表示错误/被删除的内容，绿色表示修正后的内容。")

                # --- 纯净版结果与导出 ---
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("**📋 最终纯净文本：**")
                    st.code(corrected_text, language="text")
                
                with col2:
                    st.markdown("**📥 下载：**")
                    word_file = create_word_docx(corrected_text)
                    st.download_button(
                        label="下载 Word 文档",
                        data=word_file,
                        file_name="DeepSeek_修正结果.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

            except Exception as e:
                st.error(f"发生错误：{e}")

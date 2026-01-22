import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from io import BytesIO

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="DeepSeek 智能纠错", page_icon="✍️", layout="wide")
st.title("DeepSeek 智能纠错助手")

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
def create_word_docx(text, mode_name):
    doc = Document()
    doc.add_heading(f'DeepSeek 修正结果 ({mode_name})', 0)
    doc.add_paragraph(text)
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### 🤖 模式设置")
    
    # === 新增：三种模式选择 ===
    mode = st.radio(
        "请选择处理力度：",
        ("🔍 仅标红 (只改错别字)", "🛠️ 仅纠错 (修补语病)", "✨ 深度润色 (提升文采)"),
        index=0,
        help="【仅标红】极度克制，只改明显的错字标点；\n【仅纠错】修正语法和句子不通顺；\n【深度润色】优化用词和语气，提升可读性。"
    )
    
    st.markdown("---")
    st.info("本工具由 DeepSeek V3 驱动。")

# --- 6. 核心 Prompt 策略 (根据模式切换) ---
# 这里的缩进非常重要，请不要手动修改
if "仅标红" in mode:
    # 极度保守模式
    system_prompt = "你是一个严谨的文字校对员。你的任务仅仅是找出并修正文本中的【错别字】和【标点符号错误】。⚠️ 绝对禁止修改句子结构、用词习惯或语气。如果一句话没有错别字，请原样输出。请直接输出结果，不要包含任何解释。"
elif "仅纠错" in mode:
    # 语法修复模式
    system_prompt = "你是一个语文老师。请修正文本中的【错别字】、【语病】和【不通顺】的句子。保持原文的语气和原意，不要进行过度的修饰或重写，只确保语法正确、逻辑通顺即可。请直接输出修正后的文本。"
else:
    # 深度润色模式
    system_prompt = "你是一个资深的编辑。请对文本进行【深度润色】。在修正错误的基础上，你可以优化用词、调整句式、提升文采，使文章更加优雅、专业且富有感染力。请直接输出润色后的文本。"

# 主界面
original_text = st.text_area("请输入文章/段落：", height=200, placeholder="在此粘贴文字...")

# 获取当前模式名称用于按钮显示
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
                st.subheader("🔍 修改痕迹 (红=删, 绿=增)")
                
                def diff_strings(a, b):
                    output = []
                    s = difflib.SequenceMatcher(None, a, b)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if opcode == 'equal':
                            output.append(s.a[a0:a1])
                        elif opcode == 'insert':
                            # 绿色背景
                            output.append(f'<span style="background-color:#d4edda; color:#155724; font-weight:bold; padding:0 2px;">{s.b[b0:b1]}</span>')
                        elif opcode == 'delete':
                            # 红色背景+删除线
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                        elif opcode == 'replace':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                            output.append(f'<span style="background-color:#d4edda; color:#155724; font-weight:bold; padding:0 2px;">{s.b[b0:b1]}</span>')
                    return "".join(output)

                diff_html = diff_strings(original_text, corrected_text)
                
                # 渲染对比框
                st.markdown(f'<div style="font-size:16px; line-height:1.6; border:1px solid #ddd; padding:15px; border-radius:5px; background-color:#fafafa;">{diff_html}</div>', unsafe_allow_html=True)

                # --- 纯净版结果与导出 ---
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("**📋 最终结果：**")
                    st.code(corrected_text, language="text")
                
                with col2:
                    st.markdown("**📥 存为文档：**")
                    word_file = create_word_docx(corrected_text, current_mode_name)
                    st.download_button(
                        label="下载 Word (.docx)",
                        data=word_file,
                        file_name=f"DeepSeek_{current_mode_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

            except Exception as e:
                st.error(f"发生错误：{e}")

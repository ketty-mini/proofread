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
        # === 您的核心需求：全维度标红 ===
        # 逻辑：原文中任何被 AI 判定为"不合规"（包括标点、语法、错字）的内容，都必须加红线。
        p = doc.add_paragraph()
        matcher = difflib.SequenceMatcher(None, original_text, corrected_text)
        
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                # 正确的部分：黑色
                run = p.add_run(original_text[a0:a1])
            elif opcode == 'delete':
                # 纯粹多余的内容：红色删除线
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(255, 0, 0)
                run.font.strike = True
            elif opcode == 'replace':
                # 核心：被修改的内容（可能是错字，也可能是标点或语病）
                # 我们只保留原文，并打上红色删除线，表示"此处有误"
                run_del = p.add_run(original_text[a0:a1])
                run_del.font.color.rgb = RGBColor(255, 0, 0)
                run_del.font.strike = True
            # insert (增补) 被忽略，保证"不纠错，只标红"
                
        doc.add_paragraph("\n(说明：红色删除线标示了错别字、标点误用、语病或不规范表达)")

    else:
        # 其他模式保持原样
        doc.add_paragraph(corrected_text)
    
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### ⚖️ 质检标准")
    
    # 修改了选项描述，强调语病和标点
    mode = st.radio(
        "请选择模式：",
        ("🔍 仅标红 (字/词/标点/语法)", "🛠️ 仅纠错 (直接修正)", "✨ 深度润色 (文采提升)"),
        index=0,
        help="【仅标红】高灵敏度模式。凡是错别字、标点错误、语病、搭配不当，原文都会被标红划掉。"
    )
    
    st.markdown("---")
    st.info("💡 已启用 GB/T 15834 标点符号用法 & 现代汉语通用语法规范。")

# --- 6. 核心 Prompt (针对语法和标点进行了极强强化) ---
if "仅标红" in mode:
    # === 核心：全维度排查 Prompt ===
    # 我们要求 AI 只要发现任何不符合规范的地方（哪怕是一个逗号），都要进行修正。
    # 只有 AI 修正了，代码里的 diff 算法才能检测到不同，从而标红。
    system_prompt = """
    你是一个极其严苛的图书质检员。请对文本进行全维度的【死磕式校对】。
    
    【必须修正的错误类型】：
    1. **标点符号**：严格执行 GB/T 15834 标准。
       - 修正中英文标点混用（如中文句子里用了英文逗号）。
       - 修正标点层级错误（如并列词语误用逗号而非顿号）。
       - 补全缺失的标点。
    2. **语法语病**：
       - **成分缺失**：如缺主语、缺谓语。
       - **搭配不当**：如"水平提高"（对）vs "水平培养"（错）。
       - **语序混乱**：如"我把作业做完了在昨天" -> 修正为"我昨天把作业做完了"。
    3. **错别字与词汇**：
       - 修正所有错别字。
       - 修正异形词（以《现代汉语词典》为准）。
       
    【处理逻辑】：
    - 请输出修正后的**完美文本**。
    - 你的每一次修改（无论是一个标点还是调整语序），系统都会自动在原文上生成红色标记。
    - 如果原句完全符合规范，则原样输出。
    
    请直接输出结果，不要解释。
    """
elif "仅纠错" in mode:
    system_prompt = "你是一个语文老师。请修正文本中的【错别字】、【语病】和【不通顺】的句子。保持原文的语气和原意，不要进行过度的修饰或重写，只确保语法正确、逻辑通顺即可。请直接输出修正后的文本。"
else:
    system_prompt = "你是一个资深的编辑。请对文本进行【深度润色】。在修正错误的基础上，你可以优化用词、调整句式、提升文采，使文章更加优雅、专业且富有感染力。请直接输出润色后的文本。"

# 主界面
st.markdown("#### 📝 全文质检台")
original_text = st.text_area("输入文稿：", height=200, placeholder="粘贴文章，系统将自动扫描错字、语病及标点错误...")

current_mode_name = mode.split(' ')[1]

if st.button(f"🚀 开始扫描：{current_mode_name}", type="primary"):
    if not original_text:
        st.warning("请先输入文字！")
    else:
        with st.spinner("AI 正在进行全维度（字/词/句/标点）核查..."):
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

                st.success("扫描完成！")

                # --- 差异对比逻辑 (网页版：为了让你确认，这里还是会显示绿色的正确建议) ---
                st.subheader("🔍 错误定位")
                
                def diff_strings_html(a, b):
                    output = []
                    s = difflib.SequenceMatcher(None, a, b)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if opcode == 'equal':
                            output.append(s.a[a0:a1])
                        elif opcode == 'insert':
                            # 网页版显示绿色建议，方便你核对
                            output.append(f'<span style="background-color:#d4edda; color:#155724; border-bottom:2px solid #28a745; padding:0 2px;">{s.b[b0:b1]}</span>')
                        elif opcode == 'delete':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                        elif opcode == 'replace':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                            output.append(f'<span style="background-color:#d4edda; color:#155724; border-bottom:2px solid #28a745; padding:0 2px;">{s.b[b0:b1]}</span>')
                    return "".join(output)

                diff_html = diff_strings_html(original_text, corrected_text)
                st.markdown(f'<div style="font-size:16px; line-height:1.8; border:1px solid #ddd; padding:20px; border-radius:5px; background-color:#fff;">{diff_html}</div>', unsafe_allow_html=True)

                # --- 结果导出 ---
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.caption("注：下载的文档将严格执行'只标红、不修改'的策略。")
                
                with col2:
                    st.markdown("**📥 获取标记文档：**")
                    word_file = create_word_docx(original_text, corrected_text, current_mode_name)
                    st.download_button(
                        label="下载质检红样 (.docx)",
                        data=word_file,
                        file_name=f"DeepSeek_质检_{current_mode_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

            except Exception as e:
                st.error(f"发生错误：{e}")

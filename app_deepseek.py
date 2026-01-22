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
        # === 您的核心需求：只变色，不划线 ===
        p = doc.add_paragraph()
        matcher = difflib.SequenceMatcher(None, original_text, corrected_text)
        
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                # 正确的部分：黑色 (默认)
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(0, 0, 0) # 黑色
            elif opcode == 'delete':
                # AI认为多余的内容：标红 (无删除线)
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(255, 0, 0) # 红色
                run.font.strike = False # ❌ 去掉删除线
            elif opcode == 'replace':
                # AI认为错误需要修改的内容：标红 (无删除线)
                # 我们只保留原文，并变成红色，提醒用户这里有问题
                run_del = p.add_run(original_text[a0:a1])
                run_del.font.color.rgb = RGBColor(255, 0, 0) # 红色
                run_del.font.strike = False # ❌ 去掉删除线
            # insert (增补) 依然忽略，保持"只看原文"的整洁性
                
        doc.add_paragraph("\n(说明：文中【红色字体】为 DeepSeek 依据出版国标判定存在语病、错别字或标点错误的原文)")

    else:
        # 其他模式：导出干净的修正后文本
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
        help="【仅标红】高灵敏度模式。凡是错别字、标点错误、语病，原文会直接变成红色字体（无删除线）。"
    )
    
    st.markdown("---")
    st.info("💡 已启用 GB/T 15834 标点符号用法 & 现代汉语通用语法规范。")

# --- 6. 核心 Prompt (保持最严格的国标质检逻辑) ---
if "仅标红" in mode:
    # === 核心：全维度排查 Prompt ===
    # 只要有任何不符合规范的地方，AI 必须修正，这样 difflib 才能捕捉到差异并标红。
    system_prompt = """
    你是一个极其严苛的图书质检员。请对文本进行全维度的【死磕式校对】。
    
    【必须修正的错误类型】：
    1. **标点符号**：严格执行 GB/T 15834 标准。修正中西文标点混用、标点层级错误。
    2. **语法语病**：
       - **成分缺失**：如缺主语、缺谓语。
       - **搭配不当**：如"水平培养"应改为"能力培养"。
       - **语序混乱**：如"我把作业做完了在昨天"应改为"我昨天把作业做完了"。
    3. **错别字与词汇**：修正所有错别字和不规范异形词。
       
    【处理逻辑】：
    - 请输出修正后的**完美文本**。
    - 系统会对你的修正版和原文进行比对，凡是你修改过的地方，原文都会变成红色。
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
        with st.spinner("AI 正在依照国家出版标准扫描语病和错字..."):
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

                # --- 差异对比逻辑 (网页版：依然显示红绿对比，方便你核查原因) ---
                st.subheader("🔍 错误定位预览")
                
                def diff_strings_html(a, b):
                    output = []
                    s = difflib.SequenceMatcher(None, a, b)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if opcode == 'equal':
                            output.append(s.a[a0:a1])
                        elif opcode == 'insert':
                            # 网页版显示绿色建议，告诉你"应该"改成什么
                            output.append(f'<span style="background-color:#d4edda; color:#155724; border-bottom:2px solid #28a745; padding:0 2px;">{s.b[b0:b1]}</span>')
                        elif opcode == 'delete':
                            # 红色删除线 (网页版保留删除线是为了区分)
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                        elif opcode == 'replace':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                            output.append(f'<span style="background-color:#d4edda; color:#155724; border-bottom:2px solid #28a745; padding:0 2px;">{s.b[b0:b1]}</span>')
                    return "".join(output)

                diff_html = diff_strings_html(original_text, corrected_text)
                st.caption("👇 网页预览保留了修改建议（绿色），**下载的 Word 文档将只有红字原文**。")
                st.markdown(f'<div style="font-size:16px; line-height:1.8; border:1px solid #ddd; padding:20px; border-radius:5px; background-color:#fff;">{diff_html}</div>', unsafe_allow_html=True)

                # --- 结果导出 ---
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.empty() # 占位
                
                with col2:
                    st.markdown("**📥 获取纯红字标记稿：**")
                    word_file = create_word_docx(original_text, corrected_text, current_mode_name)
                    st.download_button(
                        label="下载 Word (.docx)",
                        data=word_file,
                        file_name=f"DeepSeek_质检_{current_mode_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

            except Exception as e:
                st.error(f"发生错误：{e}")

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
    doc.add_heading(f'DeepSeek 校对报告 ({mode_name})', 0)
    
    # === 分支逻辑 ===
    if "仅标红" in mode_name:
        # === 严格校对模式：只标红错误，不显示修正后的绿色文字 ===
        p = doc.add_paragraph()
        matcher = difflib.SequenceMatcher(None, original_text, corrected_text)
        
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                # 原文无误：黑色
                run = p.add_run(original_text[a0:a1])
            elif opcode == 'delete':
                # 错误/多余：红色 + 删除线
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(255, 0, 0)
                run.font.strike = True
            elif opcode == 'replace':
                # 替换：只把原文中错误的部分标红划掉
                # 这里不写入 corrected_text (绿色部分)，只保留"红笔圈错"的效果
                run_del = p.add_run(original_text[a0:a1])
                run_del.font.color.rgb = RGBColor(255, 0, 0)
                run_del.font.strike = True
            # insert (插入) 分支被完全忽略，不体现在文档中
                
        doc.add_paragraph("\n(注：依据国家出版标准，红色删除线内容判定为【错讹/不规范/语病】)")

    else:
        # 其他模式：导出干净的最终文本
        doc.add_paragraph(corrected_text)
    
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### ⚖️ 校对标准设置")
    
    mode = st.radio(
        "请选择执行标准：",
        ("🔍 仅标红 (国家出版标准)", "🛠️ 仅纠错 (常规语法修复)", "✨ 深度润色 (文采提升)"),
        index=0,
        help="【仅标红】执行 GB/T 15834 等国家标准，严格指出错讹、语病、标点错误；\n【仅纠错】修正语法使其通顺；\n【深度润色】优化文采。"
    )
    
    st.markdown("---")
    st.info("💡 标红模式已接入《图书质量管理规定》校对逻辑。")

# --- 6. 核心 Prompt 策略 (由 DeepSeek V3 执行) ---
if "仅标红" in mode:
    # === 核心修改：国家级出版校对 Prompt ===
    system_prompt = """
    你是一位拥有30年经验的国家级出版社资深质检员。请对提供的文本进行【封闭式校对】。
    
    【执行标准】：
    严格依据以下中国国家标准进行检查：
    1. 《标点符号用法》(GB/T 15834-2011)：严格修正中西文标点混用、顿号与逗号层级混乱、数值范围符号错误等。
    2. 《出版物上数字用法》(GB/T 15835-2011)：统一数字书写规范。
    3. 《现代汉语词典》(第7版)：修正错别字、异形词（如将"登陆网站"修正为"登录网站"）。
    4. 语法规范：修正成分残缺、搭配不当、句式杂糅、逻辑矛盾。
    
    【绝对禁令】：
    1. **严禁润色**：绝对不允许修改作者的文风、语气或修辞。
    2. **严禁扩写**：除了补充必要的缺失成分外，不得增加任何修饰性词语。
    3. **只改硬伤**：只有在判定为“不符合出版规范”时才修改。如果是口语化表达但符合语法，**保持原样**。
    
    【输出要求】：
    直接输出经过修正后的全文。不要输出任何解释、列表或备注。
    """
elif "仅纠错" in mode:
    system_prompt = "你是一个语文老师。请修正文本中的【错别字】、【语病】和【不通顺】的句子。保持原文的语气和原意，不要进行过度的修饰或重写，只确保语法正确、逻辑通顺即可。请直接输出修正后的文本。"
else:
    system_prompt = "你是一个资深的编辑。请对文本进行【深度润色】。在修正错误的基础上，你可以优化用词、调整句式、提升文采，使文章更加优雅、专业且富有感染力。请直接输出润色后的文本。"

# 主界面
st.markdown("#### 📝 待审稿件")
original_text = st.text_area("请粘贴文本：", height=200, placeholder="在此输入需要校对的文字...")

current_mode_name = mode.split(' ')[1]

if st.button(f"🚀 执行质检：{current_mode_name}", type="primary"):
    if not original_text:
        st.warning("请先输入文字哦！")
    else:
        with st.spinner("正在依照国标 GB/T 15834 进行逐字核查..."):
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

                st.success("校对完成！")

                # --- 差异对比逻辑 (网页端保留红绿对比，方便你审核) ---
                st.subheader("🔍 质检痕迹 (红=问题, 绿=建议)")
                
                def diff_strings_html(a, b):
                    output = []
                    s = difflib.SequenceMatcher(None, a, b)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if opcode == 'equal':
                            output.append(s.a[a0:a1])
                        elif opcode == 'insert':
                            # 绿色 (建议增补/修正的内容)
                            output.append(f'<span style="background-color:#d4edda; color:#155724; font-weight:bold; border-bottom: 2px solid #28a745; padding:0 2px;">{s.b[b0:b1]}</span>')
                        elif opcode == 'delete':
                            # 红色 (不符合国标的内容)
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                        elif opcode == 'replace':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; font-weight:bold; padding:0 2px;">{s.a[a0:a1]}</span>')
                            output.append(f'<span style="background-color:#d4edda; color:#155724; font-weight:bold; border-bottom: 2px solid #28a745; padding:0 2px;">{s.b[b0:b1]}</span>')
                    return "".join(output)

                diff_html = diff_strings_html(original_text, corrected_text)
                st.markdown(f'<div style="font-size:16px; line-height:1.8; border:1px solid #ddd; padding:20px; border-radius:5px; background-color:#fff; font-family: "SimSun", "Songti SC", serif;">{diff_html}</div>', unsafe_allow_html=True)

                # --- 结果展示与导出 ---
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.caption("注：网页预览显示修正建议（绿色），下载的文档将仅标示错误（红色）。")
                
                with col2:
                    st.markdown("**📥 导出报告：**")
                    word_file = create_word_docx(original_text, corrected_text, current_mode_name)
                    st.download_button(
                        label="下载质检标记稿 (.docx)",
                        data=word_file,
                        file_name=f"DeepSeek_质检_{current_mode_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

            except Exception as e:
                st.error(f"发生错误：{e}")

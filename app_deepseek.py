import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor, Pt
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
    
    # 设置正文样式基础
    style = doc.styles['Normal']
    style.font.name = 'SimSun' # 宋体
    style.element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')
    
    # === 分支逻辑 ===
    if "仅标红" in mode_name:
        p = doc.add_paragraph()
        matcher = difflib.SequenceMatcher(None, original_text, corrected_text)
        
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                # 正确：黑色
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(0, 0, 0)
            elif opcode == 'delete':
                # 多余的内容：红色 (不划线，直接红字警示)
                run = p.add_run(original_text[a0:a1])
                run.font.color.rgb = RGBColor(255, 0, 0)
                run.font.strike = False 
            elif opcode == 'replace':
                # 错误的内容（含错别字、错标点）：红色原文
                run_del = p.add_run(original_text[a0:a1])
                run_del.font.color.rgb = RGBColor(255, 0, 0)
                run_del.font.strike = False
            elif opcode == 'insert':
                # === 关键修复：缺失内容警示 ===
                # 如果 AI 觉得这里缺标点或缺字，我们在原文位置加一个红色的 ^
                run_ins = p.add_run("^") 
                run_ins.font.color.rgb = RGBColor(255, 0, 0)
                run_ins.font.bold = True
                run_ins.font.size = Pt(12) # 稍微大一点以便看见
                
        doc.add_paragraph("\n(图例：【红色文字】= 错字/多余；【^】= 此处缺失标点或成分)")

    else:
        doc.add_paragraph(corrected_text)
    
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# 为了 Word 字体设置引入的库
from docx.oxml.ns import qn

# --- 5. 界面逻辑 ---
with st.sidebar:
    st.markdown("### ⚖️ 质检标准")
    
    mode = st.radio(
        "请选择模式：",
        ("🔍 仅标红 (字/词/标点/语法)", "🛠️ 仅纠错 (直接修正)", "✨ 深度润色 (文采提升)"),
        index=0,
        help="【仅标红】显示原文。错误文字变红；缺失标点的地方会显示红色的 ^ 符号。"
    )
    
    st.markdown("---")
    st.info("💡 已强化。")

# --- 6. 核心 Prompt (针对标点极其变态的严格) ---
if "仅标红" in mode:
    # 强制要求 AI 即使是一个顿号不对也要修正，这样 Diff 算法才能抓到
    system_prompt = """
    你是一个根据《图书质量管理规定》工作的魔鬼质检员。
    
    【核心任务】：
    对文本进行"地毯式"扫描，输出一份**完美符合中国出版规范**的文本。
    
    【必须纠正的微小错误】：
    1. **标点绝对严格**：
       - 补全所有句子末尾漏掉的句号。
       - 修正"逗号一逗到底"的问题。
       - 区分中英文标点（如将 , 改为 ，）。
       - 数值范围必须用波浪线（~）或一字线。
    2. **修正错别字与异形词**。
    3. **修正语病**。
    
    【输出格式】：
    直接输出修正后的全文。不要带任何解释。
    """
elif "仅纠错" in mode:
    system_prompt = "你是一个语文老师。请修正文本中的【错别字】、【语病】和【标点错误】。保持原文语气，只确保规范通顺。请直接输出修正后的文本。"
else:
    system_prompt = "你是一个资深的编辑。请对文本进行【深度润色】。优化用词、调整句式、提升文采。请直接输出润色后的文本。"

# 主界面
st.markdown("#### 📝 全文质检台")
original_text = st.text_area("输入文稿：", height=200, placeholder="尝试输入一句没标点的话，例如：'今天天气不错我们去公园玩' ...")

current_mode_name = mode.split(' ')[1]

if st.button(f"🚀 开始扫描：{current_mode_name}", type="primary"):
    if not original_text:
        st.warning("请先输入文字！")
    else:
        with st.spinner("AI 正在拿放大镜找标点错误..."):
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

                # --- 差异对比逻辑 (HTML) ---
                st.subheader("🔍 质检结果预览")
                
                def generate_diff_html(original, corrected, mode_label):
                    output = []
                    s = difflib.SequenceMatcher(None, original, corrected)
                    
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if "仅标红" in mode_label:
                            # === 仅标红逻辑 ===
                            if opcode == 'equal':
                                output.append(f'<span style="color:#000;">{original[a0:a1]}</span>')
                            elif opcode == 'delete':
                                # 多余的字：红色
                                output.append(f'<span style="color:#dc3545; font-weight:bold;">{original[a0:a1]}</span>')
                            elif opcode == 'replace':
                                # 错字/错标点：红色
                                output.append(f'<span style="color:#dc3545; font-weight:bold;">{original[a0:a1]}</span>')
                            elif opcode == 'insert':
                                # 缺失标点/缺字：显示红色 ^
                                output.append(f'<span style="color:#dc3545; font-weight:bold; font-size:1.2em;">^</span>')
                        else:
                            # === 其他模式 ===
                            if opcode == 'equal':
                                output.append(original[a0:a1])
                            elif opcode == 'insert':
                                output.append(f'<span style="background-color:#d4edda; color:#155724;">{corrected[b0:b1]}</span>')
                            elif opcode == 'delete':
                                output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through;">{original[a0:a1]}</span>')
                            elif opcode == 'replace':
                                output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through;">{original[a0:a1]}</span>')
                                output.append(f'<span style="background-color:#d4edda; color:#155724;">{corrected[b0:b1]}</span>')
                                
                    return "".join(output)

                diff_html = generate_diff_html(original_text, corrected_text, mode)
                
                st.markdown(
                    f'<div style="font-size:16px; line-height:1.8; border:1px solid #ddd; padding:20px; border-radius:5px; background-color:#fff;">{diff_html}</div>', 
                    unsafe_allow_html=True
                )
                
                if "仅标红" in mode:
                     st.caption("👆 说明：【红色字】= 原文错误；【^】= 此处缺失标点或文字。")

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


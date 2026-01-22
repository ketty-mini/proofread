import streamlit as st
from openai import OpenAI
import difflib

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="DeepSeek 智能纠错", page_icon="✍️")
st.title("DeepSeek 智能纠错助手")

# --- 2. 获取 API Key (云端保险箱模式) ---
# 优先从 Streamlit Secrets 读取
try:
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
    else:
        st.error("未检测到密钥！请在 Streamlit Cloud 后台 Secrets 中配置 DEEPSEEK_API_KEY。")
        st.stop()
except (FileNotFoundError, KeyError):
    # 本地运行如果没有配置 secrets.toml，会进这里
    st.warning("⚠️ 本地运行提示：未找到 .streamlit/secrets.toml 配置文件。")
    st.stop()

# --- 3. 初始化 DeepSeek 客户端 ---
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# --- 4. 界面逻辑 ---
# 左侧：说明区
with st.sidebar:
    st.markdown("### 🤖 关于本工具")
    st.info("本工具由 DeepSeek V3 模型驱动，能自动纠正中文错别字、语病并进行润色。")
    st.markdown("---")
    st.markdown("**使用说明：**\n1. 在右侧输入原文\n2. 点击“开始润色”\n3. 查看红绿对比结果")

# 主界面：输入区
original_text = st.text_area("请输入需要纠错的文章/段落：", height=200, placeholder="在这里粘贴你的文字...")

# --- 5. 核心处理逻辑 ---
if st.button("✨ 开始智能润色", type="primary"):
    if not original_text:
        st.warning("请先输入文字哦！")
    else:
        with st.spinner("AI 正在逐字推敲中..."):
            try:
                # 调用 DeepSeek API
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是一个专业的文字校对员。请纠正用户输入文本中的错别字和语病，保持原意不变。请直接输出修正后的文本，不要包含任何解释、开场白或结束语。"},
                        {"role": "user", "content": original_text},
                    ],
                    stream=False
                )
                corrected_text = response.choices[0].message.content.strip()

                # --- 6. 结果展示 (Diff 对比) ---
                st.success("润色完成！")
                
                # 使用 difflib 生成差异对比
                # 这里为了美观，我们简单处理：直接显示原文和修正文的对比
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📝 原文")
                    st.text(original_text)
                with col2:
                    st.subheader("✅ 修正后")
                    st.text(corrected_text)

                st.markdown("---")
                st.subheader("🔍 详细差异对比")
                
                # 生成红绿对比的 HTML
                def diff_strings(a, b):
                    output = []
                    s = difflib.SequenceMatcher(None, a, b)
                    for opcode, a0, a1, b0, b1 in s.get_opcodes():
                        if opcode == 'equal':
                            output.append(s.a[a0:a1])
                        elif opcode == 'insert':
                            output.append(f'<span style="background-color:#d4edda; color:#155724; padding:2px; border-radius:3px;">{s.b[b0:b1]}</span>')
                        elif opcode == 'delete':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; padding:2px; border-radius:3px;">{s.a[a0:a1]}</span>')
                        elif opcode == 'replace':
                            output.append(f'<span style="background-color:#f8d7da; color:#721c24; text-decoration:line-through; padding:2px; border-radius:3px;">{s.a[a0:a1]}</span>')
                            output.append(f'<span style="background-color:#d4edda; color:#155724; padding:2px; border-radius:3px;">{s.b[b0:b1]}</span>')
                    return "".join(output)

                diff_html = diff_strings(original_text, corrected_text)
                st.markdown(diff_html, unsafe_allow_html=True)

                # 纯文本复制区
                st.markdown("---")
                st.text_area("📋 复制修正后的纯文本：", value=corrected_text, height=150)

            except Exception as e:
                st.error(f"发生错误：{e}")
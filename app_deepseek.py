import streamlit as st
from PIL import Image
import pytesseract

# ==========================================
# 1. 页面配置与 CSS 优化
# ==========================================
st.set_page_config(page_title="AI 智能润色助手", page_icon="✍️", layout="centered")

# 初始化 session_state (用于在 OCR 和输入框之间传递文字)
if 'user_text' not in st.session_state:
    st.session_state['user_text'] = ""

# ==========================================
# 2. 核心处理函数 (你的 AI 逻辑放在这)
# ==========================================
def process_text(text, mode):
    """
    这里是连接 AI 模型的函数。
    请确保你已经初始化了 OpenAI 客户端 (client)。
    """
    
    # --- ⬇️ 请在这里配置你的 API Client ⬇️ ---
    # from openai import OpenAI
    # client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"]) 
    # 或者直接写死: client = OpenAI(api_key="sk-xxxx")
    
    # 模拟简单的 Prompt 逻辑 (请替换为你真实的 AI 调用代码)
    system_prompt = "You are a helpful assistant."
    user_prompt = ""
    
    if mode == "strict":
        user_prompt = f"请严格找出以下文本的错别字和语病，用红色标出，不要改写其他内容：\n{text}"
    elif mode == "fix":
        user_prompt = f"请修改以下文本的错别字和语病，保持原意不变：\n{text}"
    elif mode == "polish":
        user_prompt = f"请润色以下文本，使其更专业、优美：\n{text}"
    
    # ⚠️ 这里为了防止报错，我暂时写了一个假的返回。
    # 请把你原来代码里调用 client.chat.completions.create 的那段贴回来！
    # return response.choices[0].message.content
    
    # 临时测试用返回：
    import time
    time.sleep(1) # 假装在思考
    return f"【{mode} 模式执行成功】\n(这里应该显示 AI 的结果，请在代码中恢复 API 调用逻辑)\n\n处理原文：{text[:20]}..."

# ==========================================
# 3. 🖼️ OCR 图片文字识别区
# ==========================================
with st.expander("🖼️ 上传图片识别文字 / Upload Image OCR", expanded=True):
    uploaded_file = st.file_uploader("选择图片 (支持手写/打印)", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file is not None:
        # 手动按钮触发，防止死循环
        if st.button("🔍 开始识别图片中的文字", type="primary", key="ocr_btn"):
            try:
                with st.spinner("正在识别中 (支持中英文)..."):
                    image = Image.open(uploaded_file).convert('RGB')
                    # 核心：调用中文+英文库
                    text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                    
                    if text.strip():
                        st.session_state['user_text'] = text.strip()
                        st.success("✅ 识别成功！文字已填入下方输入框。")
                        st.rerun() # 刷新页面以更新输入框
                    else:
                        st.warning("⚠️ 未识别到有效文字，请尝试更清晰的图片。")
            except Exception as e:
                st.error(f"识别出错，请检查 packages.txt 是否包含 chi-sim。错误信息: {e}")

# ==========================================
# 4. 📝 文字输入区
# ==========================================
st.markdown("### 📝 输入内容 / Input Text")

# 绑定 session_state，这样 OCR 的结果会自动显示在这里
text_input = st.text_area(
    "请输入或粘贴文字：",
    value=st.session_state['user_text'],
    height=200,
    key="user_text_area",
    help="手动输入，或者使用上方图片识别自动填充"
)

# 每次手动输入改变时，更新 session_state
if text_input != st.session_state['user_text']:
    st.session_state['user_text'] = text_input

# ==========================================
# 5. 🎮 模式选择与执行 (你要的高亮变灰效果)
# ==========================================
st.divider()

# ✨ 关键组件：Segmented Control (胶囊菜单)
# 这就是你要的“点中变灰”效果
mode_selection = st.segmented_control(
    "请选择处理模式",
    options=["仅标红", "纠错", "润色"],
    selection_mode="single",
    default="润色",
    label_visibility="visible"
)

# 防止空选
if not mode_selection:
    mode_selection = "润色"

# 根据模式动态定义：按钮名字 & 提示语 & 内部参数
if mode_selection == "仅标红":
    btn_label = "🔍 开始查错 (Start Check)"
    instruction = "Strict Mode: 仅标红错别字与语病，绝不改写原意。"
    internal_mode = "strict"
elif mode_selection == "纠错":
    btn_label = "🚑 开始纠错 (Fix Errors)"
    instruction = "Fix Mode: 修改错别字，保持句子原意通顺。"
    internal_mode = "fix"
else: # 润色
    btn_label = "✨ 开始润色 (Polish Magic)"
    instruction = "Polish Mode: 深度优化用词与句式，提升文采。"
    internal_mode = "polish"

# 显示提示语
st.info(f"**当前模式:** {instruction}")

# ==========================================
# 6. 🚀 唯一的执行按钮
# ==========================================
if st.button(btn_label, type="primary", use_container_width=True):
    
    # 1. 检查有没有字
    if not st.session_state['user_text'].strip():
        st.warning("⚠️ 请先输入文字内容！")
        st.stop()
        
    # 2. 显示处理状态
    with st.spinner(f"AI 正在执行 {mode_selection}... 请稍候"):
        try:
            # 3. 调用 AI 函数
            result_text = process_text(st.session_state['user_text'], internal_mode)
            
            # 4. 显示结果
            st.markdown("### 🎯 处理结果 / Result")
            st.success("处理完成！")
            st.markdown(result_text)
            
        except Exception as e:
            st.error(f"运行出错: {e}")

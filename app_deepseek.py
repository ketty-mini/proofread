import streamlit as st
from openai import OpenAI
import difflib
from docx import Document
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn
from io import BytesIO
from PIL import Image
import pytesseract # 需安装 pip install pytesseract
import os
import shutil

# --- 0. Tesseract 路径强制修复 (针对云端) ---
if os.path.exists('/usr/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
else:
    possible_path = shutil.which("tesseract")
    if possible_path:
        pytesseract.pytesseract.tesseract_cmd = possible_path

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="Ketty's Mini Proofreading", 
    page_icon="✒️", 
    layout="centered"
)

# --- 2. CSS 样式 (已精简，去除了旧的 Radio Hack) ---
def local_css():
    st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
        font-family: "PingFang SC", "Microsoft YaHei", -apple-system, sans-serif;
    }
    .nav-title {
        font-size: 22px;
        font-weight: 700;
        color: #1a1a1a;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.5px;
    }
    .mode-desc {
        font-size: 14px;
        color: #666;
        margin-top: 10px;
        margin-bottom: 20px;
        padding-left: 10px;
        border-left: 3px solid #1a1a1a;
        line-height: 1.5;
        animation: fadeIn 0.6s ease;
    }
    /* === 输入框 === */
    .stTextArea textarea {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px;
        font-size: 16px;
        background-color: #fcfcfc;
        transition: all 0.2s;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.01);
    }
    .stTextArea textarea:focus {
        background-color: #ffffff;
        border-color: #1a1a1a;
        box-shadow: 0 0 0 3px rgba(0,0,0,0.05);
    }
    /* === 按钮 === */
    div.stButton > button {
        background-color: #1a1a1a;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 12px 24px;
        font-weight: 600;
        letter-spacing: 0.5px;
        width:

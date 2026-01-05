import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import io
import json
import zipfile
import base64
import time
import os

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="CONIC PDF RENAMER Pro",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS "ÉP" GIAO DIỆN TRẮNG TINH ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
    
    /* 1. ÉP BACKGROUND MÀU TRẮNG CHO TOÀN BỘ WEB */
    [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
    }
    [data-testid="stHeader"] {
        background-color: rgba(0,0,0,0) !important; /* Header trong suốt */
    }
    
    /* 2. ÉP MÀU CHỮ THÀNH ĐEN (Để không bị chữ trắng trên nền trắng) */
    h1, h2, h3, h4, h5, h6, p, span, div {
        color: #000000;
        font-family: 'Roboto', sans-serif;
    }
    
    /* 3. HEADER AREA */
    .header-container {
        display: flex;
        align-items: center;
        padding-bottom: 20px;
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 30px;
        background-color: #ffffff;
    }
    
    .logo-img {
        height: 65px;
        margin-right: 20px;
    }
    
    .title-box {
        display: flex;
        flex-direction: column;
    }
    
    .main-title {
        font-size: 1.8em;
        font-weight: 700;
        color: #000000 !important;
        line-height: 1.2;
    }
    
    .pro-tag {
        font-size: 0.5em;
        vertical-align: super;
        color: #555555 !important;
        font-weight: normal;
    }
    
    .sub-title {
        font-size: 1.1em;
        color: #333333 !important;
        margin-top: 5px;
    }
    
    /* 4. UPLOAD CARD (KHUNG TẢI HỒ SƠ) */
    .upload-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 30px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 30px;
    }
    
    .upload-header {
        font-size: 1.1em;
        font-weight: 600;
        color: #003366 !important;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Tùy chỉnh khung file uploader cho SÁNG MÀU */
    [data-testid="stFileUploader"] {
        padding: 20px;
        background-color: #ffffff; 
    }
    [data-testid="stFileUploader"] section {
        background-color: #f9f9f9 !important; /* Nền xám rất nhạt cho vùng kéo thả */
        border: 2px dashed #cccccc;
    }
    [data-testid="stFileUploader"] section > div {
        color: #333333 !important; /* Chữ hướng dẫn màu đen */
    }
    [data-testid="stFileUploader"] button {
        background-color: #ffffff;
        color: #333;
        border: 1px solid #ccc;
    }
    
    /* 5. NÚT BẤM (CENTER) */
    .stButton {
        text-align: center; 
        display: flex; 
        justify-content: center;
    }
    
    div.stButton > button {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
        border-radius: 5px;
        padding: 10px 40px;
        font-size: 1.1em;
        font-weight: 600;
        text-transform: uppercase;
        box-shadow: none;
        transition: all 0.3s;
    }
    
    div.stButton > button:hover {
        background-color: #000000 !important;
        color: #ffffff !important;
    }
    
    /* 6. INPUT API KEY */
    [data-testid="stTextInput"] label {
        color: #000000 !important;
    }
    [data-testid="stTextInput"] input {
        color: #000000 !important;
        background-color: #ffffff !important;
        border: 1px solid #ccc;
    }
    
    /* --- DASHBOARD RESULT STYLES --- */
    .list-header { font-weight: bold; color: #555 !important; margin-bottom: 10px; text-transform: uppercase; font-size: 0.85em; }
    
    .preview-box { background: #f9f9f9; border: 1px solid #eee; border-radius: 8px; padding: 10px; height: 500px; display: flex; align-items: center; justify-content: center; }
    .preview-img { max-height: 100%; max-width: 100%; object-fit: contain; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
    
    .result-panel { background: #fff; border: 1px solid #eee; border-radius: 8px; padding: 20px; height: 100%; box-shadow: 0 5px 15px rgba(0,0,0,0.05); }
    
    .conic-result-box {
        background-color: #f0f0f0;
        color: #d32f2f !important; /* Màu đỏ Conic */
        padding: 15px;
        border-radius: 5px;
        font-family: 'Consolas', monospace;
        font-weight: bold;
        border-left: 5px solid #d32f2f;
        margin-bottom: 20px;
        word-break: break-all;
    }
    
    .info-row { display: flex; justify-content: space-between; border-bottom: 1px solid #eee; padding: 8px 0; font-size: 0.9em; }
    .info-label { font-weight: bold; color: #777 !important; }
    .info-val { font-weight: 600; color: #333 !important; }

</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC BACKEND (GIỮ NGUYÊN) ---
if 'data' not in st.session_state: st.session_state.data = [] 
if 'selected_idx' not in st.session_state: st.session_state.selected_idx = 0 

def get_gemini_response(uploaded_file, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        uploaded_file.seek(0)
        
        # Prompt chuẩn
        prompt = """
        Phân tích ảnh văn bản và trả về JSON.
        
        1. QUY TẮC TÊN FILE (new_name):
           Cấu trúc: YYYY.MM.DD_LOAI_SoHieu_NoiDung_TrangThai.pdf
           - YYYY.MM.DD: Năm.Tháng.Ngày (Ví dụ 2025.12.31). Dấu CHẤM.
           - LOAI: Viết tắt (QD, TTr, CV, TB, GP, HD, BB, BC...).
           - SoHieu: Số hiệu (Ví dụ 125-UBND, thay / bằng -).
           - NoiDung: Tiếng Việt không dấu, nối gạch dưới (_).
           - TrangThai: 'Signed'.
           
        2. TRƯỜNG HIỂN THỊ (Tiếng Việt có dấu):
           - date: Ngày ký.
           - number: Số hiệu.
           - authority: Cơ quan ban hành.
           - summary: Trích yếu ngắn gọn.
           
        OUTPUT JSON: { "new_name": "...", "date": "...", "number": "...", "authority": "...", "summary": "..." }
        """
        image_part = {"mime_type": "image/png", "data": img_data}
        
        for _ in range(3):
            try:
                response = model.generate_content([prompt, image_part])
                txt = response.text.strip().replace("```json", "").replace("```", "")
                data = json.loads(txt)
                if not data['new_name'].lower().endswith(".pdf"): data['new_name'] += ".pdf"
                return data, img_base64
            except: time.sleep(1)
        return None, None
    except: return None, None

# --- 4. GIAO DIỆN HEADER & INPUT ---

# 4.1. LOGO & TITLE SECTION
col_head_1, col_head_2 = st.columns([3, 1])

with col_head_1:
    logo_base64 = ""
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f: logo_base64 = base64.b64encode(f.read()).decode()
    
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="logo-img">' if logo_base64 else ""
    
    st.markdown(f"""
    <div class="header-container">
        {logo_html}
        <div class="title-box">
            <div class="main-title">CONIC PDF RENAMER <span class="pro-tag">Pro</span></div>
            <div class="sub-title">Ban Đầu tư - Phát triển Dự án</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_head_2:
    api_key = st.text_input("Google API Key", type="password")

# 4.2. UPLOAD CARD (KHUNG TẢI HỒ SƠ)
st.markdown('<div class="upload-card">', unsafe_allow_html=True)
st.markdown('<div class="upload-header">☁️ Tải Hồ Sơ</div>', unsafe_allow_html=True)
uploaded_files = st.file_uploader("", type=['pdf'], accept_multiple_files=True, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

# 4.3. BUTTON CENTER
st.write("")
col_btn_1, col_btn_2, col_btn_3 = st.columns([1, 2, 1])
with col_btn_2:
    start_btn = st.button("BẮT ĐẦU ĐỔI TÊN")

# --- 5. LOGIC CHẠY ---
if start_btn:
    if not api_key: st.toast("⚠️ Vui lòng nhập API Key ở góc phải!")
    elif not uploaded_files: st.toast("⚠️ Vui lòng chọn file PDF!")
    else:
        st.session_state.data = []; st.session_state.selected_idx = 0
        bar = st.progress(0, text="Đang xử lý...")
        for i, f in enumerate(uploaded_files):
            meta, img = get_gemini_response(f, api_key)
            if meta:
                st.session_state.data.append({"original_name": f.name, "file_obj": f, "meta": meta, "img": img})
            bar.progress((i + 1) / len(uploaded_files))
        bar.empty(); st.success("✅ Đã xử lý xong!")

# --- 6. DASHBOARD RESULT ---
if st.session_state.data:
    st.markdown("---")
    
    c_list, c_view, c_res = st.columns([1, 1.5, 1.5])
    
    with c_list:
        st.markdown(f"<div class='list-header'>📂 DANH SÁCH FILE ({len(st.session_state.data)})</div>", unsafe_allow_html=True)
        for i, item in enumerate(st.session_state.data):
            label = f"{i+1}. {item['original_name']}"
            if len(label)>25: label = label[:22]+"..."
            if st.button(label, key=f"sel_{i}", use_container_width=True):
                st.session_state.selected_idx = i
                
    idx = st.session_state.selected_idx
    if idx >= len(st.session_state.data): idx=0
    curr = st.session_state.data[idx]; meta = curr['meta']
    
    with c_view:
        st.markdown("<div class='list-header'>👁️ XEM TRƯỚC</div>", unsafe_allow_html=True)
        st.markdown(f'<div class="preview-box"><img src="data:image/png;base64,{curr["img"]}" class="preview-img"></div>', unsafe_allow_html=True)
        
    with c_res:
        st.markdown("<div class='list-header'>✨ KẾT QUẢ</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="result-panel">
            <div style="font-size:0.8em; color:#777; margin-bottom:5px;">TÊN FILE ĐỀ XUẤT:</div>
            <div class="conic-result-box">{meta['new_name']}</div>
            
            <div class="info-row"><span class="info-label">Ngày BH:</span> <span class="info-val">{meta.get('date','-')}</span></div>
            <div class="info-row"><span class="info-label">Số hiệu:</span> <span class="info-val">{meta.get('number','-')}</span></div>
            <div class="info-row"><span class="info-label">Cơ quan:</span> <span class="info-val">{meta.get('authority','-')}</span></div>
            
            <div style="margin-top:15px;">
                <span class="info-label">Trích yếu:</span><br>
                <span style="font-style:italic; color:#333;">{meta.get('summary','-')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        curr['file_obj'].seek(0)
        st.download_button("⬇️ TẢI FILE NÀY", curr['file_obj'], meta['new_name'], "application/pdf", type="primary", use_container_width=True)

    st.markdown("---")
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        for item in st.session_state.data:
            item['file_obj'].seek(0); zf.writestr(item['meta']['new_name'], item['file_obj'].read())
    
    _, c_cen, _ = st.columns(3)
    with c_cen:
        st.download_button("📦 TẢI TRỌN BỘ (ZIP)", zip_buf.getvalue(), "Conic_Files.zip", "application/zip", use_container_width=True)

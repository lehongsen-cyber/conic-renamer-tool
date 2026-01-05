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

# --- 2. CSS "ÉP" GIAO DIỆN TRẮNG & NÚT 3D ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
    
    /* ÉP MÀU TRẮNG TUYỆT ĐỐI */
    [data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
    [data-testid="stHeader"] { background-color: rgba(0,0,0,0) !important; } /* Hiện lại Header nhưng trong suốt */
    
    /* FONT & MÀU CHỮ */
    h1, h2, h3, h4, h5, h6, p, span, div, label {
        color: #000000 !important;
        font-family: 'Roboto', sans-serif;
    }
    
    /* HEADER: BỎ ĐƯỜNG KẺ DƯỚI */
    .header-container {
        display: flex;
        align-items: center;
        padding-bottom: 10px;
        margin-bottom: 20px;
        /* border-bottom: 1px solid #e0e0e0; -> ĐÃ XÓA THEO YÊU CẦU */
        background-color: #ffffff;
    }
    
    .logo-img { height: 75px; margin-right: 25px; }
    
    .main-title {
        font-size: 2.2em;
        font-weight: 800;
        color: #000000 !important;
        line-height: 1.1;
        letter-spacing: -0.5px;
    }
    
    .pro-tag {
        font-size: 0.4em;
        vertical-align: top;
        color: #d32f2f !important; /* Màu đỏ Conic */
        font-weight: bold;
        margin-left: 5px;
    }
    
    .sub-title {
        font-size: 1.2em;
        color: #555555 !important;
        margin-top: 5px;
        font-weight: 500;
    }
    
    /* UPLOAD CARD: TINH GỌN, BỎ KHUNG THỪA */
    .upload-wrapper {
        margin-top: 20px;
        margin-bottom: 30px;
    }
    
    .upload-label {
        font-size: 1.1em;
        font-weight: 700;
        color: #003366 !important;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Tùy chỉnh khung file uploader Streamlit */
    [data-testid="stFileUploader"] {
        padding: 0px;
        background-color: #ffffff;
        border: none;
    }
    [data-testid="stFileUploader"] section {
        background-color: #f8f9fa !important;
        border: 2px dashed #d1d5db;
        border-radius: 15px;
        padding: 40px; /* Tăng padding cho rộng rãi */
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #d32f2f; /* Hover đỏ */
        background-color: #fff5f5 !important;
    }
    
    /* NÚT BẤM 3D (Ở GIỮA) */
    div.stButton {
        text-align: center;
        display: flex;
        justify-content: center;
    }
    
    div.stButton > button {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
        border-radius: 12px; /* Bo góc mềm hơn */
        padding: 15px 50px;
        font-size: 1.3em;
        font-weight: 800;
        text-transform: uppercase;
        
        /* HIỆU ỨNG 3D */
        box-shadow: 0 6px 0 #444444; /* Cái bóng dày */
        transform: translateY(0);
        transition: all 0.1s;
        margin-top: 10px;
    }
    
    div.stButton > button:hover {
        background-color: #000000 !important;
        color: #ffffff !important;
        border-color: #000000 !important;
        transform: translateY(2px); /* Nhún xuống xíu khi rê chuột */
        box-shadow: 0 4px 0 #444444;
    }
    
    div.stButton > button:active {
        transform: translateY(6px); /* Lún hẳn xuống khi bấm */
        box-shadow: 0 0 0 #444444; /* Mất bóng */
    }
    
    /* INPUT API KEY */
    [data-testid="stTextInput"] input {
        color: #000000 !important;
        background-color: #ffffff !important;
        border: 1px solid #ccc;
        border-radius: 8px;
    }
    
    /* KẾT QUẢ */
    .conic-result-box {
        background-color: #fff0f0;
        color: #d32f2f !important;
        padding: 15px;
        border-radius: 8px;
        font-family: 'Consolas', monospace;
        font-weight: bold;
        border-left: 5px solid #d32f2f;
        margin-bottom: 20px;
        word-break: break-all;
    }
    .preview-box { background: #fafafa; border: 1px solid #eee; border-radius: 10px; padding: 15px; height: 550px; display: flex; align-items: center; justify-content: center; }
    .preview-img { max-height: 100%; max-width: 100%; object-fit: contain; box-shadow: 0 8px 20px rgba(0,0,0,0.1); }
    
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC BACKEND ---
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

# --- 4. GIAO DIỆN CHÍNH ---

# 4.1. HEADER (LOGO + TITLE + API KEY)
# Chia làm 2 cột: 80% cho Logo/Title, 20% cho API Key
c_head, c_key = st.columns([4, 1.5])

with c_head:
    # Load Logo
    logo_base64 = ""
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f: logo_base64 = base64.b64encode(f.read()).decode()
    
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="logo-img">' if logo_base64 else ""
    
    st.markdown(f"""
    <div class="header-container">
        {logo_html}
        <div>
            <div class="main-title">CONIC PDF RENAMER<span class="pro-tag">PRO</span></div>
            <div class="sub-title">Ban Đầu tư - Phát triển Dự án</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with c_key:
    # API Key nằm gọn góc phải
    api_key = st.text_input("Google API Key", type="password")

# 4.2. UPLOAD SECTION (ĐÃ XÓA KHUNG CHỮ NHẬT THỪA)
# Bọc trong div wrapper để căn chỉnh
st.markdown('<div class="upload-wrapper">', unsafe_allow_html=True)
st.markdown('<div class="upload-label">☁️ Tải Hồ Sơ (Kéo thả file vào khung dưới)</div>', unsafe_allow_html=True)
uploaded_files = st.file_uploader("", type=['pdf'], accept_multiple_files=True, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

# 4.3. NÚT BẤM 3D (CĂN GIỮA TUYỆT ĐỐI)
# Dùng 3 cột tỷ lệ 1-1-1 để ép nút vào giữa
cb1, cb2, cb3 = st.columns([1, 1, 1])
with cb2:
    start_btn = st.button("BẮT ĐẦU ĐỔI TÊN")

# --- 5. LOGIC CHẠY ---
if start_btn:
    if not api_key: st.toast("⚠️ Nhập API Key đi sếp ơi!")
    elif not uploaded_files: st.toast("⚠️ Chưa có file nào hết!")
    else:
        st.session_state.data = []; st.session_state.selected_idx = 0
        bar = st.progress(0, text="Hệ thống đang xử lý...")
        for i, f in enumerate(uploaded_files):
            meta, img = get_gemini_response(f, api_key)
            if meta:
                st.session_state.data.append({"original_name": f.name, "file_obj": f, "meta": meta, "img": img})
            bar.progress((i + 1) / len(uploaded_files))
        bar.empty(); st.success("✅ Xong rồi! Mời sếp kiểm tra.")

# --- 6. DASHBOARD KẾT QUẢ ---
if st.session_state.data:
    st.markdown("---")
    
    c_list, c_view, c_res = st.columns([1, 1.5, 1.5])
    
    with c_list:
        st.markdown(f"**📂 DANH SÁCH ({len(st.session_state.data)})**")
        for i, item in enumerate(st.session_state.data):
            label = f"{i+1}. {item['original_name']}"
            if len(label)>25: label = label[:22]+"..."
            if st.button(label, key=f"sel_{i}", use_container_width=True):
                st.session_state.selected_idx = i
                
    idx = st.session_state.selected_idx
    if idx >= len(st.session_state.data): idx=0
    curr = st.session_state.data[idx]; meta = curr['meta']
    
    with c_view:
        st.markdown("**👁️ XEM TRƯỚC**")
        st.markdown(f'<div class="preview-box"><img src="data:image/png;base64,{curr["img"]}" class="preview-img"></div>', unsafe_allow_html=True)
        
    with c_res:
        st.markdown("**✨ KẾT QUẢ**")
        st.markdown(f"""
        <div style="background:#fff; padding:20px; border-radius:10px; border:1px solid #eee; box-shadow:0 4px 10px rgba(0,0,0,0.05);">
            <div style="font-size:0.8em; color:#999; margin-bottom:5px;">TÊN FILE ĐỀ XUẤT:</div>
            <div class="conic-result-box">{meta['new_name']}</div>
            
            <div style="display:flex; justify-content:space-between; margin-bottom:10px; border-bottom:1px solid #f0f0f0; padding-bottom:5px;">
                <span style="color:#777; font-weight:bold;">Ngày BH:</span> <span>{meta.get('date','-')}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:10px; border-bottom:1px solid #f0f0f0; padding-bottom:5px;">
                <span style="color:#777; font-weight:bold;">Số hiệu:</span> <span>{meta.get('number','-')}</span>
            </div>
            <div style="margin-bottom:15px;">
                <span style="color:#777; font-weight:bold;">Cơ quan:</span><br>
                <span>{meta.get('authority','-')}</span>
            </div>
             <div style="margin-bottom:15px;">
                <span style="color:#777; font-weight:bold;">Trích yếu:</span><br>
                <span style="font-style:italic;">{meta.get('summary','-')}</span>
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

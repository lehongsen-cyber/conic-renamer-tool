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
    page_title="Công ty Conic - Số Hóa Tài Liệu",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS CAO CẤP (GIAO DIỆN CONIC DASHBOARD) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    body {
        font-family: 'Inter', sans-serif;
        /* YÊU CẦU: Background màu trắng */
        background-color: #ffffff !important;
    }
    
    /* Ẩn Header mặc định */
    header[data-testid="stHeader"] {display: none;}
    
    /* HEADER CHÍNH CHO CONIC */
    .top-bar {
        background: white;
        padding: 15px 30px;
        border-bottom: 2px solid #0056b3; /* Viền xanh doanh nghiệp */
        display: flex;
        align-items: center;
        /* Thay đổi căn chỉnh để chứa Logo và Tên */
        justify-content: flex-start; 
        gap: 25px;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    /* Style cho Logo ảnh */
    .conic-logo-img {
        height: 70px; /* Chiều cao logo, chỉnh nếu cần */
        width: auto;
        object-fit: contain;
    }

    /* Style cho Tên ban */
    .conic-title {
        font-size: 1.6em;
        font-weight: 800;
        color: #0056b3; /* Màu xanh đậm chuyên nghiệp */
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* CÁC STYLE KHÁC GIỮ NGUYÊN TỪ TOOL CŨ */
    .list-header {
        font-weight: 700;
        color: #6b7280;
        margin-bottom: 10px;
        font-size: 0.85em;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    div.stButton > button {
        width: 100%;
        text-align: left;
        border: 1px solid #e5e7eb;
        background: white;
        color: #374151;
        padding: 10px 15px;
        border-radius: 8px;
        transition: all 0.2s;
        margin-bottom: 5px;
        font-size: 0.9em;
    }
    div.stButton > button:hover {
        border-color: #0056b3;
        color: #0056b3;
        background: #f0f7ff;
    }
    /* Nút chính màu xanh Conic */
    div.stButton > button[kind="primary"] {
        background: #0056b3;
        color: white;
        border: none;
        text-align: center;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #004494;
    }

    /* CỘT PREVIEW & RESULT (Nền trắng, viền nhẹ) */
    .preview-box, .result-panel {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
        height: 600px;
        border: 1px solid #e5e7eb;
    }
    .preview-box {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        padding: 15px;
    }
    .preview-img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* HỘP KẾT QUẢ (Màu xanh Conic thay vì tím) */
    .dark-box {
        background-color: #f8f9fa; /* Nền sáng nhẹ */
        color: #0056b3; /* Chữ xanh */
        padding: 20px;
        border-radius: 10px;
        margin-top: 10px;
        margin-bottom: 25px;
        font-family: 'Consolas', monospace;
        font-size: 1.1em;
        line-height: 1.4;
        border-left: 6px solid #0056b3;
        box-shadow: 0 5px 15px rgba(0, 86, 179, 0.15);
        word-break: break-all;
        font-weight: bold;
    }
    
    /* INFO GRID */
    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; }
    .info-item { background: #f9fafb; padding: 10px; border-radius: 8px; border: 1px solid #f3f4f6; }
    .info-label { font-size: 0.7em; text-transform: uppercase; color: #9ca3af; font-weight: 700; margin-bottom: 4px; }
    .info-value { font-size: 0.95em; color: #111827; font-weight: 600; }
    
    .footer-credit { position: fixed; bottom: 10px; right: 20px; font-size: 0.8em; color: #9ca3af; z-index: 999; }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC BACKEND (GIỮ NGUYÊN QUY TẮC CŨ) ---
if 'data' not in st.session_state:
    st.session_state.data = [] 
if 'selected_idx' not in st.session_state:
    st.session_state.selected_idx = 0 

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
        
        # PROMPT CŨ (YYYY.MM.DD)
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
           - date: Ngày ký (DD/MM/YYYY).
           - number: Số hiệu.
           - authority: Cơ quan ban hành.
           - summary: Trích yếu ngắn gọn.
           
        OUTPUT JSON: { "new_name": "...", "date": "...", "number": "...", "authority": "...", "summary": "..." }
        """
        
        image_part = {"mime_type": "image/png", "data": img_data}
        
        for _ in range(3):
            try:
                response = model.generate_content([prompt, image_part])
                txt = response.text.strip()
                if txt.startswith("```json"): txt = txt[7:]
                if txt.endswith("```"): txt = txt[:-3]
                data = json.loads(txt)
                if not data['new_name'].lower().endswith(".pdf"): data['new_name'] += ".pdf"
                return data, img_base64
            except:
                time.sleep(1)
        return None, None
    except:
        return None, None

# --- 4. GIAO DIỆN CHÍNH ---

# --- HEADER MỚI CHO CONIC ---
# Kiểm tra xem file logo có tồn tại không
logo_html = ""
if os.path.exists("logo.png"):
    # Đọc file ảnh và chuyển sang base64 để nhúng trực tiếp vào HTML
    with open("logo.png", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    logo_html = f'<img src="data:image/png;base64,{encoded_string}" class="conic-logo-img">'
elif os.path.exists("logo.jpg"): # Dự phòng nếu dùng file jpg
     with open("logo.jpg", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
     logo_html = f'<img src="data:image/jpeg;base64,{encoded_string}" class="conic-logo-img">'
else:
    # Placeholder nếu chưa upload logo
    logo_html = '<span style="font-size: 3em;">🏢</span>'

st.markdown(f"""
<div class="top-bar">
    {logo_html}
    <div class="conic-title">Ban Đầu tư - Phát triển Dự án Công ty Conic</div>
</div>
""", unsafe_allow_html=True)
# ---------------------------

# Input Area
with st.container():
    c1, c2, c3 = st.columns([1, 2, 0.5])
    with c1:
        api_key = st.text_input("🔑 API Key:", type="password")
    with c2:
        uploaded_files = st.file_uploader("Upload PDF", type=['pdf'], accept_multiple_files=True, label_visibility="collapsed")
    with c3:
        st.write("") 
        if st.button("🚀 BẮT ĐẦU", type="primary"):
            if not api_key: st.toast("⚠️ Thiếu API Key!")
            elif not uploaded_files: st.toast("⚠️ Chưa chọn file!")
            else:
                st.session_state.data = []; st.session_state.selected_idx = 0
                bar = st.progress(0, text="Đang khởi động...")
                for i, f in enumerate(uploaded_files):
                    meta, img = get_gemini_response(f, api_key)
                    if meta:
                        st.session_state.data.append({"original_name": f.name, "file_obj": f, "meta": meta, "img": img})
                    bar.progress((i + 1) / len(uploaded_files), text=f"Đang xử lý: {f.name}")
                bar.empty(); st.success("✅ Hoàn tất!")

# --- 5. DASHBOARD 3 CỘT ---
if st.session_state.data:
    st.divider()
    col_list, col_preview, col_detail = st.columns([1, 1.5, 1.5])
    
    with col_list:
        st.markdown(f"<div class='list-header'>📂 HÀNG CHỜ ({len(st.session_state.data)})</div>", unsafe_allow_html=True)
        for i, item in enumerate(st.session_state.data):
            label = f"{i+1}. {item['original_name']}"
            if len(label) > 30: label = label[:27] + "..."
            # Nút chọn file
            if st.button(label, key=f"sel_{i}", use_container_width=True):
                st.session_state.selected_idx = i
                
    idx = st.session_state.selected_idx; 
    if idx >= len(st.session_state.data): idx = 0
    curr = st.session_state.data[idx]; meta = curr['meta']
    
    with col_preview:
        st.markdown("<div class='list-header'>👁️ BẢN XEM TRƯỚC</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="preview-box"><img src="data:image/png;base64,{curr['img']}" class="preview-img"></div>""", unsafe_allow_html=True)
        
    with col_detail:
        st.markdown("<div class='list-header'>✨ KẾT QUẢ CHUẨN HÓA</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="result-panel">
            <div class="info-label" style="color:#0056b3;">TÊN FILE MỚI</div>
            <div class="dark-box">{meta['new_name']}</div>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">NGÀY BAN HÀNH</div><div class="info-value">{meta.get('date','...')}</div></div>
                <div class="info-item"><div class="info-label">SỐ HIỆU</div><div class="info-value">{meta.get('number','...')}</div></div>
            </div>
            <div class="info-item" style="margin-bottom:15px;"><div class="info-label">CƠ QUAN</div><div class="info-value">{meta.get('authority','...')}</div></div>
            <div class="info-item" style="margin-bottom:20px;"><div class="info-label">TRÍCH YẾU</div><div class="info-value" style="font-weight:400;">{meta.get('summary','...')}</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        curr['file_obj'].seek(0)
        st.download_button(label="⬇️ TẢI FILE NÀY", data=curr['file_obj'], file_name=meta['new_name'], mime="application/pdf", type="primary", use_container_width=True)

    st.divider()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for item in st.session_state.data:
            item['file_obj'].seek(0); zf.writestr(item['meta']['new_name'], item['file_obj'].read())
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2: st.download_button(label="📦 TẢI TRỌN BỘ (ZIP)", data=zip_buffer.getvalue(), file_name="Conic_Documents.zip", mime="application/zip", type="secondary", use_container_width=True)

else:
    st.markdown("""
    <div style="text-align: center; margin-top: 100px; color: #9ca3af; padding: 40px;">
        <div style="font-size: 4em; margin-bottom: 20px;">🏢</div>
        <h3>Hệ thống sẵn sàng</h3>
        <p>Vui lòng nhập Key và chọn file để bắt đầu số hóa.</p>
    </div>
    """, unsafe_allow_html=True)

# Footer (Có thể bỏ hoặc giữ lại tùy ý)
st.markdown('<div class="footer-credit">Internal System For Conic</div>', unsafe_allow_html=True)

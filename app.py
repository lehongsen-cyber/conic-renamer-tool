import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import io
import json
import zipfile
import base64
import time
import os
import textwrap

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="CONIC PDF RENAMER Pro",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS CHUẨN MEN (NÚT ĐỎ - NỀN TRẮNG) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
    
    /* 1. NỀN TRẮNG */
    [data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
    
    /* 2. ICON & HEADER */
    header[data-testid="stHeader"] { background-color: transparent !important; visibility: visible !important; }
    header[data-testid="stHeader"] * { color: #000000 !important; fill: #000000 !important; }
    
    /* FONT & MÀU */
    h1, h2, h3, h4, h5, h6, p, span, div, label { color: #000000 !important; font-family: 'Roboto', sans-serif; }
    
    /* HEADER */
    .header-container { display: flex; align-items: center; padding-bottom: 10px; margin-bottom: 20px; background-color: #ffffff; }
    .logo-img { height: 75px; margin-right: 25px; }
    .main-title { font-size: 2.2em; font-weight: 800; line-height: 1.1; letter-spacing: -0.5px; }
    .pro-tag { font-size: 0.4em; vertical-align: top; color: #d32f2f !important; font-weight: bold; margin-left: 5px; }
    .sub-title { font-size: 1.2em; color: #555555 !important; margin-top: 5px; font-weight: 500; }
    
    /* UPLOAD */
    .upload-wrapper { margin-top: 20px; margin-bottom: 30px; }
    .upload-label { font-size: 1.1em; font-weight: 700; color: #003366 !important; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
    [data-testid="stFileUploader"] { padding: 0px; border: none; background: white; }
    [data-testid="stFileUploader"] section { background-color: #f8f9fa !important; border: 2px dashed #d1d5db; border-radius: 12px; padding: 30px; }
    
    /* NÚT BROWSE FILES (ĐEN) */
    [data-testid="stFileUploader"] button {
        background-color: #000000 !important; color: #ffffff !important; border: 2px solid #000000 !important;
        opacity: 1 !important; font-weight: bold !important; padding: 8px 20px !important; width: auto !important;
    }
    
    /* --- PHÂN LOẠI NÚT BẤM --- */
    
    /* 1. NÚT 'BẮT ĐẦU' (Màu Trắng - Chữ Đen) - kind="secondary" */
    button[kind="secondary"] {
        background-color: #ffffff !important; color: #000000 !important; border: 2px solid #000000 !important;
        border-radius: 10px; font-size: 1.2em; font-weight: 800; text-transform: uppercase;
        box-shadow: 0 6px 0 #444444; margin-top: 10px; transition: all 0.1s;
    }
    button[kind="secondary"]:hover { transform: translateY(2px); box-shadow: 0 4px 0 #444444; background-color: #f5f5f5 !important; }
    button[kind="secondary"]:active { transform: translateY(6px); box-shadow: 0 0 0 #444444; }

    /* 2. NÚT 'TẢI VỀ' (Màu Đỏ - Chữ Trắng) - kind="primary" */
    button[kind="primary"] {
        background-color: #d32f2f !important; /* ĐỎ CONIC */
        color: #ffffff !important; border: none !important;
        border-radius: 8px; font-weight: bold; font-size: 1.1em;
        box-shadow: 0 4px 0 #8b0000; transition: all 0.1s;
    }
    button[kind="primary"]:hover { transform: translateY(2px); box-shadow: 0 2px 0 #8b0000; background-color: #b71c1c !important; }
    button[kind="primary"]:active { transform: translateY(4px); box-shadow: none; }
    
    /* INPUT KEY */
    [data-testid="stTextInput"] input { color: #000000 !important; background: #ffffff !important; border: 1px solid #ccc; border-radius: 8px; }
    
    /* KẾT QUẢ */
    .conic-result-box {
        background-color: #fff0f0; color: #d32f2f !important; padding: 15px; border-radius: 8px;
        font-family: 'Consolas', monospace; font-weight: bold; border-left: 5px solid #d32f2f;
        margin-bottom: 20px; word-break: break-all;
    }
    .preview-box { background: #fafafa; border: 1px solid #eee; border-radius: 10px; padding: 15px; height: 550px; display: flex; align-items: center; justify-content: center; }
    .preview-img { max-height: 100%; max-width: 100%; object-fit: contain; box-shadow: 0 8px 20px rgba(0,0,0,0.1); }
    
    /* LIST HEADER */
    .list-header { font-weight: bold; color: #555 !important; margin-bottom: 10px; text-transform: uppercase; font-size: 0.85em; }
    
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC XỬ LÝ ---
if 'data' not in st.session_state: st.session_state.data = [] 
if 'selected_idx' not in st.session_state: st.session_state.selected_idx = 0 

def get_best_model(api_key):
    genai.configure(api_key=api_key)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'gemini-1.5' in m.name: return m.name
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name: return m.name
    except: return None
    return "gemini-1.5-flash"

def get_gemini_response(uploaded_file, api_key, model_name):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        uploaded_file.seek(0)
        
        prompt = """
        Phân tích ảnh văn bản và trả về JSON.
        QUY TẮC: YYYY.MM.DD_LOAI_SoHieu_NoiDung_TrangThai.pdf
        OUTPUT JSON: { "new_name": "...", "date": "...", "number": "...", "authority": "...", "summary": "..." }
        """
        image_part = {"mime_type": "image/png", "data": img_data}
        
        for attempt in range(3):
            try:
                response = model.generate_content([prompt, image_part])
                txt = response.text.strip().replace("```json", "").replace("```", "")
                data = json.loads(txt)
                if not data['new_name'].lower().endswith(".pdf"): data['new_name'] += ".pdf"
                return data, img_base64, None
            except Exception as e:
                time.sleep(1)
                if attempt == 2: return None, None, str(e)
        return None, None, "Timeout"
    except Exception as e:
        return None, None, str(e)

# --- 4. GIAO DIỆN CHÍNH ---

c_head, c_key = st.columns([4, 1.5])
with c_head:
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
    api_key = st.text_input("Google API Key", type="password")

st.markdown('<div class="upload-wrapper">', unsafe_allow_html=True)
st.markdown('<div class="upload-label">☁️ Tải Hồ Sơ (Kéo thả file vào khung dưới)</div>', unsafe_allow_html=True)
uploaded_files = st.file_uploader("", type=['pdf'], accept_multiple_files=True, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

cb1, cb2, cb3 = st.columns([1, 1, 1])
with cb2:
    start_btn = st.button("BẮT ĐẦU ĐỔI TÊN", use_container_width=True, type="secondary")

# --- 5. LOGIC CHẠY ---
if start_btn:
    if not api_key: st.toast("⚠️ Nhập API Key đi sếp ơi!")
    elif not uploaded_files: st.toast("⚠️ Chưa có file nào hết!")
    else:
        active_model = get_best_model(api_key)
        if not active_model:
            st.error("❌ Key không hợp lệ hoặc không tìm thấy Model!")
        else:
            st.session_state.data = []; st.session_state.selected_idx = 0
            bar = st.progress(0, text=f"Đang xử lý bằng {active_model}...")
            errors = []
            for i, f in enumerate(uploaded_files):
                meta, img, err = get_gemini_response(f, api_key, active_model)
                if meta:
                    st.session_state.data.append({"original_name": f.name, "file_obj": f, "meta": meta, "img": img})
                else:
                    errors.append(f"{f.name}: {err}")
                bar.progress((i + 1) / len(uploaded_files))
            bar.empty()
            if st.session_state.data:
                st.success(f"✅ Đã xử lý {len(st.session_state.data)} hồ sơ!")
            if errors:
                for e in errors: st.error(e)

# --- 6. DASHBOARD KẾT QUẢ ---
if st.session_state.data:
    st.markdown("---")
    
    c_list, c_view, c_res = st.columns([1, 1.5, 1.5])
    
    with c_list:
        st.markdown(f"<div class='list-header'>📂 DANH SÁCH ({len(st.session_state.data)})</div>", unsafe_allow_html=True)
        for i, item in enumerate(st.session_state.data):
            label = f"{i+1}. {item['original_name']}"
            if len(label)>25: label = label[:22]+"..."
            # Nếu đang chọn -> primary (Đỏ), ngược lại secondary (Trắng)
            b_type = "primary" if i == st.session_state.selected_idx else "secondary"
            if st.button(label, key=f"sel_{i}", use_container_width=True, type=b_type):
                st.session_state.selected_idx = i
                st.rerun()
                
    idx = st.session_state.selected_idx
    if idx >= len(st.session_state.data): idx=0
    curr = st.session_state.data[idx]; meta = curr['meta']
    
    with c_view:
        st.markdown("<div class='list-header'>👁️ XEM TRƯỚC</div>", unsafe_allow_html=True)
        st.markdown(f'<div class="preview-box"><img src="data:image/png;base64,{curr["img"]}" class="preview-img"></div>', unsafe_allow_html=True)
        
    with c_res:
        st.markdown("<div class='list-header'>✨ KẾT QUẢ</div>", unsafe_allow_html=True)
        
        # HTML FIX: Loại bỏ thụt đầu dòng để tránh lỗi hiển thị code block
        html_content = f"""
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
"""
        st.markdown(html_content, unsafe_allow_html=True)
        
        st.write("")
        curr['file_obj'].seek(0)
        # Nút tải lẻ: Primary (Đỏ)
        st.download_button("⬇️ TẢI FILE NÀY", curr['file_obj'], meta['new_name'], "application/pdf", type="primary", use_container_width=True)

    st.markdown("---")
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        for item in st.session_state.data:
            item['file_obj'].seek(0); zf.writestr(item['meta']['new_name'], item['file_obj'].read())
    
    _, c_cen, _ = st.columns(3)
    with c_cen:
        # Nút tải ZIP: Primary (Đỏ) -> Sáng rực rỡ luôn!
        st.download_button("📦 TẢI TRỌN BỘ (ZIP)", zip_buf.getvalue(), "Conic_Files.zip", "application/zip", type="primary", use_container_width=True)

import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; color: black; }
    .code-box { font-size: 38px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 20px; border-radius: 12px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; margin: 15px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# --- 2. المحرك التقني المشترك ---

def get_pairing_code_and_store(m_id, m_token, phone):
    """يجلب الكود، يحفظه في الداتابيز، ويعيده للعرض الفوري"""
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    # تسجيل خروج لضمان طلب كود جديد
    requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/logout/{m_token}")
    time.sleep(1)
    
    url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            p_code = res.json().get('code')
            # الأمان: حفظ في الداتابيز
            supabase.table('merchants').update({"pairing_code": p_code}).eq("Phone", phone).execute()
            return p_code
    except: pass
    return None

# --- 3. إدارة الجلسة والدخول ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'last_p_code' not in st.session_state: st.session_state.last_p_code = None

if not st.session_state.logged_in:
    with st.form("login"):
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.rerun()
    st.stop()

# --- 4. واجهة التاجر ---
tabs = st.tabs(["➕ إضافة منتج", "🛒 الطلبات", "📲 واتساب"])

with tabs[0]:
    st.subheader("📦 إضافة منتج جديد")
    with st.form("add_product", clear_on_submit=True):
        p_name = st.text_input("اسم المنتج")
        p_id = st.text_input("رقم المنتج (Code)")
        p_price = st.text_input("سعر المنتج")
        p_img = st.file_uploader("رفع صورة المنتج", type=['jpg', 'png', 'jpeg'])
        if st.form_submit_button("حفظ المنتج"):
            supabase.table('products').insert({"Product": p_name, "Price": p_price, "Phone": st.session_state.merchant_phone}).execute()
            st.success("✅ تم الحفظ!")

with tabs[2]:
    st.subheader("📲 بوابة ربط الواتساب")
    curr_phone = st.session_state.merchant_phone
    
    # جلب الحالة "الآن" من الداتابيز
    m_res = supabase.table('merchants').select("*").eq("Phone", curr_phone).execute()
    m_data = m_res.data[0] if m_res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')
    db_code = m_data.get('pairing_code') # الكود المحفوظ

    if not m_id:
        st.warning("سيرفرك غير مفعل.")
    else:
        st.markdown(f"<div class='status-card'>✅ سيرفرك نشط برقم: <b>{m_id}</b></div>", unsafe_allow_html=True)
        
        if st.button("🔢 استخراج كود الربط"):
            with st.spinner("جاري جلب وحفظ الكود..."):
                code = get_pairing_code_and_store(m_id, m_token, curr_phone)
                if code:
                    st.session_state.last_p_code = code # للظهور الفوري
                    st.rerun()

        # عرض الكود (سواء القادم من الجلسة الحالية أو المحفوظ سابقاً)
        display_code = st.session_state.last_p_code or db_code
        if display_code:
            st.markdown(f"<div class='code-box'>{display_code}</div>", unsafe_allow_html=True)
            st.info(f"أدخل الكود في هاتفك المتصل بالرقم {curr_phone}")

    st.write("---")
    if st.button("🗑️ حذف وإعادة ضبط"):
        supabase.table('merchants').update({"instance_id": None, "api_token": None, "pairing_code": None}).eq("Phone", curr_phone).execute()
        st.session_state.last_p_code = None
        st.rerun()

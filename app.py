import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; color: black; }
    .code-box { font-size: 36px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 20px; border-radius: 10px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; margin: 15px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"⚠️ خطأ اتصال: {e}")

# --- 2. المحرك التقني المطور ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except: pass
    return None, None

def get_and_save_pairing_code(m_id, m_token, phone):
    """جلب الكود من Green-API وحفظه فوراً في Supabase"""
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    # تسجيل الخروج لضمان كود جديد
    requests.post(f"https://api.green-api.com/waInstance{m_id}/logout/{m_token}")
    
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            p_code = res.json().get('code')
            # حفظ الكود في عمود سأسميه pairing_code في جدولك
            supabase.table('merchants').update({"pairing_code": p_code}).eq("Phone", phone).execute()
            return p_code
    except: pass
    return None

# --- 3. الجلسة والدخول ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.form("login"):
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0].get('Store_name')
                st.rerun()
    st.stop()

# --- 4. واجهة التاجر ---
tabs = st.tabs(["➕ إضافة منتج", "🛒 طلبات", "📲 واتساب"])

with tabs[0]:
    st.subheader("📦 إضافة منتج")
    with st.form("add_p"):
        st.text_input("اسم المنتج")
        st.text_input("رقم المنتج")
        st.text_input("السعر")
        st.file_uploader("الصورة")
        st.form_submit_button("حفظ")

with tabs[2]:
    st.subheader("📲 بوابة الواتساب")
    curr_phone = st.session_state.merchant_phone
    
    # جلب البيانات "الآن" من الداتابيز
    m_res = supabase.table('merchants').select("*").eq("Phone", curr_phone).execute()
    m_data = m_res.data[0] if m_res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')
    saved_code = m_data.get('pairing_code') # جلب الكود المحفوظ

    if not m_id:
        if st.button("🚀 تفعيل السيرفر"):
            create_merchant_instance(curr_phone)
            st.rerun()
    else:
        st.markdown(f"<div class='status-card'>✅ السيرفر نشط (ID: {m_id})</div>", unsafe_allow_html=True)
        
        if st.button("🔢 استخراج كود الربط (8 أرقام)"):
            with st.spinner("جاري جلب الكود وحفظه..."):
                get_and_save_pairing_code(m_id, m_token, curr_phone)
                st.rerun() # إعادة التشغيل لعرض الكود المحفوظ

        # إظهار الكود من الداتابيز إذا كان موجوداً
        if saved_code:
            st.markdown(f"<div class='code-box'>{saved_code}</div>", unsafe_allow_html=True)
            st.info(f"أدخل الكود في هاتفك المتصل برقم: {curr_phone}")

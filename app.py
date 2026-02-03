import streamlit as st
import requests, time
from supabase import create_client

# 1. الإعدادات الرسمية
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
API_URL = "https://api.green-api.com"

# 2. اتصال Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- دالة تسجيل الدخول ---
def login_page():
    st.title("🔐 تسجيل الدخول - ريم ستور")
    with st.form("login_form"):
        u_phone = st.text_input("رقم الهاتف")
        u_pass = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            # البحث في الجدول باستخدام الأعمدة الصحيحة من صورتك
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pass).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.success("تم تسجيل الدخول بنجاح!")
                st.rerun()
            else:
                st.error("رقم الهاتف أو كلمة السر غير صحيحة")

# --- دالة بوابة الربط ---
def pairing_gate(phone):
    st.title("📲 بوابة الربط الاحترافية")
    
    # جلب البيانات باستخدام الأعمدة من صورتك: Merchant_nar و pairing_code
    res = supabase.table('merchants').select("*").eq("Phone", phone).execute()
    m_data = res.data[0] if res.data else {}
    
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')
    saved_code = m_data.get('pairing_code')

    if not m_id or m_id == "None":
        st.info("سيرفرك غير مفعل.") #
        if st.button("🚀 إنشاء وتفعيل السيرفر"):
            with st.spinner("جاري الإنشاء..."):
                c_res = requests.post(f"{API_URL}/partner/createInstance/{PARTNER_TOKEN}", json={"plan": "developer"})
                if c_res.status_code == 200:
                    d = c_res.json()
                    supabase.table('merchants').update({
                        "instance_id": str(d['idInstance']), 
                        "api_token": d['apiTokenInstance']
                    }).eq("Phone", phone).execute()
                    st.rerun()
    else:
        st.success(f"✅ سيرفرك الحالي: {m_id}")
        
        if st.button("🔢 اطلب كود الربط الرقمي"):
            with st.spinner("جاري جلب الكود من Green-API..."):
                # محاولة تنظيف الجلسة وطلب الكود
                requests.post(f"{API_URL}/waInstance{m_id}/logout/{m_token}")
                time.sleep(2)
                code_res = requests.post(f"{API_URL}/waInstance{m_id}/getPairingCode/{m_token}", json={"phoneNumber": phone})
                if code_res.status_code == 200:
                    code = code_res.json().get('code')
                    supabase.table('merchants').update({"pairing_code": code}).eq("Phone", phone).execute()
                    st.session_state.p_code = code
                    st.rerun()

        # عرض الكود
        display = st.session_state.get('p_code') or saved_code
        if display:
            st.markdown(f"<div style='text-align:center; background:#e3f2fd; padding:30px; border-radius:15px; border:3px dashed #2196f3;'><h1 style='font-size:60px; color:#075E54;'>{display}</h1></div>", unsafe_allow_html=True)
            st.info("أدخل الكود في هاتفك.")

# --- منطق تشغيل التطبيق ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    pairing_gate(st.session_state.merchant_phone)
    if st.sidebar.button("تسجيل خروج"):
        st.session_state.logged_in = False
        st.rerun()

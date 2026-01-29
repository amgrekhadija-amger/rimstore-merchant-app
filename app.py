import streamlit as st
import os
import requests
import base64
import time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات الثابتة ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

# تحميل الإعدادات
load_dotenv() 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# تعريف الاتصال بـ Supabase في البداية ليكون متاحاً لكل الكود
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ يرجى ضبط مفاتيح Supabase في البيئة (Env) أو Secrets")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 2. دالات Green-API الاحترافية ---

def create_merchant_instance(phone):
    """إنشاء مثيل جديد وحفظ بياناته في قاعدة البيانات"""
    url = f"https://api.green-api.com/partner/waInstance/create/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # تحديث أعمدة التاجر في Supabase (استخدام Phone كما في صورك)
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token,
                "session_status": "starting"
            }).eq("Phone", phone).execute()
            
            # ضبط الويب هوك
            setup_webhook(m_id, m_token)
            return m_id, m_token
    except:
        return None, None

def setup_webhook(m_id, m_token):
    url = f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {"webhookUrl": WEBHOOK_URL, "outgoingAPIMessage": "yes", "incomingMsg": "yes"}
    requests.post(url, json=payload, timeout=10)

def get_pairing_code(m_id, m_token, phone):
    """جلب الكود الرقمي للربط"""
    clean_phone = ''.join(filter(str.isdigit, phone))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except:
        return None

# --- 3. إدارة الجلسة وتسجيل الدخول ---

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    
    with tab_signup:
        with st.form("signup_form"):
            s_m_name = st.text_input("اسم التاجر")
            s_s_name = st.text_input("اسم المحل")
            s_phone = st.text_input("رقم واتساب التاجر")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                # الكود الخاص بك للتسجيل... (مختصر هنا للسرعة)
                supabase.table('merchants').insert({
                    "Merchant_name": s_m_name, "Store_name": s_s_name, 
                    "Phone": s_phone, "password": s_pass, "session_status": "disconnected"
                }).execute()
                st.success("✅ تم الإنشاء!")

    with tab_login:
        with st.form("login_form"):
            l_phone = st.text_input("رقم واتساب")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.session_state.store_name = res.data[0].get('Store_name')
                    st.rerun()
                else:
                    st.error("بيانات خاطئة")
else:
    # --- 4. واجهة المتجر الرئيسية ---
    st.title(f"🏪 متجر: {st.session_state.store_name}")
    
    # تعريف التبويبات هنا لضمان عدم حدوث NameError
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t1:
        st.write("إضافة منتجاتك هنا")
        # كود إضافة المنتجات الخاص بك...

    with t4:
        st.subheader("📲 بوابة ربط الواتساب (Green-API)")
        
        # جلب أحدث البيانات من السيرفر
        m_query = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        m_data = m_query.data[0] if m_query.data else {}
        
        inst_id = m_data.get('instance_id')
        inst_token = m_data.get('api_token')

        if not inst_id:
            st.warning("لم يتم تفعيل السيرفر بعد.")
            if st.button("🚀 تفعيل السيرفر المخصص"):
                with st.spinner("جاري الإنشاء..."):
                    new_id, new_token = create_merchant_instance(st.session_state.merchant_phone)
                    if new_id:
                        st.success("✅ تم الإنشاء!")
                        st.rerun()
        else:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔢 الحصول على كود الربط الرقمي"):
                    with st.spinner("جاري طلب الكود..."):
                        p_code = get_pairing_code(inst_id, inst_token, st.session_state.merchant_phone)
                        if p_code:
                            st.session_state.p_code_display = p_code
                
                if 'p_code_display' in st.session_state:
                    st.code(st.session_state.p_code_display, language="text")
                    st.info("أدخل الكود في هاتفك: الأجهزة المرتبطة > ربط جهاز > الربط برقم الهاتف")

            with col2:
                if st.button("🔍 فحص الحالة"):
                    status_url = f"https://api.green-api.com/waInstance{inst_id}/getStateInstance/{inst_token}"
                    state = requests.get(status_url).json().get('stateInstance')
                    st.metric("الحالة", state)
                    if state == 'authorized':
                        supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", st.session_state.merchant_phone).execute()

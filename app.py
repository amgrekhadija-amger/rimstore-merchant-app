import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- إعدادات الأمان وقراءة الملف من PythonAnywhere ---
load_dotenv() 
if not os.getenv("SUPABASE_URL"):
    home_env = os.path.expanduser('/home/rimstorebot/.env')
    load_dotenv(home_env)

# --- الإعدادات الثابتة ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ ملف .env غير موجود أو المفاتيح ناقصة.")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 1. دالة إنشاء Instance ---
def create_merchant_instance(phone):
    if not phone: return None, None
    url = f"https://api.greenapi.com/partner/createInstance/{PARTNER_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"plan": "developer"}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            if m_id and m_token:
                supabase.table('merchants').update({
                    "instance_id": m_id, 
                    "api_token": m_token
                }).eq("Phone", phone).execute()
                set_webhook_url(m_id, m_token)
                return m_id, m_token
        return None, None
    except: return None, None

# --- 2. دالة ضبط الويب هوك ---
def set_webhook_url(m_id, m_token):
    url = f"https://api.greenapi.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {"webhookUrl": WEBHOOK_URL, "outgoingAPIMessage": "yes", "incomingMsg": "yes"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

# --- 3. دالة جلب الرمز QR المحدثة ---
def get_green_qr(id_instance, api_token):
    if not id_instance or not api_token: return None
    url = f"https://api.greenapi.com/waInstance{id_instance}/qr/{api_token}"
    try:
        res = requests.get(url, timeout=20)
        if res.status_code == 200:
            return res.json() # يعيد {'type': 'qrCode', 'message': '...base64...'}
        elif res.status_code == 466:
            return {"type": "alreadyLoggedIn"}
    except: pass
    return None

# --- واجهة التطبيق (التصميم الأصلي) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # (بقيت شاشات الدخول كما هي دون تغيير لضمان عملها)
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    with tab_signup:
        with st.form("signup_form"):
            s_m_name = st.text_input("اسم التاجر")
            s_s_name = st.text_input("اسم المحل")
            s_phone = st.text_input("رقم واتساب التاجر")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                try:
                    check = supabase.table('merchants').select("Phone").eq("Phone", s_phone).execute()
                    if check.data: st.error("❌ الرقم مسجل مسبقاً!")
                    elif s_m_name and s_s_name and s_phone and s_pass:
                        supabase.table('merchants').insert({"Merchant_name": s_m_name, "Store_name": s_s_name, "Phone": s_phone, "password": s_pass}).execute()
                        st.success("✅ تم إنشاء الحساب!")
                except: st.error("حدث خطأ")

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
    st.title(f"🏪 لوحة تحكم: {st.session_state.store_name}")
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    # (Tabs 1, 2, 3 بقيت كما هي دون تغيير في التصميم)
    with t1:
        with st.form("add"):
            # ... كود إضافة المنتج ...
            pass
    with t2:
        # ... كود الإدارة ...
        pass
    with t3:
        # ... كود الطلبات ...
        pass

    with t4:
        st.subheader("📲 تفعيل وربط الواتساب")
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id:
            if st.button("🚀 تفعيل الآن"):
                with st.spinner("جاري إنشاء الحساب..."):
                    res_id, _ = create_merchant_instance(st.session_state.merchant_phone)
                    if res_id: st.rerun()
        else:
            col_qr, col_status = st.columns(2)
            with col_qr:
                st.write("### 1️⃣ ربط الجهاز")
                if st.button("🔄 توليد رمز QR الجديد"):
                    with st.spinner("جاري جلب الرمز..."):
                        qr_data = get_green_qr(m_id, m_token)
                        if qr_data:
                            if qr_data.get('type') == 'qrCode':
                                # التعديل المهم: فك تشفير الصورة وعرضها فوراً
                                qr_bytes = base64.b64decode(qr_data.get('message'))
                                st.image(qr_bytes, caption="امسح الرمز الآن بواتساب الهاتف", width=300)
                            elif qr_data.get('type') == 'alreadyLoggedIn':
                                st.success("✅ الجهاز مربوط بالفعل!")
                        else:
                            st.error("⚠️ فشل جلب الرمز. تأكد من رصيدك في حساب الشريك.")
            
            with col_status:
                st.write("### 2️⃣ الحالة")
                if st.button("🔍 فحص الاتصال"):
                    res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/getStateInstance/{m_token}").json()
                    st.metric("الحالة الحالية", res.get('stateInstance'))

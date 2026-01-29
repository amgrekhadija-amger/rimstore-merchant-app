import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- إعدادات الأمان وقراءة الملف ---
load_dotenv() 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# القيم التي حصلتِ عليها من تبويب "Account" في حساب الشريك
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com" 
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم خديجة المتطورة", layout="wide")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ مفاتيح Supabase ناقصة في ملف .env")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 1. دالة إنشاء Instance بناءً على التوثيق الجديد ---
def create_merchant_instance(phone):
    if not phone: return None, None
    
    # الرابط كما ورد في التوثيق: {{partnerApiUrl}}/partner/createInstance/{{partnerToken}}
    url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    
    try:
        # إرسال طلب الإنشاء (Method: POST)
        res = requests.post(url, timeout=30)
        
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            if m_id and m_token:
                # تحديث بيانات التاجر في Supabase
                supabase.table('merchants').update({
                    "instance_id": m_id, 
                    "api_token": m_token
                }).eq("Phone", phone).execute()
                
                # ضبط الإعدادات الموصى بها (Webhook)
                set_recommended_settings(m_id, m_token)
                return m_id, m_token
        else:
            st.error(f"خطأ من Green-API: {res.text}")
    except Exception as e:
        st.error(f"⚠️ عطل فني: {str(e)}")
    return None, None

# --- 2. دالة ضبط الإعدادات الموصى بها ---
def set_recommended_settings(m_id, m_token):
    url = f"{PARTNER_API_URL}/waInstance{m_id}/setSettings/{m_token}"
    payload = {
        "webhookUrl": WEBHOOK_URL,
        "outgoingAPIMessage": "yes",
        "incomingMsg": "yes",
        "deviceStatus": "yes"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

# --- 3. دالة جلب الرمز QR ---
def get_green_qr(m_id, m_token):
    url = f"{PARTNER_API_URL}/waInstance{m_id}/qr/{m_token}"
    try:
        res = requests.get(url, timeout=20)
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 466:
            return {"type": "alreadyLoggedIn"}
    except:
        pass
    return None

# --- واجهة التطبيق ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    t_login, t_signup = st.tabs(["🔐 دخول", "✨ حساب جديد"])
    
    with t_signup:
        with st.form("signup"):
            s_name = st.text_input("اسم التاجر")
            s_store = st.text_input("اسم المحل")
            s_phone = st.text_input("رقم الهاتف")
            s_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                try:
                    supabase.table('merchants').insert({
                        "Merchant_name": s_name, 
                        "Store_name": s_store, 
                        "Phone": s_phone, 
                        "password": s_pass
                    }).execute()
                    st.success("✅ تم التسجيل!")
                except:
                    st.error("فشل في التسجيل، تأكدي من إعدادات الجدول")

    with t_login:
        with st.form("login"):
            l_phone = st.text_input("رقم الهاتف")
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
    st.title(f"🏪 {st.session_state.store_name}")
    tab_whatsapp = st.tabs(["📲 ربط الواتساب"])[0]

    with tab_whatsapp:
        st.subheader("إعدادات الربط")
        m_res = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id or m_id == "None":
            if st.button("🚀 تفعيل المثيل (Create Instance)"):
                with st.spinner("جاري التواصل مع Green-API..."):
                    res_id, _ = create_merchant_instance(st.session_state.merchant_phone)
                    if res_id:
                        st.success("تم الإنشاء!")
                        st.rerun()
        else:
            st.info(f"Instance ID: {m_id}")
            if st.button("🔄 إظهار رمز QR للربط"):
                qr_data = get_green_qr(m_id, m_token)
                if qr_data:
                    if qr_data.get('type') == 'qrCode':
                        qr_bytes = base64.b64decode(qr_data.get('message'))
                        st.image(qr_bytes, caption="امسح الرمز بواتساب الهاتف")
                    elif qr_data.get('type') == 'alreadyLoggedIn':
                        st.success("الجهاز متصل بالفعل!")

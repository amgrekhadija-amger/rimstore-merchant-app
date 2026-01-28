import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- 1. الإعدادات الثابتة (تأكدي من صحتها من حسابك) ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com" 
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر - khadija", layout="wide")

# --- 2. الاتصال بـ Supabase ---
load_dotenv() 
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ يرجى ضبط مفاتيح Supabase في Secrets")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 3. الدوال البرمجية (Logic) ---

def set_webhook_url(m_id, m_token):
    """ضبط الويب هوك لاستقبال الرسائل"""
    url = f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {
        "webhookUrl": WEBHOOK_URL, 
        "outgoingAPIMessage": "yes", 
        "incomingMsg": "yes",
        "deviceStatus": "yes"
    }
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def create_merchant_instance(phone):
    """إنشاء Instance جديد للتاجر وحفظه فوراً"""
    url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            if m_id and m_token:
                # تحديث قاعدة البيانات والتأكد من نجاح العملية
                update_res = supabase.table('merchants').update({
                    "instance_id": m_id, 
                    "api_token": m_token
                }).eq("Phone", phone).execute()
                
                if len(update_res.data) > 0:
                    set_webhook_url(m_id, m_token)
                    return m_id, m_token
                else:
                    st.error(f"❌ فشل تحديث السجل. تأكد من وجود الرقم {phone} في جدول التجار.")
            else:
                st.error("⚠️ البيانات العائدة من Green-API ناقصة.")
        else:
            st.error(f"❌ خطأ Partner API: {res.status_code} - {res.text}")
    except Exception as e:
        st.error(f"⚠️ خطأ تقني: {str(e)}")
    return None, None

def get_pairing_code(id_instance, api_token, phone):
    """جلب كود الربط المكون من 8 أرقام"""
    clean_phone = ''.join(filter(str.isdigit, phone))
    url = f"https://api.green-api.com/waInstance{id_instance}/getPairingCode/{api_token}?phoneNumber={clean_phone}"
    try:
        res = requests.get(url, timeout=20)
        if res.status_code == 200: return res.json()
        elif res.status_code == 466: return {"type": "alreadyLoggedIn"}
    except: pass
    return None

# --- 4. واجهة التطبيق (UI) ---

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 دخول", "✨ تسجيل جديد"])
    with tab_signup:
        with st.form("signup"):
            s_m_name = st.text_input("اسم التاجر")
            s_phone = st.text_input("رقم الهاتف (مثال: 222000000)")
            s_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء حساب"):
                supabase.table('merchants').insert({
                    "Merchant_name": s_m_name, "Phone": s_phone, 
                    "password": s_pass, "session_status": "disconnected"
                }).execute()
                st.success("✅ تم التسجيل!")

    with tab_login:
        with st.form("login"):
            l_phone = st.text_input("رقم الهاتف")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.rerun()
                else: st.error("بيانات خاطئة")
else:
    # لوحة التحكم بعد تسجيل الدخول
    st.sidebar.write(f"مرحباً: {st.session_state.merchant_phone}")
    if st.sidebar.button("🚪 خروج"):
        st.session_state.logged_in = False
        st.rerun()

    t1, t2, t3, t4 = st.tabs(["➕ منتج جديد", "📦 الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    # (أقسام t1, t2, t3 تبقى كما هي في كودك الأصلي)

    with t4:
        st.subheader("📲 إعدادات بوت الواتساب")
        
        # جلب البيانات الحالية من Supabase
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id or m_id == "None":
            st.warning("⚠️ حساب الواتساب غير مفعل حالياً.")
            if st.button("🚀 تفعيل حسابي الآن"):
                with st.spinner("جاري إنشاء المثيل وحفظ البيانات..."):
                    new_id, new_token = create_merchant_instance(st.session_state.merchant_phone)
                    if new_id:
                        st.success("✅ تم الحفظ! جاري تحديث الصفحة...")
                        time.sleep(1)
                        st.rerun()
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                st.info(f"ID المثيل: {m_id}")
                if st.button("🔢 جلب كود الربط (8 أرقام)"):
                    p_data = get_pairing_code(m_id, m_token, st.session_state.merchant_phone)
                    if p_data and 'code' in p_data:
                        st.session_state.p_code = p_data['code']
                    elif p_data and p_data.get('type') == 'alreadyLoggedIn':
                        st.success("✅ متصل بالفعل!")
                
                if 'p_code' in st.session_state:
                    st.success(f"كود الربط الخاص بك: **{st.session_state.p_code}**")
                    st.write("افتح واتساب > الأجهزة المرتبطة > ربط جهاز > الربط برقم الهاتف")

            with col_b:
                if st.button("🔍 فحص الحالة"):
                    res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}").json()
                    st.metric("الحالة", res.get('stateInstance', 'unknown'))

                if st.button("🗑️ إعادة ضبط"):
                    if st.checkbox("أؤكد حذف بيانات الربط الحالية"):
                        supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", st.session_state.merchant_phone).execute()
                        st.rerun()

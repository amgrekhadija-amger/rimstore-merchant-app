import streamlit as st
import os
import requests
import base64
import time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات الأساسية ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

load_dotenv() 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ يرجى ضبط مفاتيح Supabase في الإعدادات (Secrets)!")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 2. الدالات (Functions) ---

def create_merchant_instance(phone):
    """إنشاء Instance جديد مع الكشف الدقيق عن أسباب الفشل"""
    if not phone:
        return None, None
    url = f"https://api.green-api.com/partner/waInstance/create/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        
        # في حال النجاح
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token,
                "session_status": "starting"
            }).eq("Phone", phone).execute()
            
            setup_webhook(m_id, m_token)
            return m_id, m_token
        
        # في حال الفشل (تعديل كشف السبب)
        else:
            try:
                error_info = res.json().get('message', 'خطأ غير معروف من السيرفر')
            except:
                error_info = res.text
            st.error(f"❌ رد Green-API: {error_info} (كود: {res.status_code})")
            return None, None
            
    except Exception as e:
        st.error(f"⚠️ خطأ تقني في الاتصال: {str(e)}")
        return None, None

def setup_webhook(m_id, m_token):
    url = f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {"webhookUrl": WEBHOOK_URL, "outgoingAPIMessage": "yes", "incomingMsg": "yes"}
    requests.post(url, json=payload, timeout=10)

def get_pairing_code(m_id, m_token, phone):
    if not phone or not m_id: return None
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except:
        return None

# --- 3. نظام تسجيل الدخول ---

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    t_login, t_signup = st.tabs(["🔐 دخول", "✨ حساب جديد"])
    with t_signup:
        with st.form("signup"):
            name = st.text_input("الاسم")
            store = st.text_input("المحل")
            phone = st.text_input("الهاتف")
            pw = st.text_input("السر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                supabase.table('merchants').insert({
                    "Merchant_name": name, "Store_name": store, 
                    "Phone": phone, "password": pw
                }).execute()
                st.success("✅ تم التسجيل! انتقل لتبويب الدخول.")

    with t_login:
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
                else: 
                    st.error("❌ بيانات الدخول غير صحيحة")

else:
    # --- 4. واجهة المتجر الرئيسية ---
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

    t1, t2, t3, t4 = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

    with t4:
        st.subheader("📲 ربط الواتساب (Green-API Partner)")
        current_phone = st.session_state.get('merchant_phone')
        
        if current_phone:
            # جلب بيانات التاجر الحالية
            m_query = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
            m_data = m_query.data[0] if m_query.data else {}
            m_id = m_data.get('instance_id')
            m_token = m_data.get('api_token')

            if not m_id:
                if st.button("🚀 تفعيل السيرفر المخصص"):
                    with st.spinner("جاري التواصل مع Green-API..."):
                        # استدعاء الدالة المعدلة التي تكشف سبب الخطأ
                        result = create_merchant_instance(current_phone)
                        if result and result[0]:
                            st.success("✅ تم تفعيل السيرفر!")
                            st.rerun()
            else:
                st.info(f"معرف السيرفر النشط: `{m_id}`")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🔢 طلب كود الربط"):
                        with st.spinner("جاري طلب الكود..."):
                            code = get_pairing_code(m_id, m_token, current_phone)
                            if code:
                                st.session_state['pairing_code'] = code
                                st.rerun()
                    
                    if 'pairing_code' in st.session_state:
                        st.success(f"كود الربط: **{st.session_state['pairing_code']}**")
                        st.info("افتح الواتساب > الأجهزة المرتبطة > ربط برقم هاتف")

                with c2:
                    if st.button("🔍 فحص حالة الاتصال"):
                        if m_id and m_token:
                            url = f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}"
                            try:
                                response = requests.get(url, timeout=10)
                                state = response.json().get('stateInstance')
                                st.metric("الحالة", state)
                                if state == 'authorized':
                                    supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", current_phone).execute()
                                    st.success("✅ الهاتف متصل!")
                            except:
                                st.error("⚠️ تعذر جلب الحالة حالياً")
                
                st.write("---")
                if st.button("🗑️ حذف البيانات وإعادة البدء"):
                    supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", current_phone).execute()
                    st.session_state.pop('pairing_code', None)
                    st.rerun()

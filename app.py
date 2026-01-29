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
        st.error("⚠️ يرجى ضبط مفاتيح Supabase في الإعدادات!")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في قاعدة البيانات: {e}")
    st.stop()

# --- 2. الدالات (Functions) ---

def create_merchant_instance(phone):
    if not phone: return None, None
    url = f"https://api.green-api.com/partner/waInstance/create/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
            supabase.table('merchants').update({
                "instance_id": m_id, "api_token": m_token, "session_status": "starting"
            }).eq("Phone", phone).execute()
            setup_webhook(m_id, m_token)
            return m_id, m_token
    except: return None, None

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
        if res.status_code == 200: return res.json().get('code')
    except: return None

# --- 3. نظام تسجيل الدخول ---

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    t_login, t_signup = st.tabs(["🔐 دخول", "✨ حساب جديد"])
    with t_signup:
        with st.form("signup"):
            name, store, phone, pw = st.text_input("الاسم"), st.text_input("المحل"), st.text_input("الهاتف"), st.text_input("السر", type="password")
            if st.form_submit_button("إنشاء"):
                supabase.table('merchants').insert({"Merchant_name": name, "Store_name": store, "Phone": phone, "password": pw}).execute()
                st.success("تم!")

    with t_login:
        with st.form("login"):
            u_phone, u_pw = st.text_input("رقم الهاتف"), st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = u_phone
                    st.session_state.store_name = res.data[0].get('Store_name')
                    st.rerun()
                else: st.error("خطأ!")

else:
    # --- 4. واجهة المتجر الرئيسية ---
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

    t1, t2, t3, t4 = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

    with t1:
        st.subheader("إضافة منتج")
        with st.form("add_p"):
            p_name, p_price, p_img = st.text_input("الاسم"), st.text_input("السعر"), st.file_uploader("الصورة")
            if st.form_submit_button("حفظ"):
                img = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                supabase.table('products').insert({"Product": p_name, "Price": p_price, "Image_url": img, "Phone": st.session_state.merchant_phone}).execute()
                st.success("تم!")

    with t4:
        st.subheader("📲 ربط الواتساب")
        current_phone = st.session_state.get('merchant_phone')
        
        if current_phone:
            m_query = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
            m_data = m_query.data[0] if m_query.data else {}
            m_id, m_token = m_data.get('instance_id'), m_data.get('api_token')

            if not m_id:
                if st.button("🚀 تفعيل السيرفر"):
                    with st.spinner("انتظري قليلاً..."):
                        mid, mtk = create_merchant_instance(current_phone)
                        if mid: st.rerun()
            else:
                st.success(f"معرف السيرفر الخاص بك: {m_id}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🔢 طلب كود الربط"):
                        code = get_pairing_code(m_id, m_token, current_phone)
                        if code:
                            st.session_state['pairing_code'] = code
                            st.rerun()
                    if 'pairing_code' in st.session_state:
                        st.code(st.session_state['pairing_code'], language="text")
                        st.info("أدخلي الكود في واتساب الهاتف")

                with c2:
                    # التعديل الأمني هنا: التحقق من وجود m_id و m_token قبل بناء الرابط
                    if st.button("🔍 فحص الاتصال"):
                        if m_id and m_token:
                            try:
                                url = f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}"
                                response = requests.get(url, timeout=10)
                                if response.status_code == 200:
                                    state = response.json().get('stateInstance')
                                    st.write(f"الحالة: {state}")
                                    if state == 'authorized':
                                        supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", current_phone).execute()
                                        st.success("✅ متصل!")
                                else: st.error("فشل الاتصال بالسيرفر")
                            except: st.error("حدث خطأ أثناء المحاولة")
                        else: st.warning("⚠️ بيانات الربط غير مكتملة.")
                
                if st.button("🗑️ حذف السيرفر والبدء من جديد"):
                    supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", current_phone).execute()
                    st.session_state.pop('pairing_code', None)
                    st.rerun()

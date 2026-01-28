import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- إعدادات الأمان (PythonAnywhere) ---
load_dotenv() 
if not os.getenv("SUPABASE_URL"):
    home_env = os.path.expanduser('/home/rimstorebot/.env')
    load_dotenv(home_env)

# --- الإعدادات الثابتة المستخرجة من حساب الشريك ---
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ مفاتيح Supabase غير موجودة في ملف .env بالسيرفر.")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في قاعدة البيانات: {e}")
    st.stop()

# --- 1. دالة إنشاء Instance (تطبيق نصيحة الفريق التقني) ---
def create_merchant_instance(phone):
    if not phone: return None, None
    
    # الرابط الجديد المعتمد: التوكن داخل الرابط مباشرة
    url = f"https://api.greenapi.com/partner/createInstance/{PARTNER_TOKEN}"
    
    # الجسم (Body) حسب التوصيات
    payload = {"plan": "developer"}
    headers = {"Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            if m_id and m_token:
                # حفظ البيانات فوراً في قاعدة البيانات
                supabase.table('merchants').update({
                    "instance_id": m_id, 
                    "api_token": m_token
                }).eq("Phone", phone).execute()
                
                # ضبط الإعدادات والويب هوك للمثيل الجديد
                setup_url = f"https://api.greenapi.com/waInstance{m_id}/setSettings/{m_token}"
                requests.post(setup_url, json={
                    "webhookUrl": WEBHOOK_URL,
                    "outgoingAPIMessage": "yes",
                    "incomingMsg": "yes"
                }, timeout=10)
                
                return m_id, m_token
        st.error(f"❌ فشل إنشاء المثيل: {res.text}")
        return None, None
    except Exception as e:
        st.error(f"⚠️ خطأ في الاتصال: {e}")
        return None, None

# --- 2. دالة جلب الرمز QR ---
def get_green_qr(id_instance, api_token):
    url = f"https://api.greenapi.com/waInstance{id_instance}/qr/{api_token}"
    try:
        res = requests.get(url, timeout=20)
        if res.status_code == 200:
            return res.json() 
        elif res.status_code == 466:
            return {"type": "alreadyLoggedIn"}
    except: pass
    return None

# --- واجهة التطبيق (التصميم الأصلي دون تغيير) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    with tab_signup:
        with st.form("signup"):
            s_m_name = st.text_input("اسم التاجر")
            s_s_name = st.text_input("اسم المحل")
            s_phone = st.text_input("رقم واتساب التاجر")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                supabase.table('merchants').insert({"Merchant_name": s_m_name, "Store_name": s_s_name, "Phone": s_phone, "password": s_pass}).execute()
                st.success("✅ تم الإنشاء!")

    with tab_login:
        with st.form("login"):
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

    with t1:
        with st.form("add_p"):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر")
            p_img = st.file_uploader("صورة المنتج")
            if st.form_submit_button("حفظ"):
                img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                supabase.table('products').insert({"Product": p_name, "Price": p_price, "Image_url": img_data, "Phone": st.session_state.merchant_phone}).execute()
                st.success("تم!")

    with t2:
        prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        for p in prods.data:
            st.write(f"📦 {p['Product']} - {p['Price']} MRU")

    with t3:
        orders = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        for o in orders.data: st.info(f"طلب من: {o['customer_phone']}")

    with t4:
        st.subheader("📲 تفعيل وربط الواتساب")
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id:
            if st.button("🚀 تفعيل الآن"):
                with st.spinner("جاري إنشاء المثيل بنظام الشريك..."):
                    m_id, m_token = create_merchant_instance(st.session_state.merchant_phone)
                    if m_id: st.rerun()
        else:
            col_qr, col_status = st.columns(2)
            with col_qr:
                if st.button("🔄 توليد رمز QR للربط"):
                    with st.spinner("جاري جلب الرمز..."):
                        qr_data = get_green_qr(m_id, m_token)
                        if qr_data:
                            if qr_data.get('type') == 'qrCode':
                                st.session_state.current_qr = qr_data.get('message')
                            elif qr_data.get('type') == 'alreadyLoggedIn':
                                st.success("✅ مربوط بالفعل!")
                        else: st.error("فشل جلب الرمز.")
                
                if 'current_qr' in st.session_state and st.session_state.current_qr:
                    st.image(base64.b64decode(st.session_state.current_qr), width=300)

            with col_status:
                if st.button("🔍 فحص الحالة"):
                    res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/getStateInstance/{m_token}").json()
                    st.metric("الحالة", res.get('stateInstance'))


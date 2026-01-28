import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- إعدادات الأمان وقراءة الملف من PythonAnywhere ---
# الكود سيبحث عن .env في المجلد الحالي، وإذا لم يجده سيبحث في المجلد الرئيسي للسيرفر
load_dotenv() 
if not os.getenv("SUPABASE_URL"):
    # استبدلي 'rimstorebot' باسم المستخدم الخاص بك في PythonAnywhere إذا كان مختلفاً
    home_env = os.path.expanduser('/home/rimstorebot/.env')
    load_dotenv(home_env)

# --- الإعدادات الثابتة ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

# جلب البيانات (الآن أصبحت آمنة في سيرفر PythonAnywhere فقط)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ ملف .env غير موجود في السيرفر. يرجى التأكد من رفعه في /home/rimstorebot/")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 1. دالة إنشاء Instance (الرابط المعتمد لتفادي 403) ---
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
        st.error(f"❌ فشل الإنشاء: {res.text}")
        return None, None
    except Exception as e:
        st.error(f"⚠️ خطأ تقني: {str(e)}")
        return None, None

# --- 2. دالة ضبط الويب هوك ---
def set_webhook_url(m_id, m_token):
    url = f"https://api.greenapi.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {
        "webhookUrl": WEBHOOK_URL, 
        "outgoingAPIMessage": "yes", 
        "incomingMsg": "yes",
        "deviceStatus": "yes"
    }
    try: requests.post(url, json=payload, timeout=10)
    except: pass

# --- 3. دالة جلب الرمز QR ---
def get_green_qr(id_instance, api_token):
    if not id_instance or not api_token: return None
    url = f"https://api.greenapi.com/waInstance{id_instance}/qr/{api_token}"
    try:
        res = requests.get(url, timeout=20)
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 466:
            return {"type": "alreadyLoggedIn"}
        return None
    except: return None

# --- واجهة التطبيق (التصميم الأصلي كما طلبتِ) ---
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
                try:
                    check = supabase.table('merchants').select("Phone").eq("Phone", s_phone).execute()
                    if check.data: st.error("❌ الرقم مسجل مسبقاً!")
                    elif s_m_name and s_s_name and s_phone and s_pass:
                        supabase.table('merchants').insert({
                            "Merchant_name": s_m_name, "Store_name": s_s_name, 
                            "Phone": s_phone, "password": s_pass, "session_status": "disconnected"
                        }).execute()
                        st.success("✅ تم إنشاء الحساب!")
                except: st.error("حدث خطأ في التسجيل")

    with tab_login:
        with st.form("login_form"):
            l_phone = st.text_input("رقم واتساب")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                try:
                    res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                    if res.data:
                        st.session_state.logged_in = True
                        st.session_state.merchant_phone = l_phone
                        st.session_state.store_name = res.data[0].get('Store_name')
                        st.rerun()
                    else: st.error("بيانات الدخول غير صحيحة")
                except: st.error("فشل الاتصال")
else:
    st.title(f"🏪 لوحة تحكم: {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل الخروج"):
        st.session_state.logged_in = False
        st.rerun()

    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t1:
        with st.form("add_product", clear_on_submit=True):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر")
            p_size = st.text_input("المقاس")
            p_color = st.text_input("اللون")
            p_img = st.file_uploader("صورة المنتج", type=['png','jpg'])
            if st.form_submit_button("حفظ المنتج"):
                try:
                    img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                    supabase.table('products').insert({"Product": p_name, "Price": p_price, "Size": p_size, "Color": p_color, "Image_url": img_data, "Phone": st.session_state.merchant_phone}).execute()
                    st.success("✅ تم حفظ المنتج!")
                except: st.error("فشل الحفظ")

    with t2:
        st.subheader("📦 إدارة المنتجات")
        prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        for p in prods.data:
            col1, col2 = st.columns([5, 1])
            col1.write(f"**{p['Product']}** | {p['Price']} MRU")
            if col2.button("🗑️", key=f"del_{p['id']}"):
                supabase.table('products').delete().eq("id", p['id']).execute()
                st.rerun()

    with t3:
        st.subheader("🛒 سجل الطلبات")
        orders = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        for o in orders.data: st.info(f"📦 طلب من: {o['customer_phone']} | {o['product_name']}")

    with t4:
        st.subheader("📲 تفعيل وربط الواتساب")
        
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id:
            st.warning("⚠️ الخدمة غير مفعلة.")
            if st.button("🚀 تفعيل الآن"):
                with st.spinner("جاري إنشاء الحساب..."):
                    res_id, _ = create_merchant_instance(st.session_state.merchant_phone)
                    if res_id:
                        st.success("✅ تم التفعيل!")
                        time.sleep(1)
                        st.rerun()
        else:
            col_qr, col_status = st.columns(2)
            with col_qr:
                if st.button("🔄 توليد رمز QR"):
                    qr_data = get_green_qr(m_id, m_token)
                    if qr_data and qr_data.get('type') == 'qrCode':
                        st.session_state.qr_img = qr_data.get('message')
                if 'qr_img' in st.session_state:
                    st.image(base64.b64decode(st.session_state.qr_img), width=300)
            
            with col_status:
                if st.button("🔍 فحص الاتصال"):
                    res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/getStateInstance/{m_token}").json()
                    st.metric("الحالة", res.get('stateInstance'))

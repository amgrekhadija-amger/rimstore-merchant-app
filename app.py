import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- 1. الإعدادات وتجهيز البيئة ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم المتجر - WPP", layout="wide")

# الاتصال بقاعدة البيانات
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ مفاتيح Supabase غير مضبوطة في ملف .env")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بـ Supabase: {e}")
    st.stop()

# --- 2. الدوال البرمجية (Green-API Logic) ---

def create_merchant_instance(phone):
    """إنشاء Instance جديد وحفظه للتاجر"""
    url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    try:
        res = requests.post(url, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            if m_id and m_token:
                # تحديث بيانات التاجر في الجدول
                supabase.table('merchants').update({
                    "instance_id": m_id, 
                    "api_token": m_token
                }).eq("Phone", phone).execute()
                return m_id, m_token
    except: pass
    return None, None

def get_pairing_code(m_id, m_token, phone):
    """جلب كود الربط الرقمي وحفظه في عمود qr_code"""
    clean_phone = ''.join(filter(str.isdigit, phone))
    url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_phone}"
    try:
        res = requests.get(url, timeout=20)
        if res.status_code == 200:
            code = res.json().get('code')
            if code:
                # حفظ الكود في عمود qr_code كما طلبتِ
                supabase.table('merchants').update({"qr_code": code}).eq("Phone", phone).execute()
                return code
    except: pass
    return None

# --- 3. واجهة المستخدم (UI) ---

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- شاشات ما قبل الدخول ---
if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    
    with tab_signup:
        with st.form("signup_form"):
            s_m_name = st.text_input("اسم التاجر الكامل")
            s_s_name = st.text_input("اسم المتجر")
            s_phone = st.text_input("رقم الواتساب (مثال: 22200000)")
            s_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                try:
                    supabase.table('merchants').insert({
                        "Merchant_name": s_m_name, 
                        "Store_name": s_s_name, 
                        "Phone": s_phone, 
                        "password": s_pass
                    }).execute()
                    st.success("✅ تم إنشاء الحساب! يمكنك الدخول الآن.")
                except: st.error("❌ فشل التسجيل (تأكدي من إعدادات الجدول)")

    with tab_login:
        with st.form("login_form"):
            l_phone = st.text_input("رقم الهاتف")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.session_state.store_name = res.data[0].get('Store_name')
                    st.rerun()
                else: st.error("❌ بيانات خاطئة")

# --- شاشات ما بعد الدخول ---
else:
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 خروج"):
        st.session_state.logged_in = False
        st.rerun()

    t1, t2, t3, t4 = st.tabs(["➕ منتج جديد", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    # --- تبويب إضافة المنتج ---
    with t1:
        with st.form("add_p"):
            p_name = st.text_input("اسم المنتج")
            p_price = st.number_input("السعر", min_value=0)
            p_file = st.file_uploader("صورة المنتج", type=['png', 'jpg', 'jpeg'])
            if st.form_submit_button("حفظ المنتج"):
                img_str = ""
                if p_file:
                    img_str = f"data:image/png;base64,{base64.b64encode(p_file.read()).decode()}"
                supabase.table('products').insert({
                    "Product": p_name, "Price": str(p_price), 
                    "Image_url": img_str, "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("✅ تمت الإضافة")

    # --- تبويب الطلبات ---
    with t3:
        st.subheader("🛒 الطلبات المستلمة")
        orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
        if orders.data:
            for o in orders.data:
                st.info(f"طلب من: {o['customer_pho']} | المنتج: {o['product_name']}")
        else: st.write("لا توجد طلبات.")

    # --- تبويب ربط الواتساب (الجزء الذي طلبتِه) ---
    with t4:
        st.subheader("📲 تفعيل وربط الواتساب")
        m_data = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute().data[0]
        m_id = m_data.get('instance_id')

        if not m_id or m_id == "None":
            if st.button("🚀 البدء: إنشاء جلسة ربط"):
                with st.spinner("جاري التواصل مع Green-API..."):
                    new_id, _ = create_merchant_instance(st.session_state.merchant_phone)
                    if new_id: st.rerun()
        else:
            st.info(f"🆔 معرف الجلسة: {m_id}")
            if st.button("🔢 طلب كود الربط (8 أرقام)"):
                with st.spinner("جاري جلب الكود..."):
                    code = get_pairing_code(m_id, m_data.get('api_token'), st.session_state.merchant_phone)
                    if code:
                        st.session_state.display_code = code
                        st.success("تم جلب الكود وحفظه بنجاح!")

            if 'display_code' in st.session_state:
                st.markdown(f"""
                <div style="text-align:center; background-color:#f0f2f6; padding:30px; border-radius:15px; border: 2px solid #075e54;">
                    <h2 style="color:#075e54;">كود ربط الواتساب:</h2>
                    <h1 style="letter-spacing: 12px; font-size: 60px; color:#128c7e;">{st.session_state.display_code}</h1>
                    <p>أدخل هذا الكود في هاتفك الآن</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.write("**🔧 طريقة الربط:**")
                st.write("واتساب الهاتف > الأجهزة المرتبطة > ربط جهاز > الربط برقم الهاتف بدلاً من ذلك.")

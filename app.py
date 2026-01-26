import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64

# --- الإعدادات الثابتة ---
# ملاحظة: تم استخدام الرابط الخاص بـ Instance رقم 7107 كما في صورتك
INSTANCE_ID = "7107486495"
API_TOKEN = "772f960f54514800808a349c2d6229199f1a0e1b6946445b91" # تأكدي من هذا التوكن من لوحة التحكم
BASE_URL = "https://7107.api.greenapi.com"

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

load_dotenv() 
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ يرجى ضبط المفاتيح في Advanced Settings -> Secrets")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- دالات الاتصال ---
def get_green_qr():
    url = f"{BASE_URL}/waInstance{INSTANCE_ID}/qr/{API_TOKEN}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            return res.json()
        return None
    except: return None

# --- واجهة تسجيل الدخول ---
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
                    supabase.table('merchants').insert({"Merchant_name": s_m_name, "Store_name": s_s_name, "Phone": s_phone, "password": s_pass}).execute()
                    st.success("✅ تم إنشاء الحساب!")
                except: st.error("خطأ في الخادم")
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
                else: st.error("بيانات خاطئة")
else:
    st.title(f"🏪 متجر: {st.session_state.store_name}")
    
    # تعريف التبويبات داخل شرط تسجيل الدخول لضمان عدم حدوث NameError
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t1:
        with st.form("add_p", clear_on_submit=True):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر")
            p_img = st.file_uploader("صورة المنتج", type=['png','jpg'])
            if st.form_submit_button("حفظ"):
                try:
                    img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                    supabase.table('products').insert({"Product": p_name, "Price": p_price, "Image_url": img_data, "Phone": st.session_state.merchant_phone}).execute()
                    st.success("تم الحفظ!")
                except: st.error("فشل الحفظ")

    with t2:
        st.subheader("📦 إدارة المنتجات")
        prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        for p in prods.data:
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{p['Product']}** - {p['Price']} MRU")
            if col2.button("🗑️", key=f"del_{p['id']}"):
                supabase.table('products').delete().eq("id", p['id']).execute()
                st.rerun()

    with t3:
        st.subheader("🛒 الطلبات")
        orders = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        for o in orders.data: st.write(f"طلب من {o['customer_phone']}: {o['product_name']}")

    with t4:
        st.subheader("📲 ربط واتساب المتجر")
        st.info(f"رقم الجهاز الفني المشترك: {INSTANCE_ID}")
        
        col_qr, col_status = st.columns(2)
        with col_qr:
            if st.button("🔄 توليد رمز QR للربط"):
                with st.spinner("جاري جلب الرمز..."):
                    qr_data = get_green_qr()
                    if qr_data:
                        if qr_data.get('type') == 'qrCode':
                            st.session_state.qr_img = qr_data.get('message')
                            st.rerun()
                        elif qr_data.get('type') == 'alreadyLoggedIn':
                            st.success("✅ الهاتف مربوط بالفعل!")
                    else: st.error("⚠️ فشل جلب الرمز")

            if 'qr_img' in st.session_state:
                st.image(base64.b64decode(st.session_state.qr_img), width=300)
        
        with col_status:
            if st.button("🔍 تحديث حالة الربط"):
                try:
                    res = requests.get(f"{BASE_URL}/waInstance{INSTANCE_ID}/getStateInstance/{API_TOKEN}", timeout=5).json()
                    st.write(f"الحالة الحالية: {res.get('stateInstance')}")
                except: st.error("تعذر الاتصال")

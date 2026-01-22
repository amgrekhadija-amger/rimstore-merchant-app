import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import time
import base64

# 1. إعداد الصفحة
st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

# 2. تحميل الإعدادات
load_dotenv() 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# الربط مع سيرفر Node.js (المنفذ الجديد)
GATEWAY_URL = "http://127.0.0.1:3000"

# 3. الاتصال بقاعدة البيانات
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ ملف .env ناقص")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ: {e}")
    st.stop()

# --- نظام الجلسة ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    
    with tab_signup:
        with st.form("signup_form"):
            s_merchant_name = st.text_input("اسم التاجر")
            s_store_name = st.text_input("اسم المحل")
            s_phone = st.text_input("رقم واتساب التاجر")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            
            if st.form_submit_button("إنشاء الحساب"):
                check = supabase.table('merchants').select("Phone").eq("Phone", s_phone).execute()
                if check.data: st.error("❌ الرقم مسجل مسبقاً!")
                elif s_merchant_name and s_store_name and s_phone and s_pass:
                    supabase.table('merchants').insert({
                        "Merchant_name": s_merchant_name, "Store_name": s_store_name, 
                        "Phone": s_phone, "password": s_pass, "session_status": "disconnected"
                    }).execute()
                    st.success("✅ تم إنشاء الحساب!")
                else: st.warning("أكمل البيانات")

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
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    # --- تبويب إضافة المنتج (نفس تصميمك) ---
    with t1:
        status_db = supabase.table('merchants').select("session_status").eq("Phone", st.session_state.merchant_phone).execute()
        is_linked = status_db.data and status_db.data[0].get('session_status') == "connected"

        if not is_linked:
            st.warning("⚠️ يجب ربط الواتساب أولاً.")
        
        with st.form("add_p", clear_on_submit=True):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر")
            p_size = st.text_input("المقاس")
            p_color = st.text_input("اللون")
            p_img = st.file_uploader("صورة المنتج", type=['png','jpg'])
            if st.form_submit_button("حفظ") and is_linked:
                img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                supabase.table('products').insert({
                    "Product": p_name, "Price": p_price, "Size": p_size,
                    "Color": p_color, "Image_url": img_data, "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("تم الحفظ!")

    # --- تبويب ربط الواتساب (التعديل التقني فقط) ---
    with t4:
        st.subheader("إعدادات الاتصال")
        if st.button("🔄 توليد رمز QR الجديد"):
            with st.spinner("جاري الاتصال..."):
                try:
                    requests.post(f"{GATEWAY_URL}/init-session", json={"phone": st.session_state.merchant_phone})
                    st.session_state.show_qr = True
                    time.sleep(2)
                    st.rerun()
                except: st.error("تأكد من تشغيل ملف server.js أولاً")

        if st.session_state.get('show_qr'):
            try:
                res = requests.get(f"{GATEWAY_URL}/get-qr/{st.session_state.merchant_phone}")
                if res.status_code == 200:
                    st.image(res.json()['qr'], caption="امسح الرمز بواتساب التاجر")
                else: st.info("الرمز قيد التجهيز...")
            except: st.error("فشل جلب الرمز")
            
            if st.button("🔄 تحديث حالة الربط"):
                check = supabase.table('merchants').select("session_status").eq("Phone", st.session_state.merchant_phone).execute()
                if check.data and check.data[0]['session_status'] == "connected":
                    st.success("✅ متصل!")
                    st.session_state.show_qr = False
                    st.rerun()
                else: st.info("لم يتم المسح بعد.")

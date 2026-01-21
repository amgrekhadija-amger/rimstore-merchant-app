import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
import requests
import time
import base64

# 1. إعداد الصفحة
st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

# 2. تحميل الإعدادات
load_dotenv() 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WPP_URL = os.getenv("WPP_URL", "http://127.0.0.1:2136")
SECRET_KEY = os.getenv("SECRET_KEY", "THISISMYSECUREKEY")

# 3. الاتصال بقاعدة البيانات
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ ملف .env ناقص أو غير موجود")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بـ Supabase: {e}")
    st.stop()

# --- واجهة المستخدم (الدخول والتسجيل تبقى كما هي) ---
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
                if check.data: st.error("❌ هذا الرقم مسجل مسبقاً!")
                elif s_merchant_name and s_store_name and s_phone and s_pass:
                    supabase.table('merchants').insert({
                        "Merchant_name": s_merchant_name, "Store_name": s_store_name, 
                        "Phone": s_phone, "password": s_pass, "session_status": "disconnected"
                    }).execute()
                    st.success("✅ تم إنشاء الحساب!")
                else: st.warning("اكمل البيانات")

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

    # --- تبويب إضافة المنتج ---
    with t1:
        # فحص حالة الربط من قاعدة البيانات
        status_db = supabase.table('merchants').select("session_status").eq("Phone", st.session_state.merchant_phone).execute()
        is_linked = status_db.data and status_db.data[0].get('session_status') == "connected"

        if not is_linked:
            st.warning("⚠️ يجب ربط الواتساب أولاً لتتمكن من إضافة المنتجات.")
        
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

    # --- تبويب ربط الواتساب (التعديل الجذري لـ WPP) ---
    with t4:
        st.subheader("ربط الواتساب (WPPConnect)")
        session_id = f"store_{st.session_state.merchant_phone}"
        headers = {"Authorization": f"Bearer {SECRET_KEY}", "Content-Type": "application/json"}

        if st.button("🔄 توليد رمز QR الجديد"):
            with st.spinner("جاري بدء الجلسة..."):
                # 1. بدء الجلسة
                requests.post(f"{WPP_URL}/api/{session_id}/start-session", headers=headers)
                st.session_state.show_qr = True
                st.rerun()

        if st.session_state.get('show_qr'):
            qr_url = f"{WPP_URL}/api/{session_id}/qrcode-session"
            qr_res = requests.get(qr_url, headers=headers)
            
            if qr_res.status_code == 200:
                st.image(qr_res.content, caption="امسح الرمز الآن")
            
            # فحص الحالة
            check_url = f"{WPP_URL}/api/{session_id}/check-connection-session"
            status_res = requests.get(check_url, headers=headers).json()
            
            if status_res.get('status') is True:
                supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", st.session_state.merchant_phone).execute()
                st.success("✅ تم الربط بنجاح!")
                st.session_state.show_qr = False
                st.rerun()

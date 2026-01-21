import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
import requests
import base64

# 1. إعداد الصفحة
st.set_page_config(page_title="لوحة تحكم المتجر - WPP", layout="wide")

# 2. تحميل الإعدادات
load_dotenv() 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# التعديل: تغيير المنفذ إلى 21465 كما ظهر في السجلات
WPP_URL = os.getenv("WPP_URL", "http://127.0.0.1:21465")
SECRET_KEY = os.getenv("SECRET_KEY", "THISISMYSECUREKEY")

# 3. الاتصال بقاعدة البيانات
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ ملف .env ناقص")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ Supabase: {e}")
    st.stop()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # --- واجهة الدخول (نفس كودك الأصلي) ---
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    with tab_signup:
        with st.form("signup"):
            s_phone = st.text_input("رقم الواتساب")
            s_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء"):
                supabase.table('merchants').insert({"Phone": s_phone, "password": s_pass, "session_status": "disconnected"}).execute()
                st.success("تم!")
    with tab_login:
        with st.form("login"):
            l_phone = st.text_input("رقم الهاتف")
            l_pass = st.text_input("السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.rerun()
else:
    st.title(f"🏪 لوحة التحكم")
    t1, t4 = st.tabs(["➕ المنتجات", "📲 ربط الواتساب"])

    with t4:
        st.subheader("ربط الواتساب")
        session_id = f"store_{st.session_state.merchant_phone}"
        headers = {"Authorization": f"Bearer {SECRET_KEY}", "Content-Type": "application/json"}

        if st.button("🔄 توليد رمز QR"):
            with st.spinner("جاري الاتصال بالمحرك..."):
                # طلب بدء الجلسة
                try:
                    requests.post(f"{WPP_URL}/api/{session_id}/start-session", headers=headers)
                    st.session_state.show_qr = True
                    st.info("تم إرسال الطلب، انتظر ظهور الرمز بالأسفل...")
                except:
                    st.error("المحرك لا يستجيب، تأكد من تشغيل wpp-server")

        if st.session_state.get('show_qr'):
            # محاولة جلب الرمز
            qr_url = f"{WPP_URL}/api/{session_id}/qrcode-session"
            try:
                qr_res = requests.get(qr_url, headers=headers)
                if qr_res.status_code == 200:
                    # عرض الصورة مباشرة
                    st.image(qr_res.content, caption="امسح الرمز عبر واتساب هاتف")
                else:
                    st.warning("الرمز يتكون الآن... انتظر ثوانٍ واضغط 'توليد' مرة أخرى")
            except:
                st.error("فشل جلب الرمز")

        # زر لفحص الحالة يدوياً
        if st.button("✅ تأكيد الربط"):
            check_url = f"{WPP_URL}/api/{session_id}/check-connection-session"
            try:
                status_res = requests.get(check_url, headers=headers).json()
                if status_res.get('status') is True:
                    supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", st.session_state.merchant_phone).execute()
                    st.success("تم الربط بنجاح!")
                    st.session_state.show_qr = False
                else:
                    st.error("لم يتم المسح بعد.")
            except:
                st.error("لا يمكن التأكد من الحالة حالياً")

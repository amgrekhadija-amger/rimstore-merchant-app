import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
import requests

# 1. إعداد الصفحة (يجب أن يكون أول سطر)
st.set_page_config(page_title="RimStore - لوحة تحكم التاجر", layout="wide")

# 2. تحديد مسار ملف .env بدقة لضمان قراءته على السيرفر
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MY_GATEWAY_URL = os.getenv("MY_GATEWAY_URL", "http://46.224.250.252:3000")

# 3. التأكد من تحميل الإعدادات بنجاح
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(f"⚠️ خطأ: ملف .env مفقود أو غير مكتمل في المسار: {env_path}")
    st.info("تأكدي من وجود الملف داخل مجلد المشروع.")
    st.stop()

# 4. الاتصال بقاعدة البيانات مع معالجة الأخطاء
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ فشل الاتصال بـ Supabase: {e}")
    st.stop()

# --- 5. قاموس اللغات والتصميم ---
languages = {
    "العربية": {
        "dir": "rtl",
        "title": "RimStore - لوحة تحكم التاجر",
        "sidebar_title": "🔐 بوابة التاجر",
        "tabs": ["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"],
        "qr_btn": "توليد رمز الـ QR الخاص بسيرفري",
        "status_connected": "✅ متصل بسيرفر RimStore الخاص",
        "status_disconnected": "❌ غير متصل، امسح الرمز لربط جهازك",
        "login": "دخول",
        "phone": "رقم الواتساب",
        "password": "كلمة السر"
    }
}

if 'lang' not in st.session_state: st.session_state.lang = "العربية"
t = languages[st.session_state.lang]

# --- 6. نظام تسجيل الدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title(t["title"])
    with st.form("login_form"):
        phone = st.text_input(t["phone"])
        password = st.text_input(t["password"], type="password")
        if st.form_submit_button(t["login"]):
            # هنا يتم التحقق من التاجر في قاعدة البيانات
            st.session_state.logged_in = True
            st.session_state.merchant_phone = phone
            st.rerun()
else:
    # --- 7. لوحة التحكم الرئيسية بعد الدخول ---
    st.title(t["title"])
    tab1, tab2, tab3, tab4 = st.tabs(t["tabs"])
    
    with tab1:
        st.subheader("📦 إضافة بضاعة جديدة")
        # أضيفي هنا حقول إضافة المنتج الخاصة بكِ

    with tab4:
        st.subheader("📲 نظام الربط الخاص (RimStore Gateway)")
        merchant_id = st.session_state.merchant_phone
        
        try:
            res = supabase.table('merchants').select('session_status, qr_code').eq('Phone', merchant_id).execute()
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(t["qr_btn"]):
                    if res.data:
                        status = res.data[0].get('session_status')
                        qr_string = res.data[0].get('qr_code')
                        
                        if status == 'connected':
                            st.success(t["status_connected"])
                        elif qr_string:
                            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_string}"
                            st.image(qr_url, caption="امسح الرمز لربط متجرك", width=300)
                        else:
                            try:
                                requests.post(f"{MY_GATEWAY_URL}/init-session", json={"phone": merchant_id}, timeout=5)
                                st.info("جاري طلب الرمز... انتظر ثواني وحدث الصفحة")
                            except:
                                st.error("السيرفر الخاص (Node.js) غير متصل حالياً")
            
            with col2:
                if res.data and res.data[0].get('session_status') == 'connected':
                    st.success(t["status_connected"])
                else:
                    st.warning(t["status_disconnected"])
        except Exception as e:
            st.error(f"حدث خطأ أثناء جلب البيانات: {e}")

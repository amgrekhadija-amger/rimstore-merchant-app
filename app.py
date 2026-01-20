import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
import requests
import time
import base64
from PIL import Image
import io

# 1. إعداد الصفحة
st.set_page_config(page_title="لوحة تحكم المتجر", layout="wide")

# 2. تحميل الإعدادات
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# إعدادات Evolution API
EVO_URL = "http://46.224.250.252:8080"
EVO_API_KEY = "123456" 

# 3. الاتصال بقاعدة البيانات
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ خطأ في ملف .env")
    st.stop()

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ اتصال بـ Supabase: {e}")
    st.stop()

# --- وظيفة ضبط الـ Webhook آلياً ---
def set_webhook_automatically(instance_name):
    url = f"{EVO_URL}/webhook/set/{instance_name}"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    payload = {
        "enabled": True,
        "url": "http://localhost:5000/webhook", 
        "webhook_by_events": False,
        "events": ["MESSAGES_UPSERT"]
    }
    try:
        requests.post(url, json=payload, headers=headers, timeout=5)
        return True
    except:
        return False

# --- 4. واجهة الدخول وإنشاء الحساب (بدون تغيير) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    with tab_login:
        with st.form("login_form"):
            st.subheader("تسجيل الدخول")
            l_phone = st.text_input("رقم واتساب التاجر")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.session_state.store_name = res.data[0].get('Store_name', 'المتجر')
                    st.rerun()
                else: st.error("بيانات الدخول غير صحيحة")

    with tab_signup:
        with st.form("signup_form"):
            st.subheader("فتح متجر جديد")
            s_name = st.text_input("اسم التاجر")
            s_phone = st.text_input("رقم الواتساب")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                try:
                    supabase.table('merchants').insert({"Store_name": s_name, "Phone": s_phone, "password": s_pass}).execute()
                    st.success("تم إنشاء الحساب بنجاح!")
                except: st.error("الرقم مسجل مسبقاً")
else:
    current_store = st.session_state.get('store_name', 'متجرك')
    st.title(f"🏪 لوحة تحكم: {current_store}")
    tab1, tab2, tab3, tab4 = st.tabs(["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"])

    # قسم إضافة منتج (بدون تغيير)
    with tab1:
        with st.form("add_product", clear_on_submit=True):
            p_name = st.text_input("📍 اسم المنتج")
            p_price = st.number_input("💰 السعر", min_value=0)
            if st.form_submit_button("حفظ"):
                supabase.table('products').insert({"Product": p_name, "Price": str(p_price), "Phone": st.session_state.merchant_phone}).execute()
                st.success("تم الحفظ!")

    # قسم إدارة الأسعار والطلبات (بدون تغيير)
    with tab2: st.info("إدارة المنتجات")
    with tab3: st.info("الطلبات")

    # --- قسم ربط الواتساب (التعديل المطلوب) ---
    with tab4:
        st.subheader("📲 ربط واتساب المتجر")
        merchant_phone = st.session_state.merchant_phone
        instance_name = f"merchant_{merchant_phone}"
        headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 توليد رمز QR جديد"):
                # 1. إنشاء الجلسة
                requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instance_name}, headers=headers)
                # 2. ضبط الـ Webhook آلياً
                set_webhook_automatically(instance_name)
                st.session_state.last_qr_time = time.time()
                st.rerun()

            # منطق تحديث الـ QR كل 20 ثانية وعدم الحفظ إلا عند النجاح
            if 'last_qr_time' in st.session_state:
                res_qr = requests.get(f"{EVO_URL}/instance/connect/{instance_name}", headers=headers)
                if res_qr.status_code == 200:
                    qr_base64 = res_qr.json().get('base64')
                    if qr_base64:
                        img_data = base64.b64decode(qr_base64.split(",")[1] if "," in qr_base64 else qr_base64)
                        st.image(Image.open(io.BytesIO(img_bytes)), caption="امسح الكود خلال 20 ثانية")
                
                # التحقق من حالة الاتصال
                status_res = requests.get(f"{EVO_URL}/instance/connectionState/{instance_name}", headers=headers)
                state = status_res.json().get('instance', {}).get('state')
                
                if state == "open":
                    # الآن فقط يتم الحفظ في Database بنجاح
                    supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", merchant_phone).execute()
                    st.success("✅ تم الربط بنجاح وحفظ البيانات!")
                    del st.session_state.last_qr_time
                else:
                    time.sleep(20) # الانتظار 20 ثانية قبل التحديث القادم
                    st.rerun()

        with col2:
            st.info("سيتم ضبط البوت آلياً فور مسح الكود")

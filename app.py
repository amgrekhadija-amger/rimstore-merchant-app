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
st.set_page_config(page_title="لوحة تحكم المتجر المتطورة", layout="wide")

# 2. تحميل الإعدادات وتصحيح العناوين
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# تصحيح: الاتصال داخلي (Local) لتفاوضي خطأ Connection Refused
EVO_URL = os.getenv("EVO_URL", "http://127.0.0.1:8080")
EVO_API_KEY = os.getenv("EVO_API_KEY", "123456") 

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
    # ملاحظة: استبدلي IP السيرفر هنا بعنوانك الفعلي ليصل البوت البيانات
    payload = {
        "enabled": True,
        "url": "http://46.224.250.252:5000/webhook", 
        "webhook_by_events": False,
        "events": ["MESSAGES_UPSERT"]
    }
    try:
        requests.post(url, json=payload, headers=headers, timeout=5)
        return True
    except:
        return False

# --- واجهة المستخدم ---
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
            s_merchant_name = st.text_input("اسم التاجر") # جديد
            s_store_name = st.text_input("اسم المحل") # جديد
            s_phone = st.text_input("رقم واتساب التاجر")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            
            if st.form_submit_button("إنشاء الحساب"):
                if s_merchant_name and s_store_name and s_phone and s_pass:
                    try:
                        supabase.table('merchants').insert({
                            "merchant_name": s_merchant_name,
                            "Store_name": s_store_name, 
                            "Phone": s_phone, 
                            "password": s_pass
                        }).execute()
                        st.success("تم إنشاء حساب المحل بنجاح!")
                    except: st.error("الرقم مسجل مسبقاً أو هناك خطأ في البيانات")
                else:
                    st.warning("الرجاء ملء جميع الخانات")

else:
    current_store = st.session_state.get('store_name', 'متجرك')
    st.title(f"🏪 لوحة تحكم: {current_store}")
    tab1, tab2, tab3, tab4 = st.tabs(["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"])

    with tab1:
        st.subheader("إضافة منتج جديد للمتجر")
        with st.form("add_product", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                p_name = st.text_input("📍 اسم المنتج")
                p_price = st.number_input("💰 السعر", min_value=0)
                p_size = st.text_input("📏 المقاس (مثال: XL, 42, 2L)") # جديد
            with col_b:
                p_colors = st.text_input("🎨 الألوان المتوفرة (افصلي بينها بفاصلة)") # جديد
                p_image = st.file_uploader("🖼️ ارفع صورة المنتج", type=['png', 'jpg', 'jpeg']) # جديد
            
            if st.form_submit_button("حفظ المنتج"):
                # تحويل الصورة إلى نص إذا وجدت (Base64) للتخزين البسيط أو معالجة الرفع
                img_str = ""
                if p_image:
                    img_str = base64.b64encode(p_image.read()).decode()

                try:
                    supabase.table('products').insert({
                        "Product": p_name, 
                        "Price": str(p_price), 
                        "Size": p_size,
                        "Colors": p_colors,
                        "Image": img_str,
                        "Phone": st.session_state.merchant_phone
                    }).execute()
                    st.success(f"تمت إضافة {p_name} بنجاح!")
                except Exception as e:
                    st.error(f"خطأ أثناء الحفظ: {e}")

    # بقية الأقسام (إدارة الأسعار، الطلبات، الواتساب) تبقى كما هي مع التأكد من EVO_URL المعدل أعلاه
    with tab4:
        st.subheader("📲 ربط واتساب المتجر")
        merchant_phone = st.session_state.merchant_phone
        instance_name = f"merchant_{merchant_phone}"
        headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}

        if st.button("🔄 توليد رمز QR جديد"):
            requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instance_name}, headers=headers)
            set_webhook_automatically(instance_name)
            st.session_state.last_qr_time = time.time()
            st.rerun()

        if 'last_qr_time' in st.session_state:
            res_qr = requests.get(f"{EVO_URL}/instance/connect/{instance_name}", headers=headers)
            if res_qr.status_code == 200:
                qr_base64 = res_qr.json().get('base64')
                if qr_base64:
                    img_data = base64.b64decode(qr_base64.split(",")[1] if "," in qr_base64 else qr_base64)
                    st.image(Image.open(io.BytesIO(img_data)), caption="امسح الكود الآن")
            
            status_res = requests.get(f"{EVO_URL}/instance/connectionState/{instance_name}", headers=headers)
            if status_res.status_code == 200 and status_res.json().get('instance', {}).get('state') == "open":
                supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", merchant_phone).execute()
                st.success("✅ تم الربط!")
                del st.session_state.last_qr_time
                st.rerun()

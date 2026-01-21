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

# 2. تحميل الإعدادات من ملف .env الموجود على السيرفر
load_dotenv() 

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EVO_URL = os.getenv("EVO_URL", "http://127.0.0.1:8080")
EVO_API_KEY = os.getenv("EVO_API_KEY", "123456") 

# 3. الاتصال بقاعدة البيانات
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ ملف .env ناقص أو غير موجود في السيرفر")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بـ Supabase: {e}")
    st.stop()

# --- واجهة المستخدم ---
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
                if check.data:
                    st.error("❌ هذا الرقم مسجل مسبقاً!")
                elif s_merchant_name and s_store_name and s_phone and s_pass:
                    supabase.table('merchants').insert({
                        "Merchant_name": s_merchant_name, "Store_name": s_store_name, 
                        "Phone": s_phone, "password": s_pass, "is_active": True
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

    with t1:
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

    with t3:
        st.subheader("الطلبات الواردة")
        ords = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        if ords.data: st.table(pd.DataFrame(ords.data)[['customer_phone', 'product_name', 'total_price', 'status']])

    with t4:
        st.subheader("ربط الواتساب")
        # التعديل: تغيير اسم الجلسة إلى v2 لتجاوز أخطاء الـ state القديمة
        inst = f"v2_{st.session_state.merchant_phone}"
        headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}

        if st.button("🔄 توليد رمز QR جديد"):
            # الخطوة 1: حذف الجلسة القديمة لتنظيف الذاكرة تماماً
            try: requests.delete(f"{EVO_URL}/instance/delete/{inst}", headers=headers, timeout=5)
            except: pass
            time.sleep(1) 
            
            # الخطوة 2: إنشاء الجلسة بطلب بسيط جداً
            create_payload = {
                "instanceName": inst,
                "token": "123456",
                "integration": "WHATSAPP-BAILEYS",
                "qrcode": True
            }
            
            response = requests.post(f"{EVO_URL}/instance/create", json=create_payload, headers=headers)
            
            if response.status_code in [200, 201]:
                # الخطوة 3: ضبط الـ Webhook بشكل منفصل
                webhook_payload = {
                    "enabled": True,
                    "url": "http://46.224.250.252:5000/webhook",
                    "webhook_by_events": False,
                    "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]
                }
                requests.post(f"{EVO_URL}/webhook/set/{inst}", json=webhook_payload, headers=headers)
                
                st.session_state.qr_time = time.time()
                st.rerun()
            else:
                st.error(f"خطأ في الطلب: {response.text}")

        if 'qr_time' in st.session_state:
            elapsed = time.time() - st.session_state.qr_time
            if elapsed > 40:
                st.error("انتهت الصلاحية! يرجى التوليد مرة أخرى.")
                del st.session_state.qr_time
            else:
                qr_res = requests.get(f"{EVO_URL}/instance/connect/{inst}", headers=headers)
                if qr_res.status_code == 200:
                    qr_data = qr_res.json()
                    qr_base64 = qr_data.get('base64') or qr_data.get('code')
                    if qr_base64:
                        img_b64 = qr_base64.split(",")[1] if "," in qr_base64 else qr_base64
                        st.image(base64.b64decode(img_b64), caption=f"امسح الرمز الآن (المتبقي: {int(40-elapsed)} ثانية)")
                
                chk = requests.get(f"{EVO_URL}/instance/connectionState/{inst}", headers=headers)
                if chk.status_code == 200 and chk.json().get('instance', {}).get('state') == "open":
                    supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", st.session_state.merchant_phone).execute()
                    st.success("✅ تم الربط بنجاح!")
                    del st.session_state.qr_time
                    st.rerun()

import streamlit as st
from supabase import create_client
import pandas as pd
import uuid
import requests
import os
from dotenv import load_dotenv

# --- 1. تحميل الإعدادات من ملف .env ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MY_GATEWAY_URL = os.getenv("MY_GATEWAY_URL", "http://46.224.250.252:3000")

# التأكد من تحميل المفاتيح بنجاح
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ خطأ: لم يتم العثور على إعدادات Supabase في ملف .env")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- (قاموس اللغات كما هو في تصميمك الأصلي) ---
languages = {
    "العربية": {
        "dir": "rtl",
        "title": "RimStore - لوحة تحكم التاجر",
        "sidebar_title": "🔐 بوابة التاجر",
        "auth_mode": ["تسجيل دخول", "إنشاء حساب جديد"],
        "login": "دخول",
        "signup": "إنشاء الحساب والدخول",
        "phone": "رقم الواتساب",
        "password": "كلمة السر",
        "store_name": "اسم المتجر",
        "tabs": ["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"],
        "add_prod_title": "إضافة بضاعة جديدة",
        "p_name": "📍 اسم المنتج",
        "p_price": "💰 السعر",
        "save": "حفظ ونشر المنتج",
        "qr_btn": "توليد رمز الـ QR الخاص بسيرفري",
        "logout": "تسجيل الخروج",
        "status_connected": "✅ متصل بسيرفر RimStore الخاص",
        "status_disconnected": "❌ غير متصل، امسح الرمز لربط جهازك"
    }
}

if 'lang' not in st.session_state: st.session_state.lang = "العربية"
t = languages[st.session_state.lang]

# ... (كود تسجيل الدخول والتحقق يظل هنا كما هو) ...

if st.session_state.get('logged_in', False):
    
    tab1, tab2, tab3, tab4 = st.tabs(t["tabs"])
    
    # --- Tab 4: نظام الربط (باستخدام المتغيرات المحمية) ---
    with tab4:
        st.subheader("📲 نظام الربط الخاص (RimStore Gateway)")
        
        merchant_id = st.session_state.merchant_phone
        
        # جلب حالة السيرفر من Supabase
        try:
            res = supabase.table('merchants').select('session_status, qr_code').eq('Phone', merchant_id).execute()
        except Exception as e:
            st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
            res = None
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(t["qr_btn"]):
                if res and res.data:
                    status = res.data[0].get('session_status')
                    qr_string = res.data[0].get('qr_code')
                    
                    if status == 'connected':
                        st.success(t["status_connected"])
                    elif qr_string:
                        # تحويل النص إلى صورة QR
                        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_string}"
                        st.image(qr_url, caption="امسح الرمز لربط متجرك", width=300)
                    else:
                        try:
                            requests.post(f"{MY_GATEWAY_URL}/init-session", json={"phone": merchant_id}, timeout=5)
                            st.info("جاري طلب الرمز... انتظر ثواني وحدث الصفحة")
                        except:
                            st.error("السيرفر الخاص غير متصل حالياً (Node.js Gateway Offline)")
                else:
                    st.error("لم يتم العثور على بيانات التاجر. تأكد من إعداد حسابك بشكل صحيح.")
        
        with col2:
            if res and res.data and res.data[0].get('session_status') == 'connected':
                st.success(t["status_connected"])
            else:
                st.warning(t["status_disconnected"])
                
            st.info("💡 بمجرد مسح الكود، سيصبح سيرفرك هو المسؤول عن الردود التلقائية دون الحاجة لشركات وسيطة.")
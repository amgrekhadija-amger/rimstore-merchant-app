import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64

# --- إعدادات الأمان وقراءة الملف ---
load_dotenv() 
if not os.getenv("SUPABASE_URL"):
    home_env = os.path.expanduser('/home/rimstorebot/.env')
    load_dotenv(home_env)

# --- الإعدادات الثابتة (تعليمات الفريق) ---
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ عطل في قاعدة البيانات: {e}")
    st.stop()

# --- 1. دالة إنشاء Instance (مع تشخيص الخطأ) ---
def create_merchant_instance(phone):
    # تطبيق الرابط المباشر حسب تعليمات الفريق
    url = f"https://api.greenapi.com/partner/createInstance/{PARTNER_TOKEN}"
    payload = {"plan": "developer"}
    
    try:
        res = requests.post(url, json=payload, timeout=25)
        # تشخيص: إذا لم تكن الاستجابة 200، اطبع السبب
        if res.status_code != 200:
            return None, f"فشل السيرفر: {res.status_code} - {res.text}"
        
        data = res.json()
        m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
        
        if m_id and m_token:
            supabase.table('merchants').update({"instance_id": m_id, "api_token": m_token}).eq("Phone", phone).execute()
            return m_id, m_token
        return None, "بيانات المثيل ناقصة من الاستجابة"
    except Exception as e:
        return None, f"خطأ اتصال: {str(e)}"

# --- واجهة التطبيق ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    st.title(f"🏪 لوحة تحكم: {st.session_state.store_name}")
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t4:
        st.subheader("📲 تشخيص وربط الواتساب")
        
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id:
            st.warning("⚠️ لا يوجد مثيل مربوط بهذا الحساب.")
            if st.button("🚀 تفعيل وإنشاء مثيل الآن"):
                with st.spinner("جاري المحاولة..."):
                    new_id, error = create_merchant_instance(st.session_state.merchant_phone)
                    if new_id:
                        st.success(f"✅ تم الإنشاء بنجاح! ID: {new_id}")
                        st.rerun()
                    else:
                        st.error(f"❌ فشل التفعيل. السبب: {error}") # سيكتب لكِ الخطأ هنا
        else:
            st.info(f"المثيل الحالي: {m_id}")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 جلب كود الربط (8 أرقام)"):
                    # الربط بالرقم هو الأضمن عند فشل الـ QR
                    url_code = f"https://api.greenapi.com/waInstance{m_id}/getAuthorizationCode/{m_token}"
                    try:
                        res = requests.post(url_code, json={"phoneNumber": st.session_state.merchant_phone})
                        if res.status_code == 200:
                            st.success(f"كود الربط: {res.json().get('code')}")
                        else:
                            st.error(f"مخطأ: {res.status_code} - {res.text}")
                    except Exception as e:
                        st.error(f"عطل: {e}")

            with col2:
                if st.button("🔍 فحص حالة المثيل"):
                    try:
                        res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/getStateInstance/{m_token}").json()
                        st.metric("الحالة", res.get('stateInstance'))
                    except:
                        st.error("تعذر الوصول للسيرفر.")

# --- بقية الكود (الدخول والتسجيل) كما هي ---

import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- إعدادات الأمان وقراءة الملف من PythonAnywhere ---
load_dotenv() 
if not os.getenv("SUPABASE_URL"):
    home_env = os.path.expanduser('/home/rimstorebot/.env')
    load_dotenv(home_env)

# --- الإعدادات الثابتة ---
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ مفاتيح .env غير موجودة في السيرفر")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 1. دالة إنشاء Instance ---
def create_merchant_instance(phone):
    url = f"https://api.greenapi.com/partner/createInstance/{PARTNER_TOKEN}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
            if m_id and m_token:
                supabase.table('merchants').update({"instance_id": m_id, "api_token": m_token}).eq("Phone", phone).execute()
                # ضبط الويب هوك
                requests.post(f"https://api.greenapi.com/waInstance{m_id}/setSettings/{m_token}", 
                              json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
                return m_id, m_token
        return None, None
    except: return None, None

# --- 2. دالة الربط برقم الهاتف (الطريقة البديلة) ---
def get_linking_code(m_id, m_token, phone_to_link):
    # إزالة أي رموز غير رقمية من الهاتف
    clean_phone = ''.join(filter(str.isdigit, phone_to_link))
    url = f"https://api.greenapi.com/waInstance{m_id}/getAuthorizationCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code'), None
        return None, f"خطأ: {res.text}"
    except Exception as e:
        return None, str(e)

# --- واجهة التطبيق (القسم الخاص بالربط) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    st.title(f"🏪 لوحة تحكم: {st.session_state.store_name}")
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    # ... (الأقسام 1 و 2 و 3 كما هي) ...

    with t4:
        st.subheader("📲 ربط الواتساب (اختر الطريقة المناسبة)")
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id:
            if st.button("🚀 تفعيل الحساب أولاً"):
                create_merchant_instance(st.session_state.merchant_phone)
                st.rerun()
        else:
            col_qr, col_phone = st.columns(2)
            
            with col_qr:
                st.info("الطريقة الأولى: مسح الـ QR")
                if st.button("🔄 إظهار رمز QR"):
                    url_qr = f"https://api.greenapi.com/waInstance{m_id}/qr/{m_token}"
                    res = requests.get(url_qr)
                    if res.status_code == 200 and res.json().get('type') == 'qrCode':
                        st.image(base64.b64decode(res.json().get('message')), width=250)
                    else:
                        st.error("مخطأ: لا يمكن جلب الـ QR حالياً")

            with col_phone:
                st.info("الطريقة الثانية: الربط برقم الهاتف")
                phone_input = st.text_input("أدخل الرقم (مع رمز الدولة، مثلاً 222...)", value=st.session_state.merchant_phone)
                if st.button("🔑 الحصول على كود الربط"):
                    code, err = get_linking_code(m_id, m_token, phone_input)
                    if code:
                        st.success(f"كود الربط الخاص بك هو: {code}")
                        st.write("اذهب إلى: واتساب > الأجهزة المرتبطة > ربط جهاز > الربط برقم الهاتف")
                    else:
                        st.error(f"مخطأ: {err}")

            st.divider()
            if st.button("🔍 فحص حالة الاتصال"):
                res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/getStateInstance/{m_token}").json()
                st.warning(f"حالة الجهاز الحالية: {res.get('stateInstance')}")

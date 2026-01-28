import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64

# --- إعدادات الأمان ---
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
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ قاعدة بيانات: {e}")
    st.stop()

# --- دالة إنشاء المثيل مع طباعة تقرير مفصل ---
def create_merchant_instance(phone):
    st.write("🔍 جاري محاولة إنشاء المثيل...") 
    url = f"https://api.greenapi.com/partner/createInstance/{PARTNER_TOKEN}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        st.write(f"📡 استجابة السيرفر: {res.status_code}") # سيطبع الكود هنا (200 أو غيره)
        
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            if m_id and m_token:
                supabase.table('merchants').update({"instance_id": m_id, "api_token": m_token}).eq("Phone", phone).execute()
                st.write("✅ تم التحديث في قاعدة البيانات")
                return m_id, m_token
        else:
            st.error(f"❌ تفاصيل الخطأ من السيرفر: {res.text}")
    except Exception as e:
        st.error(f"⚠️ فشل الاتصال تماماً: {e}")
    return None, None

# --- واجهة التطبيق ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    st.title(f"🏪 متجر: {st.session_state.store_name}")
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t4:
        st.subheader("📲 فحص الربط المباشر")
        
        # جلب البيانات الحالية من Supabase
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        # منطقة التشخيص (تظهر دائماً لتعرفي ما يحدث)
        st.write(f"🛠️ تشخيص: ID={m_id} | Token={'موجود' if m_token else 'مفقود'}")

        if not m_id:
            st.warning("⚠️ لا يوجد ربط حالي.")
            if st.button("🚀 اضغطي هنا للتفعيل الآن"):
                res_id, res_tk = create_merchant_instance(st.session_state.merchant_phone)
                if res_id:
                    st.success("✨ نجح التفعيل! جاري إعادة التحميل...")
                    st.rerun()
        else:
            # إذا كان المثيل موجوداً، سنحاول جلب الكود بـ 3 طرق
            st.success(f"✅ المثيل {m_id} جاهز للربط")
            
            if st.button("🔑 جلب كود الربط (8 أرقام)"):
                st.write("⏳ جاري طلب الكود من السيرفر...")
                url_code = f"https://api.greenapi.com/waInstance{m_id}/getAuthorizationCode/{m_token}"
                try:
                    res = requests.post(url_code, json={"phoneNumber": st.session_state.merchant_phone})
                    st.write(f"📡 كود استجابة الكود: {res.status_code}")
                    if res.status_code == 200:
                        st.code(res.json().get('code'), language="text")
                        st.info("أدخلي هذا الكود في واتساب الهاتف (الأجهزة المرتبطة)")
                    else:
                        st.error(f"مخطأ تقني: {res.text}")
                except Exception as e:
                    st.error(f"عطل اتصال: {e}")

            if st.button("🖼️ تجربة إظهار الـ QR"):
                url_qr = f"https://api.greenapi.com/waInstance{m_id}/qr/{m_token}"
                res = requests.get(url_qr)
                if res.status_code == 200 and res.json().get('type') == 'qrCode':
                    st.image(base64.b64decode(res.json().get('message')))
                else:
                    st.error("فشل جلب الصورة، استخدمي كود الـ 8 أرقام أعلاه.")

# --- بقية الكود (Login/Signup) كما هي ---

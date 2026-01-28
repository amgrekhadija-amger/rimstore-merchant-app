import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- إعدادات الأمان (PythonAnywhere) ---
load_dotenv() 
if not os.getenv("SUPABASE_URL"):
    home_env = os.path.expanduser('/home/rimstorebot/.env')
    load_dotenv(home_env)

# --- الإعدادات الثابتة المستخرجة من حساب الشريك ---
# التوكن الخاص بكِ والذي سيتم وضعه في الرابط مباشرة حسب تعليمات الفريق
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

# --- 1. دالة إنشاء Instance (تطبيق تعليمات الفريق التقني) ---
def create_merchant_instance(phone):
    # استخدام الصيغة الموصى بها: {{partnerApiUrl}}/partner/createInstance/{{partnerToken}}
    url = f"https://api.greenapi.com/partner/createInstance/{PARTNER_TOKEN}"
    payload = {"plan": "developer"}
    headers = {"Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
            if m_id and m_token:
                # تحديث قاعدة البيانات
                supabase.table('merchants').update({"instance_id": m_id, "api_token": m_token}).eq("Phone", phone).execute()
                # ضبط الويب هوك فوراً
                requests.post(f"https://api.greenapi.com/waInstance{m_id}/setSettings/{m_token}", 
                              json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
                return m_id, m_token
        st.error(f"مخطأ في إنشاء المثيل: {res.text}")
        return None, None
    except Exception as e:
        st.error(f"عطل فني: {e}")
        return None, None

# --- 2. دالة الربط برقم الهاتف (الطريقة البديلة المضمونة) ---
def get_linking_code(m_id, m_token, phone_to_link):
    clean_phone = ''.join(filter(str.isdigit, phone_to_link))
    url = f"https://api.greenapi.com/waInstance{m_id}/getAuthorizationCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code'), None
        return None, f"مخطأ: {res.text}"
    except Exception as e:
        return None, str(e)

# --- واجهة التطبيق ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    with tab_signup:
        with st.form("signup"):
            s_m_name = st.text_input("اسم التاجر")
            s_s_name = st.text_input("اسم المحل")
            s_phone = st.text_input("رقم واتساب التاجر")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                supabase.table('merchants').insert({"Merchant_name": s_m_name, "Store_name": s_s_name, "Phone": s_phone, "password": s_pass}).execute()
                st.success("✅ تم الإنشاء!")

    with tab_login:
        with st.form("login"):
            l_phone = st.text_input("رقم واتساب")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.session_state.store_name = res.data[0].get('Store_name')
                    st.rerun()
else:
    st.title(f"🏪 لوحة تحكم: {st.session_state.store_name}")
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t1:
        with st.form("add"):
            n, p, img = st.text_input("المنتج"), st.text_input("السعر"), st.file_uploader("الصورة")
            if st.form_submit_button("حفظ"):
                im_d = f"data:image/png;base64,{base64.b64encode(img.read()).decode()}" if img else ""
                supabase.table('products').insert({"Product": n, "Price": p, "Image_url": im_d, "Phone": st.session_state.merchant_phone}).execute()
                st.success("تم الحفظ")

    with t2:
        ps = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        for x in ps.data: st.write(f"📦 {x['Product']} - {x['Price']}")

    with t3:
        os = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        for o in os.data: st.info(f"طلب من: {o['customer_phone']}")

    with t4:
        st.subheader("📲 ربط الواتساب")
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id:
            if st.button("🚀 تفعيل الآن"):
                with st.spinner("جاري إنشاء المثيل بنظام الشريك الجديد..."):
                    create_merchant_instance(st.session_state.merchant_phone)
                    st.rerun()
        else:
            col_qr, col_phone = st.columns(2)
            with col_qr:
                st.info("طريقة الـ QR")
                if st.button("🔄 إظهار رمز QR"):
                    res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/qr/{m_token}")
                    if res.status_code == 200 and res.json().get('type') == 'qrCode':
                        st.image(base64.b64decode(res.json().get('message')), width=250)
                    else: st.error("مخطأ: تعذر جلب الـ QR")

            with col_phone:
                st.info("الربط بالرقم (بديل آمن)")
                if st.button("🔑 الحصول على كود 8 أرقام"):
                    code, err = get_linking_code(m_id, m_token, st.session_state.merchant_phone)
                    if code: st.success(f"الكود: {code}")
                    else: st.error(f"مخطأ: {err}")

            if st.button("🔍 فحص الحالة"):
                res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/getStateInstance/{m_token}").json()
                st.metric("الحالة", res.get('stateInstance'))

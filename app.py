import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- الإعدادات الثابتة ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

load_dotenv() 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال: {e}")
    st.stop()

# --- 1. دالة إنشاء Instance (تعديل احترافي) ---
def create_merchant_instance(phone):
    # استخدام رابط الشريك الصحيح كما في التعليمات
    url = f"https://api.green-api.com/partner/waInstance/create/{PARTNER_KEY}"
    try:
        # طلب إنشاء المثيل
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # تحديث قاعدة البيانات فوراً (أسماء الأعمدة مطابقة لصورك)
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token,
                "session_status": "starting"
            }).eq("Phone", phone).execute()
            
            # ضبط الويب هوك تلقائياً
            set_webhook_url(m_id, m_token)
            return m_id, m_token
    except: 
        return None, None

def set_webhook_url(m_id, m_token):
    url = f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {
        "webhookUrl": WEBHOOK_URL, 
        "outgoingAPIMessage": "yes", 
        "incomingMsg": "yes",
        "deviceStatus": "yes"
    }
    requests.post(url, json=payload, timeout=10)

# --- 2. دالة جلب كود الربط الرقمي (إضافة جديدة احترافية) ---
def get_pairing_code(m_id, m_token, phone):
    # تنظيف رقم الهاتف من أي رموز زائدة
    clean_phone = ''.join(filter(str.isdigit, phone))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: 
        return None

# --- واجهة تسجيل الدخول (تبقي كما هي في كودك) ---
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
                if check.data: st.error("❌ الرقم مسجل مسبقاً!")
                elif s_merchant_name and s_store_name and s_phone and s_pass:
                    supabase.table('merchants').insert({
                        "Merchant_name": s_merchant_name, "Store_name": s_store_name, 
                        "Phone": s_phone, "password": s_pass, "session_status": "disconnected"
                    }).execute()
                    st.success("✅ تم إنشاء الحساب!")

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
                    st.session_state.m_id = res.data[0].get('instance_id')
                    st.session_state.m_token = res.data[0].get('api_token')
                    st.rerun()
                else: st.error("بيانات خاطئة")

else:
    st.title(f"🏪 متجر: {st.session_state.store_name}")
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    # تبويب المنتجات (كما هو)
    with t1:
        with st.form("add_p", clear_on_submit=True):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر")
            p_size = st.text_input("المقاس")
            p_color = st.text_input("اللون")
            p_img = st.file_uploader("صورة المنتج", type=['png','jpg'])
            if st.form_submit_button("حفظ"):
                img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                supabase.table('products').insert({
                    "Product": p_name, "Price": p_price, "Size": p_size, 
                    "Color": p_color, "Image_url": img_data, "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("تم الحفظ بنجاح!")

    # --- تبويب الربط (تطبيق الطريقة الاحترافية الجديدة) ---
    with t4:
        st.subheader("إعدادات الاتصال عبر Green-API")
        
        # التأكد من بيانات المثيل من قاعدة البيانات مباشرة
        m_res = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        m_data = m_res.data[0] if m_res.data else {}
        curr_id = m_data.get('instance_id')
        curr_token = m_data.get('api_token')

        if not curr_id:
            st.warning("⚠️ الخدمة غير مفعلة لهذا المتجر.")
            if st.button("🚀 تفعيل خدمة الواتساب وإنشاء السيرفر"):
                with st.spinner("جاري تهيئة النظام وخصم الرصيد..."):
                    new_id, new_token = create_merchant_instance(st.session_state.merchant_phone)
                    if new_id:
                        st.session_state.m_id = new_id
                        st.session_state.m_token = new_token
                        st.success("✅ تم تفعيل الخدمة وحفظ البيانات في السجل!")
                        st.rerun()
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"المثيل الحالي: {curr_id}")
                if st.button("🔢 طلب كود الربط الرقمي"):
                    with st.spinner("جاري جلب الكود من Green-API..."):
                        # انتظار بسيط لضمان جاهزية المثيل الجديد
                        time.sleep(2)
                        p_code = get_pairing_code(curr_id, curr_token, st.session_state.merchant_phone)
                        if p_code:
                            st.session_state.p_code = p_code
                            st.rerun()
                
                if 'p_code' in st.session_state:
                    st.success("أدخل الكود التالي في هاتفك:")
                    st.code(st.session_state.p_code, language="text")
                    st.write("الخطوات: واتساب > الأجهزة المرتبطة > ربط جهاز > الربط برقم الهاتف")

            with col2:
                if st.button("🔍 فحص حالة الاتصال"):
                    check_url = f"https://api.green-api.com/waInstance{curr_id}/getStateInstance/{curr_token}"
                    try:
                        state = requests.get(check_url).json().get('stateInstance')
                        st.metric("الحالة الآن", state)
                        if state == 'authorized':
                            supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", st.session_state.merchant_phone).execute()
                            st.success("✅ الهاتف متصل!")
                    except:
                        st.error("فشل التحقق من الحالة")
       

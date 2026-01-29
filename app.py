import streamlit as st
import os
import requests
import base64
import time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات الأساسية (تأكدي من وضعها في Secrets أو ملف .env) ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

load_dotenv() 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# الاتصال بـ Supabase (يتم تعريفه مرة واحدة في البداية)
try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ يرجى ضبط مفاتيح Supabase في الإعدادات!")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 2. دالات Green-API (نظام الشركاء) ---

def create_merchant_instance(phone):
    """إنشاء مثيل (Instance) جديد وحفظ بياناته في Supabase"""
    url = f"https://api.green-api.com/partner/waInstance/create/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # تحديث بيانات التاجر في قاعدة البيانات (الأعمدة: instance_id, api_token)
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token,
                "session_status": "starting"
            }).eq("Phone", phone).execute()
            
            # ضبط إعدادات الويب هوك تلقائياً
            setup_webhook(m_id, m_token)
            return m_id, m_token
    except:
        return None, None

def setup_webhook(m_id, m_token):
    """تفعيل استقبال الرسائل على الويب هوك الخاص بكِ"""
    url = f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {
        "webhookUrl": WEBHOOK_URL, 
        "outgoingAPIMessage": "yes", 
        "incomingMsg": "yes",
        "deviceStatus": "yes"
    }
    requests.post(url, json=payload, timeout=10)

def get_pairing_code(m_id, m_token, phone):
    """طلب كود الربط الرقمي (8 أرقام) من السيرفر"""
    clean_phone = ''.join(filter(str.isdigit, phone))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except:
        return None

# --- 3. نظام إدارة المستخدمين (تسجيل الدخول) ---

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    
    with tab_signup:
        with st.form("signup_form"):
            s_m_name = st.text_input("اسم التاجر")
            s_s_name = st.text_input("اسم المحل")
            s_phone = st.text_input("رقم واتساب التاجر")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                # التحقق من وجود الرقم مسبقاً
                check = supabase.table('merchants').select("Phone").eq("Phone", s_phone).execute()
                if check.data:
                    st.error("❌ هذا الرقم مسجل مسبقاً!")
                elif s_m_name and s_s_name and s_phone and s_pass:
                    supabase.table('merchants').insert({
                        "Merchant_name": s_m_name, "Store_name": s_s_name, 
                        "Phone": s_phone, "password": s_pass, "session_status": "disconnected"
                    }).execute()
                    st.success("✅ تم إنشاء الحساب بنجاح! انتقل لتسجيل الدخول.")

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
                else:
                    st.error("بيانات الدخول غير صحيحة")

else:
    # --- 4. واجهة المتجر (بعد تسجيل الدخول) ---
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل الخروج"):
        st.session_state.logged_in = False
        st.rerun()

    # إنشاء التبويبات (هنا تم تعريفها لتفادي NameError)
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t1:
        st.subheader("إضافة منتج جديد")
        with st.form("add_product", clear_on_submit=True):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر")
            p_img = st.file_uploader("صورة المنتج", type=['png','jpg'])
            if st.form_submit_button("حفظ المنتج"):
                img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                supabase.table('products').insert({
                    "Product": p_name, "Price": p_price, 
                    "Image_url": img_data, "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("✅ تم حفظ المنتج!")

    with t3:
        st.subheader("📦 الطلبات الواردة")
        # يمكن إضافة كود عرض الطلبات هنا

    with t4:
        st.subheader("📲 بوابة ربط الواتساب (Green-API)")
        
        # جلب بيانات المثيل من Supabase
        m_query = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        m_data = m_query.data[0] if m_query.data else {}
        
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        if not m_id:
            st.warning("⚠️ الخدمة غير مفعلة لهذا المتجر.")
            if st.button("🚀 تفعيل السيرفر المخصص"):
                with st.spinner("جاري إنشاء بوابتك..."):
                    new_id, new_token = create_merchant_instance(st.session_state.merchant_phone)
                    if new_id:
                        st.success("✅ تم تفعيل السيرفر!")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info(f"المعرف الخاص بك: `{m_id}`")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔢 الحصول على كود الربط الرقمي"):
                    with st.spinner("جاري طلب الكود..."):
                        p_code = get_pairing_code(m_id, m_token, st.session_state.merchant_phone)
                        if p_code:
                            st.session_state['active_pairing_code'] = p_code
                            st.rerun()
                
                # عرض الكود بشكل آمن
                if 'active_pairing_code' in st.session_state and st.session_state['active_pairing_code']:
                    st.markdown("---")
                    st.success(f"كود الربط: **{st.session_state['active_pairing_code']}**")
                    st.write("أدخل الكود في هاتفك (الأجهزة المرتبطة > ربط جهاز > الربط برقم الهاتف)")

            with col2:
                if st.button("🔍 فحص حالة الاتصال"):
                    status_url = f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}"
                    try:
                        res = requests.get(status_url, timeout=10).json()
                        state = res.get('stateInstance')
                        st.metric("الحالة", state)
                        if state == 'authorized':
                            supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", st.session_state.merchant_phone).execute()
                            st.success("✅ متصل!")
                    except:
                        st.error("فشل الاتصال بالسيرفر")
            
            st.markdown("---")
            if st.button("🗑️ حذف البيانات وإعادة الربط"):
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", st.session_state.merchant_phone).execute()
                st.session_state['active_pairing_code'] = None
                st.rerun()

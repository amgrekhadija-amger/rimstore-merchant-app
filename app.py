import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

# التنسيق الجمالي
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .code-box { font-size: 35px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center; border: 2px dashed #2196f3; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# --- 2. الوظائف التقنية ---

def register_merchant(name, store_name, phone, password):
    """إنشاء حساب تاجر جديد في قاعدة البيانات"""
    try:
        data = {
            "merchant_name": name,
            "Store_name": store_name,
            "Phone": phone,
            "password": password,
            "instance_id": None,
            "api_token": None
        }
        supabase.table('merchants').insert(data).execute()
        return True
    except Exception as e:
        st.error(f"خطأ في التسجيل: {e}")
        return False

def create_merchant_instance(phone):
    """إنشاء السيرفر وربطه فوراً بالرقم"""
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # تحديث قاعدة البيانات فوراً بالـ ID والـ Token
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            
            # ضبط الويب هوك
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except: pass
    return None, None

# --- 3. نظام الدخول والاشتراك ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["تسجيل الدخول", "إنشاء حساب تاجر جديد"])
    
    with tab_login:
        with st.form("login_form"):
            l_phone = st.text_input("رقم الواتساب")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.rerun()
                else: st.error("بيانات الدخول غير صحيحة")

    with tab_signup:
        with st.form("signup_form"):
            new_name = st.text_input("اسم التاجر")
            new_store = st.text_input("اسم المحل")
            new_phone = st.text_input("رقم الواتساب (بالصيغة الدولية مثلاً 222...)")
            new_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                if register_merchant(new_name, new_store, new_phone, new_pass):
                    st.success("تم إنشاء حسابك بنجاح! يمكنك الآن تسجيل الدخول.")

else:
    # --- 4. واجهة التاجر بعد الدخول ---
    current_phone = st.session_state.merchant_phone
    m_query = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
    merchant_data = m_query.data[0] if m_query.data else {}
    
    st.title(f"مرحباً بك، {merchant_data.get('merchant_name')}")
    st.write(f"متجر: **{merchant_data.get('Store_name')}**")

    m_id = merchant_data.get('instance_id')
    m_token = merchant_data.get('api_token')

    # فحص حالة السيرفر
    if not m_id or m_id == "None":
        st.warning("⚠️ سيرفر الواتساب غير مفعل لمتجرك.")
        if st.button("🚀 تفعيل السيرفر الآن"):
            with st.spinner("جاري تهيئة السيرفر الخاص بك..."):
                m_id, m_token = create_merchant_instance(current_phone)
                if m_id:
                    st.success("تم التفعيل! أعد المحاولة الآن لجلب الكود.")
                    st.rerun()
    else:
        st.info(f"✅ السيرفر نشط (ID: {m_id})")
        if st.button("🔢 اطلب كود الربط الآن"):
            with st.spinner("جاري استخراج الكود..."):
                # محاولة جلب كود الربط
                url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
                res = requests.post(url, json={"phoneNumber": current_phone})
                if res.status_code == 200:
                    code = res.json().get('code')
                    st.session_state.pairing_code = code
                else:
                    st.error("حدث خطأ في طلب الكود، تأكد من أن السيرفر غير مرتبط بجهاز آخر.")

        if 'pairing_code' in st.session_state:
            st.markdown(f"<div class='code-box'>{st.session_state.pairing_code}</div>", unsafe_allow_html=True)
            st.write("افتح واتساب -> الأجهزة المرتبطة -> ربط عبر رقم الهاتف وأدخل الكود أعلاه.")

    if st.button("تسجيل الخروج"):
        st.session_state.logged_in = False
        st.rerun()

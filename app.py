import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (ثابتة كما طلبتِ) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .status-card { padding: 20px; border-radius: 12px; background: #f8f9fa; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; color: black; }
    .code-box { font-size: 40px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 20px; border-radius: 12px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# --- 2. محرك العمليات ---

def create_instance(phone):
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(create_url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            supabase.table('merchants').update({"instance_id": m_id, "api_token": m_token}).eq("Phone", phone).execute()
            requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/setSettings/{m_token}", json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return True
    except: pass
    return False

def get_pairing_code_with_retry(m_id, m_token, phone):
    """محاولة الجلب أكثر من مرة لضمان عدم التعليق"""
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/logout/{m_token}")
    
    url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
    for _ in range(3): # محاولة 3 مرات في حال كان السيرفر مشغولاً
        try:
            res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
            if res.status_code == 200:
                p_code = res.json().get('code')
                if p_code:
                    supabase.table('merchants').update({"pairing_code": p_code}).eq("Phone", phone).execute()
                    return p_code
        except: pass
        time.sleep(2)
    return None

# --- 3. الدخول والجلسة ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.form("login"):
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.rerun()
    st.stop()

# --- 4. واجهة التاجر (نفس التصميم المطلوب) ---
tabs = st.tabs(["➕ إضافة منتج", "🛒 الطلبات", "📲 ربط الواتساب"])

# تبويب المنتجات (الخانات المطلوبة: اسم، رقم، سعر، صورة)
with tabs[0]:
    st.subheader("📦 إضافة منتج جديد")
    with st.form("add_p", clear_on_submit=True):
        p_name = st.text_input("اسم المنتج")
        p_code_sku = st.text_input("رقم المنتج (Code)")
        p_price = st.text_input("سعر المنتج")
        p_img = st.file_uploader("رفع صورة المنتج", type=['jpg', 'png', 'jpeg'])
        if st.form_submit_button("حفظ المنتج"):
            supabase.table('products').insert({
                "Product": p_name, 
                "Price": p_price, 
                "Phone": st.session_state.merchant_phone
            }).execute()
            st.success("✅ تم حفظ المنتج!")

# تبويب الواتساب (الإصلاح الجذري للجلب)
with tabs[2]:
    st.subheader("📲 بوابة ربط الواتساب")
    curr_phone = st.session_state.merchant_phone
    m_res = supabase.table('merchants').select("*").eq("Phone", curr_phone).execute()
    m_data = m_res.data[0] if m_res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')
    saved_code = m_data.get('pairing_code')

    if not m_id or m_id == "None":
        st.warning("سيرفرك غير مفعل حالياً.")
        if st.button("🚀 إنشاء وتفعيل السيرفر الآن"):
            with st.spinner("جاري إنشاء السيرفر..."):
                if create_instance(curr_phone):
                    st.success("تم الإنشاء! اضغط الآن على زر طلب الكود بالأسفل.")
                    time.sleep(1)
                    st.rerun()
    else:
        st.markdown(f"<div class='status-card'>✅ سيرفرك جاهز | المعرف: <b>{m_id}</b></div>", unsafe_allow_html=True)
        
        # الزر الذي سيجلب الـ 8 أرقام فوراً
        if st.button("🔢 اطلب كود الربط الآن"):
            with st.spinner("جاري جلب الكود من Green-API..."):
                code = get_pairing_code_with_retry(m_id, m_token, curr_phone)
                if code:
                    st.rerun()
                else:
                    st.error("السيرفر مشغول، حاول مرة أخرى خلال ثوانٍ.")

        if saved_code:
            st.markdown(f"<div class='code-box'>{saved_code}</div>", unsafe_allow_html=True)
            st.info(f"أدخل الكود في هاتفك المتصل بالرقم {curr_phone}")

    st.write("---")
    if st.button("🗑️ حذف وإعادة ضبط السيرفر"):
        supabase.table('merchants').update({"instance_id": None, "api_token": None, "pairing_code": None}).eq("Phone", curr_phone).execute()
        st.rerun()

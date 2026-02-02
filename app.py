import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات وتصميم الواجهة ---
load_dotenv()
# توثيق Green-API: استخدام Partner Token في الرابط
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com" 
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; background-color: #f8f9fa; }
    .status-card { padding: 20px; border-radius: 12px; background: #ffffff; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; color: black; }
    .code-box { font-size: 40px; font-family: 'Courier New', monospace; color: #075E54; background: #e3f2fd; padding: 20px; border-radius: 12px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"⚠️ خطأ في قاعدة البيانات: {e}")

# --- 2. محرك Green-API (المطابق للوثائق) ---

def create_merchant_instance(phone):
    # تطبيق التعليمات: {{partnerApiUrl}}/partner/createInstance/{{partnerToken}}
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(create_url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # حفظ البيانات في Supabase
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            
            # ضبط الإعدادات والويب هوك فوراً
            set_url = f"{PARTNER_API_URL}/waInstance{m_id}/setSettings/{m_token}"
            requests.post(set_url, json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"💥 فشل الإنشاء: {e}")
    return None, None

def fetch_pairing_code(m_id, m_token, phone):
    """جلب الكود وحفظه في الداتابيز لضمان ظهوره"""
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    # الخروج أولاً لضمان جاهزية طلب الكود
    requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/logout/{m_token}")
    
    code_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(code_url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            p_code = res.json().get('code')
            # حفظ الكود في الداتابيز (تأكدي من وجود عمود pairing_code)
            supabase.table('merchants').update({"pairing_code": p_code}).eq("Phone", phone).execute()
            return p_code
    except: pass
    return None

# --- 3. نظام الجلسة والدخول ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.form("login_form"):
        st.title("🔑 دخول التاجر - ريم ستور")
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0].get('Store_name')
                st.rerun()
            else: st.error("بيانات الدخول غير صحيحة")
    st.stop()

# --- 4. واجهة التاجر المدمجة ---
tabs = st.tabs(["➕ إضافة منتج", "🛒 الطلبات", "📲 ربط الواتساب"])

# -- تبويب المنتجات (الخانات المطلوبة كاملة) --
with tabs[0]:
    st.subheader("📦 إضافة منتج جديد للمتجر")
    with st.form("add_p_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        p_name = col1.text_input("اسم المنتج")
        p_code = col2.text_input("رقم المنتج (Code/SKU)")
        p_price = col1.text_input("السعر (أوقية)")
        p_img = col2.file_uploader("صورة المنتج", type=['jpg', 'jpeg', 'png'])
        
        if st.form_submit_button("حفظ المنتج"):
            if p_name and p_price:
                supabase.table('products').insert({
                    "Product": p_name, 
                    "Price": p_price, 
                    "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("✅ تم حفظ المنتج بنجاح!")
            else: st.warning("الرجاء ملء البيانات الأساسية")

# -- تبويب الواتساب (التطبيق الدقيق للتعليمات) --
with tabs[2]:
    st.subheader("📲 بوابة ربط الواتساب")
    curr_phone = st.session_state.merchant_phone
    
    # جلب البيانات الحالية من الداتابيز
    m_res = supabase.table('merchants').select("*").eq("Phone", curr_phone).execute()
    m_data = m_res.data[0] if m_res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')
    saved_code = m_data.get('pairing_code')

    if not m_id:
        st.info("سيرفرك غير مفعل حالياً.")
        if st.button("🚀 إنشاء وتفعيل السيرفر الآن"):
            with st.spinner("جاري إنشاء السيرفر وفق تعليمات Green-API..."):
                new_id, _ = create_merchant_instance(curr_phone)
                if new_id:
                    st.success("تم الإنشاء! يرجى الضغط مرة أخرى لجلب كود الربط.")
                    time.sleep(1)
                    st.rerun()
    else:
        st.markdown(f"<div class='status-card'>🟢 سيرفرك نشط | رقم المعرف: <b>{m_id}</b></div>", unsafe_allow_html=True)
        
        if st.button("🔢 الحصول على كود الربط (8 أرقام)"):
            with st.spinner("جاري استخراج الكود وحفظه..."):
                code = fetch_pairing_code(m_id, m_token, curr_phone)
                if code:
                    st.rerun() # لإظهار الكود المحفوظ فوراً

        if saved_code:
            st.markdown(f"<div class='code-box'>{saved_code}</div>", unsafe_allow_html=True)
            st.info(f"يرجى إدخال هذا الكود في واتساب الهاتف رقم: {curr_phone}")

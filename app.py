import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .code-box { font-size: 35px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 20px; border-radius: 12px; text-align: center; border: 2px dashed #2196f3; font-weight: bold; letter-spacing: 5px; }
    .instruction { background: #fff3cd; padding: 15px; border-radius: 8px; border-right: 5px solid #ffc107; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ خطأ اتصال: {e}")

# --- 2. المحرك التقني ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
            # حفظ في الداتابيز
            supabase.table('merchants').update({
                "instance_id": m_id, "api_token": m_token, "session_status": "starting"
            }).eq("Phone", phone).execute()
            # ضبط الويب هوك
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except: pass
    return None, None

def get_pairing_code(m_id, m_token, phone):
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- 3. إدارة حالة الجلسة (Session State) ---
# هذا الجزء هو المسؤول عن منع الاختفاء
if 'pairing_code' not in st.session_state:
    st.session_state.pairing_code = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- 4. واجهة التطبيق ---
if not st.session_state.logged_in:
    with st.form("login_form"):
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0].get('Store_name')
                st.rerun()
            else: st.error("بيانات خاطئة")
else:
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    tabs = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

    with tabs[3]:
        st.subheader("📲 بوابة ربط الواتساب")
        phone = st.session_state.merchant_phone
        
        # جلب البيانات من الداتابيز
        m_data = supabase.table('merchants').select("*").eq("Phone", phone).single().execute().data
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        if not m_id or m_id == "None":
            if st.button("🚀 تفعيل السيرفر الآن"):
                with st.spinner("جاري التفعيل..."):
                    res_id, res_token = create_merchant_instance(phone)
                    if res_id:
                        st.success("تم التفعيل! أعد الضغط لطلب الكود.")
                        st.rerun()
        else:
            st.markdown(f"<div class='status-card'>✅ السيرفر <b>{m_id}</b> نشط</div>", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔢 طلب كود الربط"):
                    with st.spinner("جاري استخراج الكود..."):
                        code = get_pairing_code(m_id, m_token, phone)
                        if code:
                            st.session_state.pairing_code = code # حفظ الكود في الذاكرة لكي لا يختفي
                
                # عرض الكود (سيبقى ظاهراً لأننا حفظناه في session_state)
                if st.session_state.pairing_code:
                    st.markdown(f"<div class='code-box'>{st.session_state.pairing_code}</div>", unsafe_allow_html=True)
                    st.markdown("""
                    <div class='instruction'>
                    <b>الخطوات:</b><br>
                    1. افتح واتساب > الأجهزة المرتبطة.<br>
                    2. اختر "ربط جهاز" ثم "الربط برقم الهاتف".<br>
                    3. أدخل الكود الظاهر أعلاه.
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                if st.button("🔄 فحص حالة الاتصال"):
                    try:
                        r = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}", timeout=10)
                        status = r.json().get('stateInstance')
                        st.metric("حالة الربط", status)
                        if status == "authorized":
                            st.success("تم الربط بنجاح!")
                            st.session_state.pairing_code = None # نمسح الكود فقط عند النجاح
                    except: st.error("فشل الفحص")

            if st.button("🗑️ إعادة ضبط"):
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", phone).execute()
                st.session_state.pairing_code = None
                st.rerun()

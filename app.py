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
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; color: black; }
    .code-box { font-size: 32px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center; border: 2px dashed #2196f3; font-weight: bold; margin: 15px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"⚠️ خطأ اتصال بـ Supabase: {e}")

# --- 2. المحرك التقني لـ Green-API ---
def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token,
                "session_status": "starting"
            }).eq("Phone", phone).execute()
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"💥 خطأ: {e}")
    return None, None

def get_pairing_code(m_id, m_token, phone):
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    # تسجيل الخروج أولاً لضمان طلب كود جديد ونظيف
    requests.post(f"https://api.green-api.com/waInstance{m_id}/logout/{m_token}")
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- 3. إدارة الجلسة والدخول ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'last_p_code' not in st.session_state: st.session_state.last_p_code = None

if not st.session_state.logged_in:
    with st.form("login"):
        st.title("🔑 دخول التاجر")
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
    st.stop()

# --- 4. واجهة التاجر ---
st.sidebar.title(f"🏪 {st.session_state.store_name}")
tabs = st.tabs(["➕ إضافة منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

with tabs[0]:
    st.subheader("📦 إضافة منتج جديد")
    with st.form("add_product", clear_on_submit=True):
        p_name = st.text_input("اسم المنتج")
        p_code = st.text_input("رقم المنتج (Code)")
        p_price = st.text_input("السعر")
        p_file = st.file_uploader("صورة المنتج", type=['jpg', 'png', 'jpeg'])
        if st.form_submit_button("حفظ المنتج"):
            supabase.table('products').insert({"Product": p_name, "Price": p_price, "Phone": st.session_state.merchant_phone}).execute()
            st.success("تم الحفظ!")

# --- قسم الواتساب المعدل لحل مشكلة عدم ظهور الكود ---
with tabs[3]:
    st.subheader("📲 بوابة ربط الواتساب")
    curr_phone = st.session_state.merchant_phone
    
    # جلب البيانات مباشرة للتأكد من الحالة
    m_res = supabase.table('merchants').select("instance_id, api_token").eq("Phone", curr_phone).execute()
    m_id = m_res.data[0].get('instance_id') if m_res.data else None
    m_token = m_res.data[0].get('api_token') if m_res.data else None

    if not m_id or m_id == "None":
        st.info("سيرفرك غير نشط.")
        if st.button("🚀 تفعيل السيرفر الآن"):
            with st.spinner("جاري التجهيز..."):
                new_id, _ = create_merchant_instance(curr_phone)
                if new_id:
                    st.success("تم التفعيل! اضغط مرة أخرى لطلب الكود.")
                    st.rerun()
    else:
        st.markdown(f"<div class='status-card'>✅ السيرفر جاهز (ID: {m_id})</div>", unsafe_allow_html=True)
        
        # زر استخراج الكود يظهر دائماً طالما السيرفر مفعل
        if st.button("🔢 استخراج كود الربط الآن"):
            with st.spinner("جاري طلب الكود من Green-API..."):
                code = get_pairing_code(m_id, m_token, curr_phone)
                if code:
                    st.session_state.last_p_code = code
                else:
                    st.error("السيرفر مشغول، حاول مرة أخرى")

        if st.session_state.last_p_code:
            st.markdown(f"<div class='code-box'>{st.session_state.last_p_code}</div>", unsafe_allow_html=True)
            st.info(f"أدخل الكود في هاتفك المتصل برقم {curr_phone}")

    if st.button("🗑️ حذف السيرفر"):
        supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", curr_phone).execute()
        st.session_state.last_p_code = None
        st.rerun()

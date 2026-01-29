import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (Premium UI) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

# إضافة CSS لتحسين المظهر
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; transition: 0.3s; }
    .stButton>button:hover { background-color: #25D366; color: white; border: none; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .code-box { font-size: 32px; font-family: 'Courier New', monospace; color: #075E54; background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center; border: 2px dashed #2196f3; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except:
    st.error("⚠️ خطأ في مفاتيح Supabase!")

# --- 2. المحرك التقني (إصلاح رابط Green-API) ---

def create_merchant_instance(phone):
    # الرابط المعتمد الجديد لتجنب خطأ 403
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # حفظ البيانات فوراً في قاعدة البيانات
            supabase.table('merchants').update({
                "instance_id": m_id, "api_token": m_token, "session_status": "starting"
            }).eq("Phone", phone).execute()
            
            # ضبط الويب هوك تلقائياً
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except: pass
    return None, None

def get_pairing_code(m_id, m_token, phone):
    # تنظيف رقم الهاتف وإرساله لطلب الكود
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- 3. نظام الجلسة والدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    t1, t2 = st.tabs(["🔐 دخول", "✨ حساب جديد"])
    with t1:
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
    # --- 4. واجهة المتجر الرئيسية ---
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

    tabs = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

    # تركيزنا هنا على تبويب الواتساب
    with tabs[3]:
        st.subheader("📲 إعدادات اتصال الواتساب")
        current_phone = st.session_state.get('merchant_phone')
        
        # جلب أحدث البيانات من Supabase
        m_data = supabase.table('merchants').select("*").eq("Phone", current_phone).single().execute().data
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        if not m_id or m_id == "None":
            st.markdown("""
            <div class='status-card' style='border-right-color: #ff4b4b;'>
                <h4>لا يوجد سيرفر نشط</h4>
                <p>يجب تفعيل السيرفر المخصص لمتجرك لتتمكن من الرد على الزبائن آلياً.</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🚀 تفعيل السيرفر الآن"):
                with st.spinner("جاري التواصل مع السيرفر..."):
                    if create_merchant_instance(current_phone)[0]:
                        st.balloons()
                        st.rerun()
        else:
            st.markdown(f"""
            <div class='status-card'>
                <h4 style='color: #25D366;'>✅ السيرفر جاهز للربط</h4>
                <p>معرف الجهاز الحالي: <b>{m_id}</b></p>
            </div>
            """, unsafe_allow_html=True)

            col_left, col_right = st.columns(2)
            
            with col_left:
                st.write("### 🔢 خطوة الربط")
                if st.button("طلب كود الربط الرقمي"):
                    with st.spinner("جاري استخراج الكود..."):
                        code = get_pairing_code(m_id, m_token, current_phone)
                        if code: st.session_state['p_code'] = code
                
                if 'p_code' in st.session_state:
                    st.markdown(f"<div class='code-box'>{st.session_state['p_code']}</div>", unsafe_allow_html=True)
                    st.info("أدخلي الكود في هاتفك: (الأجهزة المرتبطة > ربط برقم هاتف)")

            with col_right:
                st.write("### 🔍 الحالة")
                if st.button("تحديث حالة الاتصال"):
                    state = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}").json().get('stateInstance')
                    st.metric("الحالة الحالية", state)
                    if state == 'authorized':
                        st.success("الهاتف مرتبط بنجاح!")

            st.write("---")
            if st.button("🗑️ حذف البيانات والبدء من جديد"):
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", current_phone).execute()
                st.session_state.pop('p_code', None)
                st.rerun()

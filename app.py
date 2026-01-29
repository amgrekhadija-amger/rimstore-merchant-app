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
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .code-box { font-size: 32px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center; border: 2px dashed #2196f3; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ خطأ اتصال: {e}")

# --- 2. المحرك التقني مع نظام تتبع (Tracking) ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    
    # إنشاء حاوية رسائل لمعرفة ماذا يحدث خلف الكواليس
    debug_space = st.empty()
    debug_space.info("⏳ جاري إرسال الطلب إلى Green-API...")

    try:
        # تحديد وقت انتظار 15 ثانية فقط لكي لا يعلق المتصفح
        res = requests.post(url, json={"plan": "developer"}, timeout=15)
        
        debug_space.info(f"📩 استجابة السيرفر: {res.status_code}")

        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # تحديث Supabase
            supabase.table('merchants').update({
                "instance_id": m_id, "api_token": m_token, "session_status": "starting"
            }).eq("Phone", phone).execute()
            
            debug_space.success("✅ نجح التفعيل! جاري التحديث...")
            return m_id, m_token
        else:
            debug_space.error(f"❌ فشل السيرفر: {res.status_code}")
            st.write("تفاصيل الرد:", res.text)
            
    except requests.exceptions.Timeout:
        debug_space.error("⏰ انتهى وقت الانتظار! السيرفر بطيء جداً أو الرابط محجوب.")
    except Exception as e:
        debug_space.error(f"💥 خطأ تقني: {str(e)}")
        
    return None, None

def get_pairing_code(m_id, m_token, phone):
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=15)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- 3. الواجهة الرئيسية ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # (كود الدخول كما هو)
    with st.form("login"):
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0].get('Store_name')
                st.rerun()
else:
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    tabs = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

    with tabs[3]:
        st.subheader("📲 إعدادات اتصال الواتساب")
        current_phone = st.session_state.get('merchant_phone')
        
        # جلب البيانات من Supabase
        m_data = supabase.table('merchants').select("*").eq("Phone", current_phone).single().execute().data
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        if not m_id or m_id == "None":
            st.warning("⚠️ لا يوجد سيرفر نشط لمتجرك.")
            if st.button("🚀 تفعيل السيرفر الآن"):
                # استخدام spinner لا يختفي إلا بالنتيجة
                with st.spinner("انتظري قليلاً، نجهز بوابتك..."):
                    result = create_merchant_instance(current_phone)
                    if result and result[0]:
                        time.sleep(1)
                        st.rerun()
        else:
            st.markdown(f"<div class='status-card'>✅ السيرفر <b>{m_id}</b> نشط</div>", unsafe_allow_html=True)
            
            col_l, col_r = st.columns(2)
            with col_l:
                if st.button("🔢 طلب كود الربط"):
                    code = get_pairing_code(m_id, m_token, current_phone)
                    if code: st.session_state['p_code'] = code
                
                if 'p_code' in st.session_state:
                    st.markdown(f"<div class='code-box'>{st.session_state['p_code']}</div>", unsafe_allow_html=True)
                    st.info("أدخل الكود في هاتفك.")

            with col_r:
                if st.button("🔄 تحديث الحالة"):
                    res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}")
                    st.metric("حالة الربط", res.json().get('stateInstance'))

            if st.button("🗑️ حذف السيرفر"):
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", current_phone).execute()
                st.session_state.pop('p_code', None)
                st.rerun()

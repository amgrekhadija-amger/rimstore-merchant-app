import streamlit as st
import os, requests, time, base64
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (ثبات التصميم 100%) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; transition: 0.3s; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .code-box { font-size: 55px; font-family: monospace; color: #128c7e; background: #e3f2fd; padding: 20px; border-radius: 15px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; letter-spacing: 5px; margin: 20px 0; }
    .instruction-box { background: #fff3cd; padding: 15px; border-radius: 8px; border-right: 5px solid #ffc107; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"⚠️ خطأ اتصال قاعدة البيانات: {e}")

# --- 2. المحرك التقني المستقر (Green-API Settings) ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
            # تحديث الداتابيز
            supabase.table('merchants').update({"instance_id": m_id, "api_token": m_token}).eq("Phone", phone).execute()
            # إعدادات الويب هوك والرد الآلي
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes", "outgoingMsg": "yes"})
            return m_id, m_token
    except: pass
    return None, None

def get_pairing_code(m_id, m_token, phone):
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        # إرسال رقم الهاتف في Body لضمان القبول
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- 3. إدارة حالة الجلسة ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'persistent_pairing_code' not in st.session_state:
    st.session_state.persistent_pairing_code = None

# --- 4. واجهة الدخول ---
if not st.session_state.logged_in:
    st.title("🔐 ريم ستور - بوابة التاجر")
    with st.form("login_form"):
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0].get('Store_name')
                st.session_state.merchant_name = res.data[0].get('Merchant_name')
                st.rerun()
            else: st.error("❌ بيانات الدخول غير صحيحة")
    st.stop()

# --- 5. لوحة التحكم ---
st.sidebar.title(f"👋 {st.session_state.merchant_name}")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.logged_in = False
    st.session_state.persistent_pairing_code = None
    st.rerun()

tabs = st.tabs(["➕ إضافة منتج", "⚙️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

with tabs[0]:
    st.subheader("📦 إضافة منتج")
    with st.form("add_p", clear_on_submit=True):
        name = st.text_input("اسم المنتج")
        price = st.text_input("السعر")
        if st.form_submit_button("حفظ المنتج ✨"):
            supabase.table('products').insert({"Product": name, "Price": price, "Phone": st.session_state.merchant_phone, "Status": True}).execute()
            st.success("✅ تم حفظ المنتج!")

with tabs[2]:
    st.subheader("🛒 الطلبات الواردة")
    try:
        # البحث باستخدام العمود الصحيح من صورتك merchant_phc
        orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
        if orders.data:
            for o in orders.data: 
                with st.expander(f"📦 طلب من: {o.get('customer_pho')}"):
                    st.write(f"**المنتج:** {o.get('product_name')} | **السعر:** {o.get('total_price')}")
                    if st.button("✅ تم التوصيل", key=f"ord_{o.get('id')}"):
                        supabase.table('orders').delete().eq("id", o.get('id')).execute()
                        st.rerun()
        else: st.info("لا توجد طلبات جديدة.")
    except Exception as e: st.warning("تأكدي من إعدادات الجدول.")

# --- قسم الواتساب (الإعدادات الصحيحة والمستقرة) ---
with tabs[3]:
    st.subheader("📲 بوابة ربط الواتساب")
    phone = st.session_state.merchant_phone
    
    m_res = supabase.table('merchants').select("*").eq("Phone", phone).execute()
    m_data = m_res.data[0] if m_res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id or m_id == "None":
        st.warning("السيرفر غير مفعل.")
        if st.button("🚀 تفعيل السيرفر الآن"):
            with st.spinner("جاري التهيئة..."):
                create_merchant_instance(phone)
                st.rerun()
    else:
        st.markdown(f"<div class='status-card'>✅ السيرفر <b>{m_id}</b> نشط</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔢 طلب كود الربط الرقمي"):
                with st.spinner("جاري جلب الكود من Green-API..."):
                    code = get_pairing_code(m_id, m_token, phone)
                    if code:
                        st.session_state.persistent_pairing_code = code 
            
            if st.session_state.persistent_pairing_code:
                st.markdown(f"<div class='code-box'>{st.session_state.persistent_pairing_code}</div>", unsafe_allow_html=True)
                st.markdown("""
                <div class='instruction-box'>
                <b>كيفية الربط:</b><br>
                1. افتح واتساب > الأجهزة المرتبطة.<br>
                2. اختر "ربط جهاز" ثم "الربط برقم الهاتف".<br>
                3. أدخل الكود الموضح أعلاه.
                </div>
                """, unsafe_allow_html=True)

        with col2:
            if st.button("🔄 فحص حالة الاتصال"):
                try:
                    r = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}", timeout=10)
                    status = r.json().get('stateInstance')
                    st.metric("حالة الهاتف", status)
                    if status == "authorized":
                        st.success("🎉 متصل بنجاح!")
                        st.session_state.persistent_pairing_code = None 
                except: st.error("فشل الفحص.")

        if st.button("🗑️ حذف وإعادة ضبط السيرفر"):
            supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", phone).execute()
            st.session_state.persistent_pairing_code = None
            st.rerun()

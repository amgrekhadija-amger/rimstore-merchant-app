import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (تصميمك الأصلي) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" # رابط ويب هوك Botpress لاحقاً

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
    st.error(f"⚠️ خطأ اتصال: {e}")

# --- 2. المحرك التقني لطلب الكود (نفس طريقتك الناجحة) ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            supabase.table('merchants').update({
                "instance_id": m_id, "api_token": m_token
            }).eq("Phone", phone).execute()
            # ربط الويب هوك فوراً
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"💥 خطأ في إنشاء السيرفر: {e}")
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

# --- 3. نظام الجلسة والدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'last_p_code' not in st.session_state:
    st.session_state.last_p_code = None

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

# --- 4. الواجهة الموحدة (الرابط الواحد) ---
st.sidebar.title(f"🏪 {st.session_state.store_name}")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.logged_in = False
    st.rerun()

tabs = st.tabs(["➕ إدارة المنتجات", "🛒 الطلبات الواردة", "📲 ربط الواتساب"])

# -- تبويب المنتجات --
with tabs[0]:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📦 أضف منتج")
        with st.form("add_p", clear_on_submit=True):
            name = st.text_input("اسم المنتج")
            price = st.text_input("السعر (أوقية)")
            if st.form_submit_button("حفظ"):
                supabase.table('products').insert({"Product": name, "Price": price, "Phone": st.session_state.merchant_phone}).execute()
                st.success("تم الحفظ!")
                st.rerun()
    with col2:
        st.subheader("✏️ قائمة المنتجات والأسعار")
        prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        if prods.data:
            for p in prods.data:
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{p.get('Product')}** - {p.get('Price')} أوقية")
                if c2.button("🗑️", key=f"del_{p.get('id')}"):
                    supabase.table('products').delete().eq("id", p.get('id')).execute()
                    st.rerun()

# -- تبويب الطلبات --
with tabs[1]:
    st.subheader("🛒 طلبات الزبائن")
    orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
    if orders.data:
        for o in orders.data:
            st.info(f"👤 زبون: {o.get('customer_pho')} | المنتج: {o.get('product_name')}")
    else: st.write("لا توجد طلبات بعد.")

# -- تبويب الواتساب (مركز الربط الذكي) --
with tabs[2]:
    st.subheader("📲 ربط الرد الآلي بالواتساب")
    m_query = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    m_data = m_query.data[0]
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id:
        if st.button("🚀 تفعيل السيرفر لأول مرة"):
            with st.spinner("جاري التجهيز..."):
                create_merchant_instance(st.session_state.merchant_phone)
                st.rerun()
    else:
        st.markdown(f"<div class='status-card'>🟢 سيرفرك جاهز برقم: {m_id}</div>", unsafe_allow_html=True)
        
        if st.button("🔢 اطلب كود الربط الآن"):
            with st.spinner("جاري جلب الرقم من Green-API..."):
                code = get_pairing_code(m_id, m_token, st.session_state.merchant_phone)
                st.session_state.last_p_code = code

        if st.session_state.last_p_code:
            st.markdown(f"<div class='code-box'>{st.session_state.last_p_code}</div>", unsafe_allow_html=True)
            st.warning("⚠️ أدخل هذا الرقم في هاتفك (الأجهزة المرتبطة > ربط برقم الهاتف)")

        if st.button("🔄 تحديث حالة الاتصال"):
            status = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}").json().get('stateInstance')
            st.metric("حالة الهاتف الآن", status)

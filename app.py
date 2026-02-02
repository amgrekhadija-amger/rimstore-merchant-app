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
            
            # تحديث الداتابيز
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token,
                "session_status": "starting"
            }).eq("Phone", phone).execute()
            
            # ربط الويب هوك الخاص بـ Botpress
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"💥 خطأ في إنشاء السيرفر: {e}")
    return None, None

def get_pairing_code(m_id, m_token, phone):
    # تنظيف الرقم لضمان القبول
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- 3. إدارة الجلسة والدخول ---
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

# --- 4. واجهة التاجر الرئيسية ---
st.sidebar.title(f"🏪 {st.session_state.store_name}")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.logged_in = False
    st.session_state.last_p_code = None
    st.rerun()

tabs = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

# -- تبويب إضافة المنتج --
with tabs[0]:
    st.subheader("📦 إضافة منتج جديد")
    with st.form("add_product", clear_on_submit=True):
        p_name = st.text_input("اسم المنتج")
        p_price = st.text_input("السعر")
        if st.form_submit_button("حفظ المنتج"):
            supabase.table('products').insert({
                "Product": p_name, 
                "Price": p_price, 
                "Phone": st.session_state.merchant_phone
            }).execute()
            st.success("تمت الإضافة بنجاح!")

# -- تبويب إدارة المنتجات --
with tabs[1]:
    st.subheader("✏️ قائمة منتجاتك")
    prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    if prods.data:
        for p in prods.data:
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{p.get('Product')}** - {p.get('Price')} أوقية")
            if c2.button("🗑️", key=f"del_p_{p.get('id')}"):
                supabase.table('products').delete().eq("id", p.get('id')).execute()
                st.rerun()

# -- تبويب الطلبات --
with tabs[2]:
    st.subheader("🛒 الطلبات الواردة")
    try:
        orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
        if orders.data:
            for o in orders.data:
                with st.expander(f"📦 طلب من: {o.get('customer_pho')}"):
                    st.write(f"المنتج: {o.get('product_name')}")
                    if st.button("✅ تم التوصيل (حذف)", key=f"del_o_{o.get('id')}"):
                        supabase.table('orders').delete().eq("id", o.get('id')).execute()
                        st.rerun()
        else: st.info("لا توجد طلبات حالياً.")
    except: st.warning("تأكد من جدول الطلبات")

# -- تبويب الواتساب (الكود الناجح والمدمج) --
with tabs[3]:
    st.subheader("📲 بوابة ربط الواتساب")
    curr_phone = st.session_state.merchant_phone
    
    # جلب بيانات السيرفر
    m_query = supabase.table('merchants').select("*").eq("Phone", curr_phone).execute()
    m_data = m_query.data[0] if m_query.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id or m_id == "None":
        st.info("سيرفر الواتساب غير مفعل.")
        if st.button("🚀 تفعيل السيرفر الآن"):
            with st.spinner("جاري التجهيز..."):
                new_id, new_token = create_merchant_instance(curr_phone)
                if new_id:
                    st.success("تم التفعيل!")
                    time.sleep(2)
                    st.rerun()
    else:
        st.markdown(f"<div class='status-card'>✅ سيرفرك نشط برقم: <b>{m_id}</b></div>", unsafe_allow_html=True)
        
        col_l, col_r = st.columns(2)
        with col_l:
            st.write("### 1. طلب كود الربط")
            if st.button("🔢 استخراج الكود"):
                with st.spinner("جاري الطلب..."):
                    p_code = get_pairing_code(m_id, m_token, curr_phone)
                    if p_code:
                        st.session_state.last_p_code = p_code
                    else:
                        st.error("فشل طلب الكود")

            # عرض الكود من الـ session_state لضمان ثباته
            if st.session_state.last_p_code:
                st.markdown(f"<div class='code-box'>{st.session_state.last_p_code}</div>", unsafe_allow_html=True)
                st.info(f"أدخل الكود في هاتفك المتصل بالرقم: {curr_phone}")

        with col_r:
            st.write("### 2. فحص الاتصال")
            if st.button("🔄 تحديث الحالة"):
                try:
                    res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}", timeout=10)
                    status = res.json().get('stateInstance')
                    st.metric("الحالة الآن", status)
                except: st.error("عطل في الاتصال")

        st.write("---")
        if st.button("🗑️ حذف وإعادة ضبط السيرفر"):
            if st.checkbox("تأكيد الحذف"):
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", curr_phone).execute()
                st.session_state.last_p_code = None
                st.rerun()

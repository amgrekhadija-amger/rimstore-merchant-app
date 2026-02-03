import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (أصلية تماماً) ---
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
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- 2. المحرك التقني المستقر (كودك الأصلي حرفياً) ---
def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            supabase.table('merchants').update({"instance_id": m_id, "api_token": m_token}).eq("Phone", phone).execute()
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

# --- 3. نظام تسجيل الدخول وإنشاء الحساب (الخانات المطلوبة) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_log, tab_reg = st.tabs(["🔐 دخول", "📝 إنشاء حساب"])
    with tab_reg:
        with st.form("reg"):
            n, s, p, pw = st.text_input("اسم التاجر"), st.text_input("اسم المحل"), st.text_input("رقم الهاتف"), st.text_input("السر", type="password")
            if st.form_submit_button("فتح الحساب"):
                supabase.table('merchants').insert({"Merchant_name": n, "Store_name": s, "Phone": p, "password": pw}).execute()
                st.success("تم!")
    with tab_log:
        with st.form("login"):
            u_p, u_w = st.text_input("الرقم"), st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", u_p).eq("password", u_w).execute()
                if res.data:
                    st.session_state.logged_in, st.session_state.merchant_phone, st.session_state.store_name = True, u_p, res.data[0].get('Store_name')
                    st.rerun()

else:
    # --- 4. واجهة التاجر (كودك الأصلي مع الخانات الجديدة) ---
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل الخروج"):
        st.session_state.logged_in = False
        st.rerun()

    tabs = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

    with tabs[0]: # خانات المنتج كاملة
        with st.form("add"):
            st.write("### إضافة منتج جديد")
            p_n, p_p = st.text_input("الاسم"), st.text_input("السعر")
            p_c, p_s, p_i = st.text_input("الألوان"), st.text_input("مقاس"), st.text_input("رابط الصورة")
            if st.form_submit_button("حفظ"):
                supabase.table('products').insert({"Product": p_n, "Price": p_p, "Color": p_c, "Size": p_s, "Image_url": p_i, "Phone": st.session_state.merchant_phone}).execute()
                st.success("تم الحفظ!")

    # --- تبويب الواتساب (نفس هيكلية كودك الناجح بالضبط) ---
    with tabs[3]:
        st.subheader("📲 بوابة ربط الواتساب")
        current_phone = st.session_state.get('merchant_phone')
        m_query = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
        m_data = m_query.data[0] if m_query.data else {}
        m_id, m_token = m_data.get('instance_id'), m_data.get('api_token')

        if not m_id:
            if st.button("🚀 تفعيل السيرفر"):
                create_merchant_instance(current_phone)
                st.rerun()
        else:
            st.markdown(f"<div class='status-card'>✅ سيرفرك نشط: <b>{m_id}</b></div>", unsafe_allow_html=True)
            col_l, col_r = st.columns(2)
            
            with col_l:
                if st.button("🔢 استخراج الكود"):
                    p_code = get_pairing_code(m_id, m_token, current_phone)
                    if p_code:
                        # حفظ في الداتابيز وفي الجلسة لضمان الظهور
                        supabase.table('merchants').update({"pairing_code": p_code}).eq("Phone", current_phone).execute()
                        st.session_state['last_p_code'] = p_code
                        st.session_state['expiry'] = time.time() + 30

                # عرض الكود (هنا السر: لا يختفي إلا بعد 30 ثانية)
                if 'last_p_code' in st.session_state:
                    rem = int(st.session_state['expiry'] - time.time())
                    if rem > 0:
                        st.markdown(f"<div class='code-box'>{st.session_state['last_p_code']}</div>", unsafe_allow_html=True)
                        st.caption(f"يختفي بعد {rem} ثانية")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.session_state.pop('last_p_code', None)

            with col_r:
                if st.button("🔄 تحديث الحالة"):
                    res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}")
                    st.metric("حالة الهاتف", res.json().get('stateInstance'))

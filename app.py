import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (أصلية 100%) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

# الاتصال بـ Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 2. المحرك التقني المستقر (كودك الناجح كما هو) ---
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

# --- 3. نظام تسجيل الدخول وإنشاء الحساب ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    auth_tab, reg_tab = st.tabs(["🔐 دخول", "📝 فتح حساب جديد"])
    
    with reg_tab:
        with st.form("registration"):
            st.write("### انضم لـ ريم ستور")
            new_m_name = st.text_input("اسم التاجر")
            new_s_name = st.text_input("اسم المحل")
            new_phone = st.text_input("رقم الهاتف")
            new_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء حسابي"):
                supabase.table('merchants').insert({
                    "Merchant_name": new_m_name, "Store_name": new_s_name, 
                    "Phone": new_phone, "password": new_pass
                }).execute()
                st.success("🎉 تم التسجيل بنجاح! يمكنك الدخول الآن.")

    with auth_tab:
        with st.form("login_form"):
            u_phone = st.text_input("الرقم")
            u_pw = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = u_phone
                    st.session_state.store_name = res.data[0].get('Store_name')
                    st.rerun()
                else: st.error("❌ بيانات خاطئة")

else:
    # --- 4. لوحة تحكم التاجر المدمجة ---
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 خروج"):
        st.session_state.logged_in = False
        st.rerun()

    tabs = st.tabs(["➕ إضافة منتج", "✏️ إدارة السعر", "🛒 الطلبات", "📲 واتساب"])

    with tabs[0]:
        st.subheader("📦 إضافة منتج جديد")
        with st.form("product_form"):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("سعر المنتج")
            p_colors = st.text_input("الألوان")
            p_size = st.text_input("مقاس")
            p_img = st.text_input("رابط صورة المنتج")
            if st.form_submit_button("حفظ"):
                supabase.table('products').insert({
                    "Product": p_name, "Price": p_price, "Color": p_colors, 
                    "Size": p_size, "Image_url": p_img, "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("تم الحفظ!")

    with tabs[1]:
        st.subheader("✏️ تعديل الأسعار والتوفر")
        p_res = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        for p in p_res.data:
            with st.expander(f"تعديل: {p['Product']}"):
                new_val = st.text_input("السعر", p['Price'], key=f"p_{p['id']}")
                is_on = st.checkbox("متوفر حالياً", value=p.get('Status', True), key=f"s_{p['id']}")
                if st.button("تحديث السعر", key=f"b_{p['id']}"):
                    supabase.table('products').update({"Price": new_val, "Status": is_on}).eq("id", p['id']).execute()
                    st.rerun()

    with tabs[2]:
        st.subheader("🛒 قائمة الطلبات")
        o_res = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        st.table(o_res.data)

    with tabs[3]:
        st.subheader("📲 بوابة الواتساب (ثبات 30 ثانية)")
        m_q = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        m_d = m_q.data[0] if m_q.data else {}
        m_id, m_tok = m_d.get('instance_id'), m_d.get('api_token')

        if not m_id:
            if st.button("🚀 تفعيل السيرفر"):
                create_merchant_instance(st.session_state.merchant_phone)
                st.rerun()
        else:
            if st.button("🔢 استخراج كود الربط"):
                code = get_pairing_code(m_id, m_tok, st.session_state.merchant_phone)
                if code:
                    # حفظ في الداتابيز وتثبيت العرض
                    supabase.table('merchants').update({"pairing_code": code}).eq("Phone", st.session_state.merchant_phone).execute()
                    st.session_state.view_code = code
                    st.session_state.timer = time.time() + 30
                    st.rerun()

            if 'view_code' in st.session_state:
                rem = int(st.session_state.timer - time.time())
                if rem > 0:
                    st.markdown(f"<div style='text-align:center; background:#e3f2fd; padding:30px; border-radius:15px; border:2px solid #2196f3;'><h1 style='color:#075E54; font-size:60px;'>{st.session_state.view_code}</h1><p>يختفي الكود بعد {rem} ثانية</p></div>", unsafe_allow_html=True)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.session_state.pop('view_code', None)

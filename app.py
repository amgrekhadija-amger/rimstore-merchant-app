import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (بدون تغيير) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

# الاتصال بـ Supabase
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"⚠️ خطأ اتصال: {e}")

# --- 2. المحرك التقني المستقر (كودك الأصلي كما هو) ---
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
            code = res.json().get('code')
            # التعديل المطلوب: حفظ الكود في الداتابيز (بدون تغيير منطق الربط)
            supabase.table('merchants').update({"pairing_code": code}).eq("Phone", phone).execute()
            return code
    except: pass
    return None

# --- 3. نظام إدارة الحسابات (جديد) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    menu = st.sidebar.selectbox("القائمة", ["تسجيل دخول", "إنشاء حساب جديد"])
    
    if menu == "إنشاء حساب جديد":
        st.subheader("📝 إنشاء حساب تاجر جديد")
        with st.form("register"):
            m_name = st.text_input("اسم التاجر")
            s_name = st.text_input("اسم المحل")
            phone = st.text_input("رقم الهاتف")
            pwd = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                supabase.table('merchants').insert({
                    "Merchant_name": m_name, "Store_name": s_name, 
                    "Phone": phone, "password": pwd
                }).execute()
                st.success("تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.")

    else:
        st.subheader("🔐 تسجيل دخول التاجر")
        with st.form("login"):
            u_phone = st.text_input("رقم التاجر")
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
    # --- 4. واجهة التاجر مع التبويبات المطلوبة ---
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل خروج"):
        st.session_state.logged_in = False
        st.rerun()

    tabs = st.tabs(["➕ إضافة منتج", "✏️ إدارة المنتجات", "🛒 الطلبات", "📲 واتساب"])

    # تبويب إضافة المنتجات
    with tabs[0]:
        st.subheader("📦 إضافة منتج جديد")
        with st.form("add_product"):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("سعر المنتج")
            p_colors = st.text_input("الألوان")
            p_size = st.text_input("المقاس")
            p_img = st.text_input("رابط صورة المنتج") # أو رفع ملف
            if st.form_submit_button("حفظ المنتج"):
                supabase.table('products').insert({
                    "Product": p_name, "Price": p_price, "Color": p_colors, 
                    "Size": p_size, "Image_url": p_img, "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("تمت إضافة المنتج بنجاح!")

    # تبويب إدارة السعر والتوفر
    with tabs[1]:
        st.subheader("✏️ إدارة أسعار وتوفر المنتجات")
        prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        for p in prods.data:
            col1, col2, col3 = st.columns(3)
            with col1: st.write(p['Product'])
            with col2: new_price = st.text_input("السعر", p['Price'], key=f"p_{p['id']}")
            with col3: available = st.checkbox("متوفر", value=p.get('Status', True), key=f"s_{p['id']}")
            if st.button("تحديث", key=f"b_{p['id']}"):
                supabase.table('products').update({"Price": new_price, "Status": available}).eq("id", p['id']).execute()
                st.rerun()

    # تبويب الطلبات
    with tabs[2]:
        st.subheader("🛒 الطلبات الواردة من واتساب")
        orders = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        if orders.data:
            st.table(orders.data)
        else:
            st.info("لا توجد طلبات جديدة حالياً.")

    # تبويب واتساب (كودك الأصلي تماماً مع تعديل الـ 30 ثانية)
    with tabs[3]:
        st.subheader("📲 بوابة ربط الواتساب")
        m_query = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        m_data = m_query.data[0] if m_query.data else {}
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        if not m_id or m_id == "None":
            if st.button("🚀 تفعيل السيرفر الآن"):
                create_merchant_instance(st.session_state.merchant_phone)
                st.rerun()
        else:
            st.write(f"✅ سيرفرك: {m_id}")
            if st.button("🔢 استخراج الكود"):
                p_code = get_pairing_code(m_id, m_token, st.session_state.merchant_phone)
                if p_code:
                    placeholder = st.empty()
                    # عد تنازلي 30 ثانية كما طلبتِ
                    for i in range(30, 0, -1):
                        placeholder.markdown(f"<div style='font-size:40px; text-align:center; background:#e3f2fd; padding:10px;'>{p_code} <br> <small>ينتهي خلال {i} ثانية</small></div>", unsafe_allow_html=True)
                        time.sleep(1)
                    placeholder.empty()
                    st.warning("انتهت مدة الكود، يرجى الطلب مرة أخرى.")

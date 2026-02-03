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
try:
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ خطأ اتصال: {e}")

# --- 2. المحرك التقني المستقر (نفس منطقك الأصلي 100%) ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            supabase.table('merchants').update({
                "instance_id": m_id, "api_token": m_token, "session_status": "starting"
            }).eq("Phone", phone).execute()
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
            # التعديل المطلوب: حفظ الكود في الداتابيز فور استلامه
            supabase.table('merchants').update({"pairing_code": code}).eq("Phone", phone).execute()
            return code
    except: pass
    return None

# --- 3. نظام الجلسة ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # القائمة الجانبية للتنقل بين الدخول والتسجيل
    menu = st.sidebar.selectbox("القائمة", ["تسجيل دخول", "إنشاء حساب جديد"])
    
    if menu == "إنشاء حساب جديد":
        with st.form("register_form"):
            st.subheader("📝 إنشاء حساب تاجر")
            m_name = st.text_input("اسم التاجر")
            s_name = st.text_input("اسم المحل")
            phone = st.text_input("رقم الهاتف")
            pwd = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("فتح الحساب"):
                supabase.table('merchants').insert({"Merchant_name": m_name, "Store_name": s_name, "Phone": phone, "password": pwd}).execute()
                st.success("تم بنجاح! يمكنك الدخول الآن.")
    else:
        with st.form("login"):
            st.subheader("🔐 دخول التاجر")
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
    # واجهة التاجر بعد الدخول
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل خروج"):
        st.session_state.logged_in = False
        st.rerun()

    tabs = st.tabs(["➕ إضافة منتج", "✏️ إدارة السعر", "🛒 الطلبات", "📲 واتساب"])

    with tabs[0]:
        st.subheader("📦 إضافة منتج جديد")
        with st.form("add_p"):
            p_n = st.text_input("اسم المنتج")
            p_p = st.text_input("سعر المنتج")
            p_c = st.text_input("الألوان")
            p_s = st.text_input("مقاس")
            p_i = st.text_input("رفع صورة (رابط)")
            if st.form_submit_button("حفظ المنتج"):
                supabase.table('products').insert({"Product": p_n, "Price": p_p, "Color": p_c, "Size": p_s, "Image_url": p_i, "Phone": st.session_state.merchant_phone}).execute()
                st.success("تم الحفظ!")

    with tabs[1]:
        st.subheader("✏️ إدارة السعر والتوفر")
        prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        for p in prods.data:
            with st.expander(f"تعديل: {p['Product']}"):
                new_price = st.text_input("تغيير السعر", p['Price'], key=f"p_{p['id']}")
                is_avail = st.selectbox("الحالة", ["متوفر", "غير متوفر"], key=f"s_{p['id']}")
                if st.button("تحديث", key=f"b_{p['id']}"):
                    supabase.table('products').update({"Price": new_price, "Status": is_avail}).eq("id", p['id']).execute()
                    st.rerun()

    with tabs[2]:
        st.subheader("🛒 الطلبات الواردة")
        # يتم عرض الطلبات التي تضاف للداتابيز من الواتساب
        orders = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        st.table(orders.data)

    with tabs[3]:
        # --- هذا هو كودك الأصلي بحذافيره مع تعديل الـ 30 ثانية المضمون ---
        st.subheader("📲 بوابة ربط الواتساب")
        current_phone = st.session_state.get('merchant_phone')
        m_query = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
        m_data = m_query.data[0] if m_query.data else {}
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        if not m_id or m_id == "None":
            st.info("لم يتم تفعيل السيرفر بعد.")
            if st.button("🚀 تفعيل السيرفر الآن"):
                create_merchant_instance(current_phone)
                st.rerun()
        else:
            st.markdown(f"<div class='status-card'>✅ سيرفر متجرك نشط برقم: <b>{m_id}</b></div>", unsafe_allow_html=True)
            col_l, col_r = st.columns(2)
            
            with col_l:
                st.write("### 1. طلب كود الربط")
                if st.button("🔢 استخراج الكود"):
                    p_code = get_pairing_code(m_id, m_token, current_phone)
                    if p_code:
                        # استخدام حلقة عرض مباشرة لضمان بقاء الكود 30 ثانية
                        placeholder = st.empty()
                        for i in range(30, 0, -1):
                            placeholder.markdown(f"<div class='code-box'>{p_code}</div><p style='text-align:center'>⏱️ يختفي خلال {i} ثانية</p>", unsafe_allow_html=True)
                            time.sleep(1)
                        placeholder.empty()

            with col_r:
                st.write("### 2. فحص الاتصال")
                if st.button("🔄 تحديث حالة الهاتف"):
                    check_res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}")
                    st.metric("الحالة الآن", check_res.json().get('stateInstance'))

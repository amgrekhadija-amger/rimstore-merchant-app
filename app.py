import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (ثابتة تماماً) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

# الاتصال بـ Supabase (تأكدي من وجود الخيارات في Secrets)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 2. المحرك التقني المستقر (كودك الأصلي دون تغيير) ---
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

# --- 3. نظام الجلسة وتسجيل الدخول/الخروج ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# زر تسجيل الخروج في الجانب (Sidebar) ليكون متاحاً دائماً بعد الدخول
if st.session_state.logged_in:
    if st.sidebar.button("🚪 تسجيل الخروج"):
        st.session_state.logged_in = False
        st.rerun()

if not st.session_state.logged_in:
    tab_login, tab_register = st.tabs(["🔐 تسجيل دخول", "📝 إنشاء حساب جديد"])
    
    # مكان إنشاء حساب جديد
    with tab_register:
        with st.form("reg_form"):
            reg_name = st.text_input("اسم التاجر")
            reg_store = st.text_input("اسم المحل")
            reg_phone = st.text_input("رقم الهاتف")
            reg_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                supabase.table('merchants').insert({
                    "Merchant_name": reg_name, "Store_name": reg_store, 
                    "Phone": reg_phone, "password": reg_pass
                }).execute()
                st.success("تم إنشاء الحساب بنجاح! توجه لتبويب تسجيل الدخول.")

    # مكان تسجيل الدخول
    with tab_login:
        with st.form("login_form"):
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
    # واجهة التاجر
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    tabs = st.tabs(["➕ إضافة منتج", "✏️ إدارة السعر", "🛒 الطلبات", "📲 واتساب"])

    # تبويب إضافة منتجات (كل الخانات المطلوبة)
    with tabs[0]:
        st.subheader("📦 إضافة منتج جديد")
        with st.form("add_prod"):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("سعر المنتج")
            p_colors = st.text_input("الألوان")
            p_size = st.text_input("مقاس")
            p_img = st.file_uploader("رفع صورة المنتج", type=['png', 'jpg', 'jpeg'])
            if st.form_submit_button("حفظ المنتج"):
                # هنا يتم الحفظ في جدول products
                supabase.table('products').insert({
                    "Product": p_name, "Price": p_price, "Color": p_colors, 
                    "Size": p_size, "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("تم حفظ المنتج!")

    # تبويب إدارة السعر والتوفر
    with tabs[1]:
        st.subheader("✏️ إدارة أسعار وتوفر المنتجات")
        prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        for p in prods.data:
            with st.expander(f"تعديل: {p['Product']}"):
                new_p = st.text_input("تغيير السعر", value=p['Price'], key=f"price_{p['id']}")
                is_avail = st.selectbox("الحالة", ["متوفر", "غير متوفر"], 
                                      index=0 if p.get('Status') else 1, key=f"stat_{p['id']}")
                if st.button("تحديث البيانات", key=f"btn_{p['id']}"):
                    supabase.table('products').update({
                        "Price": new_p, "Status": (is_avail == "متوفر")
                    }).eq("id", p['id']).execute()
                    st.rerun()

    # تبويب الطلبات (الواردة من واتساب)
    with tabs[2]:
        st.subheader("🛒 طلبات واتساب")
        orders = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        st.table(orders.data)

    # تبويب واتساب (تعديل الـ 30 ثانية والحفظ)
    with tabs[3]:
        st.subheader("📲 بوابة ربط الواتساب")
        m_query = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        m_data = m_query.data[0] if m_query.data else {}
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        if not m_id or m_id == "None":
            if st.button("🚀 تفعيل السيرفر"):
                create_merchant_instance(st.session_state.merchant_phone)
                st.rerun()
        else:
            if st.button("🔢 استخراج كود الربط"):
                p_code = get_pairing_code(m_id, m_token, st.session_state.merchant_phone)
                if p_code:
                    # 1. حفظ الكود في الداتابيز فوراً
                    supabase.table('merchants').update({"pairing_code": p_code}).eq("Phone", st.session_state.merchant_phone).execute()
                    
                    # 2. إظهار الكود لمدة 30 ثانية مع عداد
                    stop_time = time.time() + 30
                    placeholder = st.empty()
                    while time.time() < stop_time:
                        remaining = int(stop_time - time.time())
                        placeholder.markdown(f"""
                        <div style='text-align:center; background:#e3f2fd; padding:20px; border-radius:10px; border:2px solid #2196f3;'>
                            <h1 style='color:#075E54; font-size:50px;'>{p_code}</h1>
                            <p>هذا الكود سينتهي ويختفي خلال <b>{remaining}</b> ثانية</p>
                        </div>
                        """, unsafe_allow_html=True)
                        time.sleep(1)
                    placeholder.empty()
                    st.warning("انتهى وقت الكود. إذا لم يتم الربط، اطلب كوداً جديداً.")

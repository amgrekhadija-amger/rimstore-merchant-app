import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات ---
load_dotenv()
# تأكدي من وضع القيم الصحيحة في ملف .env أو استبدالها هنا مباشرة
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .code-box { font-size: 32px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center; border: 2px dashed #2196f3; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    # يفضل استخدام os.getenv ولكن سأتركها هكذا لتعمل مع إعداداتك
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ خطأ اتصال بـ Supabase: {e}")

# --- 2. المحرك التقني (وظائف API) ---

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
            # ضبط الإعدادات والويب هوك
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"خطأ في إنشاء السيرفر: {e}")
    return None, None

def get_pairing_code(m_id, m_token, phone):
    # تنظيف الرقم (ضروري جداً لنجاح العملية)
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            code = res.json().get('code')
            # حفظ الكود في الداتابيز (إختياري ولكن مفيد)
            try:
                supabase.table('merchants').update({"pairing_code": code}).eq("Phone", phone).execute()
            except: pass 
            return code
    except Exception as e:
        print(f"Error fetching code: {e}")
    return None

# --- 3. نظام الجلسة والواجهة ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    menu = st.sidebar.selectbox("القائمة", ["تسجيل دخول", "إنشاء حساب جديد"])
    
    if menu == "إنشاء حساب جديد":
        with st.form("register_form"):
            st.subheader("📝 إنشاء حساب تاجر")
            m_name = st.text_input("اسم التاجر")
            s_name = st.text_input("اسم المحل")
            phone = st.text_input("رقم الهاتف (بصيغة 966...)")
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
    # لوحة التحكم
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل خروج"):
        st.session_state.logged_in = False
        st.rerun()

    tabs = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

    # --- تبويبات الإدارة (مختصرة للتركيز على الواتساب) ---
    with tabs[0]:
        st.subheader("📦 إضافة منتج")
        with st.form("add_p"):
            p_n = st.text_input("الاسم"); p_p = st.text_input("السعر")
            if st.form_submit_button("حفظ"):
                supabase.table('products').insert({"Product": p_n, "Price": p_p, "Phone": st.session_state.merchant_phone}).execute()
                st.success("تم!")

    with tabs[2]:
        st.subheader("🛒 الطلبات")
        orders = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        st.table(orders.data)

    # --- تبويب الواتساب (التعديل المطلوب) ---
    with tabs[3]:
        st.subheader("📲 بوابة ربط الواتساب")
        current_phone = st.session_state.merchant_phone
        
        m_query = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
        m_data = m_query.data[0] if m_query.data else {}
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        if not m_id or m_id == "None":
            st.warning("لم يتم تفعيل السيرفر.")
            if st.button("🚀 تفعيل السيرفر الآن"):
                with st.spinner("جاري تهيئة السيرفر..."):
                    create_merchant_instance(current_phone)
                    st.rerun()
        else:
            st.markdown(f"<div class='status-card'>✅ سيرفرك نشط: <b>{m_id}</b></div>", unsafe_allow_html=True)
            
            col_l, col_r = st.columns(2)
            with col_l:
                st.write("### 1. طلب كود الربط")
                if st.button("🔢 استخراج الكود"):
                    with st.spinner("جاري جلب الكود..."):
                        p_code = get_pairing_code(m_id, m_token, current_phone)
                    
                    if p_code:
                        # العرض باستخدام placeholder لضمان التحديث اللحظي
                        code_placeholder = st.empty()
                        time_placeholder = st.empty()
                        
                        for i in range(30, 0, -1):
                            code_placeholder.markdown(f"<div class='code-box'>{p_code}</div>", unsafe_allow_html=True)
                            time_placeholder.info(f"⏳ أدخل الكود في هاتفك (الأجهزة المرتبطة). يختفي خلال {i} ثانية")
                            time.sleep(1)
                        
                        code_placeholder.empty()
                        time_placeholder.warning("⚠️ انتهى الوقت. اطلب كوداً جديداً إذا لم تكتمل العملية.")
                    else:
                        st.error("تعذر جلب الكود. تأكد أن الرقم هو نفس رقم واتساب الهاتف.")

            with col_r:
                st.write("### 2. الحالة")
                if st.button("🔄 تحديث الحالة"):
                    res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}")
                    status = res.json().get('stateInstance')
                    st.metric("حالة الاتصال", status)
                    if status == "authorized": st.success("تم الربط بنجاح!")

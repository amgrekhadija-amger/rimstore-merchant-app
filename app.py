import streamlit as st
import os, requests, time, base64
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات ---
load_dotenv()
# مفاتيح التشغيل
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"
PARTNER_API_URL = "https://api.green-api.com"

# الاتصال بـ Supabase
try:
    # يحاول الجلب من secrets (للموقع) أو من البيئة المحلية
    SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ خطأ اتصال بقاعدة البيانات: {e}")

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

# تحسين المظهر
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .code-box { font-size: 55px; font-family: monospace; color: #128c7e; background: #e3f2fd; padding: 20px; border-radius: 15px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; margin: 20px 0; }
    .instruction { background: #fff3cd; padding: 15px; border-radius: 8px; border-right: 5px solid #ffc107; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. المحرك التقني لربط الواتساب ---

def start_full_connection(phone):
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    try:
        # 1. إنشاء المثيل (Instance)
        response = requests.post(create_url, json={"plan": "developer"}, timeout=30)
        if response.status_code == 200:
            data = response.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
            
            # 2. حفظ البيانات فوراً في الداتابيز
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            
            # 3. ضبط الإعدادات والويب هوك للرد الآلي
            requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            
            time.sleep(3) # انتظار التفعيل في السيرفر
            
            # 4. طلب كود الربط
            clean_phone = ''.join(filter(str.isdigit, str(phone)))
            pairing_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
            p_res = requests.post(pairing_url, json={"phoneNumber": clean_phone}, timeout=20)
            
            if p_res.status_code == 200:
                return m_id, p_res.json().get('code')
    except Exception as e:
        st.error(f"خطأ في عملية الربط: {e}")
    return None, None

# --- 3. إدارة الجلسة والدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'pairing_code' not in st.session_state:
    st.session_state.pairing_code = None

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
                st.session_state.merchant_name = res.data[0].get('Merchant_name')
                st.rerun()
            else: st.error("بيانات الدخول خاطئة")
    st.stop()

# --- 4. واجهة التطبيق الرئيسية ---
st.sidebar.title(f"👋 {st.session_state.merchant_name}")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.logged_in = False
    st.rerun()

t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "⚙️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

# قسم 1: إضافة المنتجات
with t1:
    st.subheader("📦 أضف منتجاً جديداً")
    with st.form("add_p", clear_on_submit=True):
        p_name = st.text_input("اسم المنتج")
        p_price = st.text_input("السعر")
        p_img = st.file_uploader("صورة المنتج", type=['png', 'jpg'])
        if st.form_submit_button("حفظ المنتج"):
            img_b64 = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
            supabase.table('products').insert({
                "Product": p_name, "Price": p_price, "Image_url": img_b64, 
                "Phone": st.session_state.merchant_phone, "Status": True
            }).execute()
            st.success("✅ تم حفظ المنتج!")

# قسم 3: الطلبات (مع حماية من الأخطاء)
with t3:
    st.subheader("🛒 طلبات الزبائن")
    try:
        orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
        if orders.data:
            for o in orders.data:
                st.info(f"📱 زبون: {o.get('customer_pho')} | المنتج: {o.get('product_name')}")
        else:
            st.info("لا توجد طلبات حالياً.")
    except:
        st.warning("⚠️ تأكدي من ضبط أذونات (Policies) جدول الطلبات في Supabase.")

# قسم 4: ربط الواتساب الاحترافي
with t4:
    st.subheader("📲 بوابة اتصال الواتساب")
    # جلب بيانات المثيل الحالية من الداتابيز
    m_data = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).single().execute().data
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id or m_id == "None":
        st.warning("لم يتم تفعيل سيرفر الواتساب لمتجرك بعد.")
        if st.button("🚀 تفعيل السيرفر وطلب الكود الآن"):
            with st.spinner("جاري إنشاء السيرفر..."):
                res_id, code = start_full_connection(st.session_state.merchant_phone)
                if code:
                    st.session_state.pairing_code = code
                    st.rerun()
    else:
        st.markdown(f"<div class='status-card'>✅ السيرفر الحالي: <b>{m_id}</b> نشط</div>", unsafe_allow_html=True)
        
        col_l, col_r = st.columns(2)
        with col_l:
            if st.button("🔢 طلب كود ربط جديد"):
                with st.spinner("جاري استخراج الكود..."):
                    clean_ph = ''.join(filter(str.isdigit, str(st.session_state.merchant_phone)))
                    p_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
                    res = requests.post(p_url, json={"phoneNumber": clean_ph})
                    if res.status_code == 200:
                        st.session_state.pairing_code = res.json().get('code')

            if st.session_state.pairing_code:
                st.markdown(f"<div class='code-box'>{st.session_state.pairing_code}</div>", unsafe_allow_html=True)
                st.markdown("""
                <div class='instruction'>
                <b>طريقة الربط:</b><br>
                1. اذهب للواتساب > الأجهزة المرتبطة.<br>
                2. اختر "ربط جهاز" ثم "الربط برقم الهاتف".<br>
                3. أدخل الكود الموضح أعلاه.
                </div>
                """, unsafe_allow_html=True)

        with col_r:
            if st.button("🔄 فحص حالة الاتصال"):
                try:
                    r = requests.get(f"{PARTNER_API_URL}/waInstance{m_id}/getStateInstance/{m_token}", timeout=10)
                    status = r.json().get('stateInstance')
                    st.metric("حالة الربط", status)
                    if status == "authorized": 
                        st.success("الجهاز مرتبط ويعمل!")
                        st.session_state.pairing_code = None
                except: st.error("تعذر الاتصال بالسيرفر.")

        if st.button("🗑️ إعادة ضبط الاتصال"):
            supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", st.session_state.merchant_phone).execute()
            st.session_state.pairing_code = None
            st.rerun()

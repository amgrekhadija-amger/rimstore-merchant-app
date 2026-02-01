import streamlit as st
import os, requests, time, base64
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (نفس التصميم الأصلي تماماً) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

# الحفاظ على الـ CSS الخاص بكِ دون تغيير
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; transition: 0.3s; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .code-box { font-size: 55px; font-family: 'Courier New', monospace; color: #128c7e; background: #e3f2fd; padding: 20px; border-radius: 15px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; margin: 20px 0; letter-spacing: 5px; }
    .step-box { background: #fff3cd; padding: 15px; border-radius: 8px; border-right: 5px solid #ffc107; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ فشل الاتصال بقاعدة البيانات.")

# --- 2. المحرك التقني لربط الواتساب (نسخة خديجة المستقرة) ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
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

# --- 3. إدارة الجلسة (Session State) ---
if 'pairing_code' not in st.session_state:
    st.session_state.pairing_code = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

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
                st.session_state.merchant_name = res.data[0].get('Merchant_name')
                st.rerun()
            else: st.error("❌ البيانات غير صحيحة")
    st.stop()

# --- 5. لوحة التحكم الرئيسية ---
st.sidebar.title(f"👋 {st.session_state.merchant_name}")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.logged_in = False
    st.rerun()

t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "⚙️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

# قسم 1: إضافة المنتجات
with t1:
    st.subheader("📦 أضف منتجاً لمتجرك")
    with st.form("add_p", clear_on_submit=True):
        p_name = st.text_input("اسم المنتج")
        p_price = st.text_input("السعر")
        p_img = st.file_uploader("صورة المنتج", type=['png', 'jpg', 'jpeg'])
        if st.form_submit_button("حفظ المنتج ✨"):
            img_b64 = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
            supabase.table('products').insert({
                "Product": p_name, "Price": p_price, "Image_url": img_b64, 
                "Phone": st.session_state.merchant_phone, "Status": True
            }).execute()
            st.success("✅ تمت الإضافة!")

# قسم 2: إدارة المنتجات
with t2:
    st.subheader("⚙️ إدارة منتجاتك")
    prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    for p in prods.data:
        with st.expander(f"📦 {p['Product']} - {p['Price']}"):
            if st.button("حذف المنتج", key=f"delp_{p['id']}"):
                supabase.table('products').delete().eq("id", p['id']).execute()
                st.rerun()

# قسم 3: الطلبات (باستخدام الأعمدة التي أرسلتِها في الصورة)
with t3:
    st.subheader("🛒 طلبات الزبائن")
    try:
        # هنا استخدمنا merchant_phc كما في صورتك تماماً
        orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
        if orders.data:
            for o in orders.data:
                st.info(f"📱 زبون: {o.get('customer_pho')} | المنتج: {o.get('product_name')}")
                if st.button("✅ تم التوصيل", key=f"ord_{o.get('id')}"):
                    supabase.table('orders').delete().eq("id", o.get('id')).execute()
                    st.rerun()
        else: st.info("لا توجد طلبات جديدة.")
    except Exception as e:
        st.error(f"تأكدي من إعدادات الجدول: {e}")

# قسم 4: ربط الواتساب (التصميم الأصلي + استقرار الكود)
with t4:
    st.subheader("📲 إعدادات بوت الواتساب")
    m_data = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).single().execute().data
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id or m_id == "None":
        st.warning("سيرفر الرد الآلي غير مفعل.")
        if st.button("🚀 تفعيل السيرفر"):
            with st.spinner("جاري التفعيل..."):
                res_id, res_token = create_merchant_instance(st.session_state.merchant_phone)
                if res_id: st.rerun()
    else:
        st.markdown(f"<div class='status-card'>✅ السيرفر الخاص بك <b>{m_id}</b> نشط</div>", unsafe_allow_html=True)
        
        col_l, col_r = st.columns(2)
        with col_l:
            if st.button("🔢 الحصول على كود ربط جديد"):
                with st.spinner("جاري استخراج الكود..."):
                    code = get_pairing_code(m_id, m_token, st.session_state.merchant_phone)
                    if code: st.session_state.pairing_code = code
            
            if st.session_state.pairing_code:
                st.markdown(f"<div class='code-box'>{st.session_state.pairing_code}</div>", unsafe_allow_html=True)
                st.markdown("""
                <div class='step-box'>
                    <b>خطوات الربط:</b><br>
                    1. افتح واتساب > الأجهزة المرتبطة > ربط جهاز.<br>
                    2. اختر الربط برقم الهاتف وأدخل الكود أعلاه.
                </div>
                """, unsafe_allow_html=True)

        with col_r:
            if st.button("🔄 فحص حالة الاتصال"):
                try:
                    state_res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}")
                    status = state_res.json().get('stateInstance')
                    st.metric("حالة الهاتف", status)
                    if status == "authorized": 
                        st.success("متصل!")
                        st.session_state.pairing_code = None
                except: st.error("خطأ في الاتصال.")

        if st.button("🗑️ إعادة ضبط الاتصال"):
            supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", st.session_state.merchant_phone).execute()
            st.session_state.pairing_code = None
            st.rerun()

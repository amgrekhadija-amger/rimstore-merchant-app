import streamlit as st
import os, requests, time, base64
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (Premium UI) ---
load_dotenv()
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"
PARTNER_API_URL = "https://api.green-api.com"

# الاتصال بـ Supabase (استخدام st.secrets للهاتف أو os.getenv للمحلي)
try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ فشل الاتصال بقاعدة البيانات. تأكدي من المفاتيح!")

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

# تحسين المظهر بالـ CSS
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; transition: 0.3s; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .code-box { font-size: 60px; font-family: 'Courier New', monospace; color: #128c7e; background: #e3f2fd; padding: 20px; border-radius: 15px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; margin: 20px 0; }
    .step-box { background: #fff3cd; padding: 15px; border-radius: 8px; border-right: 5px solid #ffc107; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. المحرك التقني لربط الواتساب ---

def start_full_connection(phone):
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    try:
        response = requests.post(create_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
            
            # حفظ في الداتابيز
            supabase.table('merchants').update({"instance_id": m_id, "api_token": m_token}).eq("Phone", phone).execute()
            
            # إعداد الويب هوك للرد الآلي
            requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            
            time.sleep(3) # انتظار التفعيل
            clean_phone = ''.join(filter(str.isdigit, str(phone)))
            pairing_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_phone}"
            p_res = requests.get(pairing_url, timeout=20)
            if p_res.status_code == 200:
                p_code = p_res.json().get('code')
                return m_id, p_code
    except Exception as e:
        st.error(f"خطأ اتصال: {e}")
    return None, None

# --- 3. إدارة الجلسة والدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_p_code' not in st.session_state:
    st.session_state.current_p_code = None

if not st.session_state.logged_in:
    st.title("🔐 ريم ستور - بوابة التاجر")
    t_login, t_signup = st.tabs(["تسجيل دخول", "إنشاء حساب جديد"])
    
    with t_signup:
        with st.form("signup_form"):
            n_name = st.text_input("اسمك الكريم")
            n_store = st.text_input("اسم متجرك")
            n_phone = st.text_input("رقم هاتفك")
            n_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("فتح الحساب ✨"):
                supabase.table('merchants').insert({"Merchant_name": n_name, "Store_name": n_store, "Phone": n_phone, "password": n_pass}).execute()
                st.success("✅ مبروك! تم إنشاء حسابك بنجاح.")
    
    with t_login:
        with st.form("login_form"):
            l_phone = st.text_input("رقم الهاتف")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.session_state.merchant_name = res.data[0]['Merchant_name']
                    st.rerun()
                else: st.error("❌ البيانات غير صحيحة")
    st.stop()

# --- 4. لوحة التحكم الرئيسية ---
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
        p_price = st.text_input("السعر (مثال: 500 أوقية)")
        p_size = st.text_input("المقاس")
        p_desc = st.text_area("وصف قصير")
        p_img = st.file_uploader("صورة المنتج", type=['png', 'jpg', 'jpeg'])
        if st.form_submit_button("حفظ المنتج"):
            img_b64 = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
            supabase.table('products').insert({
                "Product": p_name, "Price": p_price, "Size": p_size, 
                "description": p_desc, "Image_url": img_b64, 
                "Phone": st.session_state.merchant_phone, "Status": True
            }).execute()
            st.success("✅ تمت إضافة المنتج للمتجر!")

# قسم 2: إدارة المخزون
with t2:
    st.subheader("⚙️ إدارة منتجاتك")
    prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    for p in prods.data:
        with st.expander(f"📦 {p['Product']} - {p['Price']}"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_p = st.text_input("تعديل السعر", value=p['Price'], key=f"p_{p['created_at']}")
                if st.button("تحديث", key=f"bp_{p['created_at']}"):
                    supabase.table('products').update({"Price": new_p}).eq("created_at", p['created_at']).execute()
                    st.rerun()
            with col_b:
                st.write(f"الحالة: {'✅ متوفر' if p['Status'] else '❌ غير متوفر'}")
                if st.button("تبديل الحالة", key=f"bs_{p['created_at']}"):
                    supabase.table('products').update({"Status": not p['Status']}).eq("created_at", p['created_at']).execute()
                    st.rerun()

# قسم 3: الطلبات
with t3:
    st.subheader("🛒 طلبات الزبائن")
    orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
    if orders.data:
        for o in orders.data:
            st.info(f"📱 زبون: {o.get('customer_pho')} | المنتج: {o.get('product_name')}")
            if st.button("✅ تم التوصيل", key=f"ord_{o.get('created_at')}"):
                supabase.table('orders').delete().eq("created_at", o.get('created_at')).execute()
                st.rerun()
    else:
        st.info("لا توجد طلبات جديدة حالياً.")

# --- قسم 4: ربط الواتساب الاحترافي (المعالج) ---
with t4:
    st.subheader("📲 إعدادات بوت الواتساب")
    res = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    
    if res.data:
        merchant = res.data[0]
        m_id = merchant.get('instance_id')
        m_token = merchant.get('api_token')

        # الحالة 1: السيرفر غير مفعل
        if not m_id or m_id == "None":
            st.warning("سيرفر الرد الآلي غير مفعل لمتجرك.")
            if st.button("🚀 تفعيل البوت وطلب كود الربط"):
                with st.spinner("جاري التواصل مع Green-API..."):
                    m_id_new, code = start_full_connection(st.session_state.merchant_phone)
                    if code:
                        st.session_state.current_p_code = code
                        st.rerun()

        # الحالة 2: السيرفر موجود (واجهة الربط)
        else:
            st.markdown(f"<div class='status-card'>✅ السيرفر الخاص بك <b>{m_id}</b> نشط</div>", unsafe_allow_html=True)
            
            col_l, col_r = st.columns(2)
            with col_l:
                if st.button("🔢 الحصول على كود ربط جديد"):
                    with st.spinner("جاري استخراج الكود..."):
                        clean_ph = ''.join(filter(str.isdigit, str(st.session_state.merchant_phone)))
                        p_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_ph}"
                        st.session_state.current_p_code = requests.get(p_url).json().get('code')
                
                # إظهار الكود بشكل كبير وواضح لكي لا يختفي
                if st.session_state.current_p_code:
                    st.markdown(f"<div class='code-box'>{st.session_state.current_p_code}</div>", unsafe_allow_html=True)
                    st.markdown("""
                    <div class='step-box'>
                        <b>خطوات الربط:</b><br>
                        1. افتح واتساب على هاتفك.<br>
                        2. الأجهزة المرتبطة > ربط جهاز.<br>
                        3. اختر <b>الربط برقم الهاتف</b>.<br>
                        4. أدخل الكود الظاهر أعلاه.
                    </div>
                    """, unsafe_allow_html=True)

            with col_r:
                if st.button("🔄 فحص حالة الاتصال"):
                    try:
                        state_res = requests.get(f"{PARTNER_API_URL}/waInstance{m_id}/getStateInstance/{m_token}")
                        status = state_res.json().get('stateInstance')
                        st.metric("حالة الهاتف الآن", status)
                        if status == "authorized": st.success("تم الربط بنجاح! البوت يعمل.")
                    except: st.error("السيرفر لا يستجيب.")

            if st.button("🗑️ إعادة ضبط الاتصال"):
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", st.session_state.merchant_phone).execute()
                st.session_state.current_p_code = None
                st.rerun()

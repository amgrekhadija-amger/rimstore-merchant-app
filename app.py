import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (نفس التصميم الذي طلبتِهِ) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .code-box { font-size: 32px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center; border: 2px dashed #2196f3; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"⚠️ خطأ اتصال: {e}")

# --- 2. المحرك التقني المستقر (نفس طريقتك الناجحة حرفياً) ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token, 
                "session_status": "starting"
            }).eq("Phone", phone).execute()
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"💥 عطل فني: {str(e)}")
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

# --- 3. نظام الجلسة ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- 4. واجهة الدخول ---
if not st.session_state.logged_in:
    with st.form("login"):
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

# --- 5. واجهة التاجر المدمجة ---
st.sidebar.title(f"🏪 {st.session_state.store_name}")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.logged_in = False
    st.session_state.pop('last_p_code', None)
    st.rerun()

tabs = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

# قسم إضافة المنتج
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

# قسم الطلبات (محدث ليعمل مع جداولك merchant_phc)
with tabs[2]:
    st.subheader("🛒 الطلبات الواردة")
    try:
        orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
        if orders.data:
            for o in orders.data:
                with st.expander(f"📦 طلب من: {o.get('customer_pho')}"):
                    st.write(f"المنتج: {o.get('product_name')}")
                    if st.button("✅ تم التوصيل (حذف)", key=f"del_{o.get('id')}"):
                        supabase.table('orders').delete().eq("id", o.get('id')).execute()
                        st.rerun()
        else: st.info("لا توجد طلبات.")
    except: st.warning("تأكد من وجود عمود merchant_phc في جدول orders")

# --- قسم الواتساب (نفس طريقتك الناجحة حرفياً دون تغيير) ---
with tabs[3]:
    st.subheader("📲 بوابة ربط الواتساب")
    current_phone = st.session_state.get('merchant_phone')
    
    m_query = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
    m_data = m_query.data[0] if m_query.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id or m_id == "None":
        st.info("لم يتم تفعيل سيرفر الواتساب لمتجرك بعد.")
        if st.button("🚀 تفعيل السيرفر الآن"):
            with st.spinner("جاري إنشاء السيرفر الخاص بك..."):
                new_id, new_token = create_merchant_instance(current_phone)
                if new_id:
                    st.success(f"تم إنشاء السيرفر بنجاح!")
                    time.sleep(2)
                    st.rerun()
    else:
        st.markdown(f"<div class='status-card'>✅ سيرفر متجرك نشط برقم: <b>{m_id}</b></div>", unsafe_allow_html=True)
        
        st.write("---")
        col_l, col_r = st.columns(2)
        
        with col_l:
            st.write("### 1. طلب كود الربط")
            if st.button("🔢 استخراج الكود"):
                with st.spinner("جاري جلب الكود..."):
                    p_code = get_pairing_code(m_id, m_token, current_phone)
                    if p_code:
                        st.session_state['last_p_code'] = p_code
                    else:
                        st.error("فشل طلب الكود.")

            if 'last_p_code' in st.session_state:
                st.markdown(f"<div class='code-box'>{st.session_state['last_p_code']}</div>", unsafe_allow_html=True)
                st.markdown(f"""
                **خطوات الربط في هاتفك:**
                1. افتح واتساب على هاتفك (**{current_phone}**).
                2. اذهب لـ **الأجهزة المرتبطة** > **ربط جهاز**.
                3. اختر **الربط برقم الهاتف بدلاً من ذلك**.
                4. أدخل الكود الظاهر أعلاه.
                """)

        with col_r:
            st.write("### 2. فحص الاتصال")
            if st.button("🔄 تحديث حالة الهاتف"):
                try:
                    check_res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}", timeout=10)
                    status = check_res.json().get('stateInstance')
                    st.metric("حالة الهاتف الآن", status)
                    if status == "authorized":
                        st.success("🎉 مبروك! متجرك مرتبط.")
                except:
                    st.error("السيرفر لا يستجيب.")

        st.write("---")
        if st.button("🗑️ حذف وإعادة ضبط السيرفر"):
            if st.checkbox("أؤكد رغبتي في الحذف"):
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", current_phone).execute()
                st.session_state.pop('last_p_code', None)
                st.rerun()

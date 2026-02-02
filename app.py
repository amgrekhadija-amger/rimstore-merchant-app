import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والتصميم ---
load_dotenv()
# ملاحظة: استبدلي الرابط أدناه برابط الـ Webhook الخاص بـ Botpress لاحقاً
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; background-color: #f0f2f6; }
    .status-card { padding: 20px; border-radius: 12px; background: #ffffff; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; color: #1a1a1a; }
    .code-box { font-size: 38px; font-family: 'Courier New', monospace; color: #075E54; background: #e3f2fd; padding: 20px; border-radius: 10px; text-align: center; border: 3px dashed #2196f3; font-weight: bold; margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"⚠️ خطأ اتصال بـ Supabase: {e}")

# --- 2. محرك Green-API المطور ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            # حفظ البيانات فوراً في قاعدة البيانات
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            # ضبط الويب هوك (Webhook)
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"💥 عطل في إنشاء السيرفر: {str(e)}")
    return None, None

def get_pairing_code(m_id, m_token, phone):
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    # التعديل: تسجيل الخروج أولاً لضمان جاهزية طلب الكود
    try:
        requests.post(f"https://api.green-api.com/waInstance{m_id}/logout/{m_token}", timeout=5)
    except: pass
    
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
        else:
            st.error(f"فشل السيرفر في إصدار الكود: {res.text}")
    except Exception as e:
        st.error(f"خطأ تقني: {str(e)}")
    return None

# --- 3. نظام إدارة الجلسة والدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'last_p_code' not in st.session_state:
    st.session_state.last_p_code = None

if not st.session_state.logged_in:
    with st.form("login"):
        st.title("🔑 دخول التاجر - ريم ستور")
        u_phone = st.text_input("رقم الهاتف (بصيغة 222xxxxxxx)")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0].get('Store_name')
                st.rerun()
            else: st.error("بيانات الدخول غير صحيحة")
    st.stop()

# --- 4. واجهة التحكم الرئيسية ---
st.sidebar.title(f"🏪 {st.session_state.store_name}")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.logged_in = False
    st.session_state.last_p_code = None
    st.rerun()

tabs = st.tabs(["➕ إضافة منتج", "✏️ إدارة المتجر", "🛒 الطلبات", "📲 ربط الواتساب"])

# -- قسم المنتجات والطلبات (مختصر للاختبار) --
with tabs[0]:
    st.subheader("📦 أضف منتجاتك هنا")
    # (كود إضافة المنتجات الخاص بكِ يوضع هنا)

with tabs[2]:
    st.subheader("🛒 قائمة الطلبات الواردة")
    # (كود عرض الطلبات من Supabase يوضع هنا)

# --- 5. قسم الواتساب (التعديل المطور والشامل) ---
with tabs[3]:
    st.subheader("📲 بوابة ربط الواتساب الذكية")
    m_phone = st.session_state.merchant_phone
    
    # جلب أحدث بيانات السيرفر
    m_query = supabase.table('merchants').select("*").eq("Phone", m_phone).execute()
    m_data = m_query.data[0] if m_query.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id or m_id == "None":
        st.info("سيرفر الواتساب الخاص بك غير مفعل حالياً.")
        if st.button("🚀 إنشاء وتفعيل السيرفر الآن"):
            with st.spinner("جاري التواصل مع Green-API..."):
                new_id, _ = create_merchant_instance(m_phone)
                if new_id:
                    st.success("تم إنشاء السيرفر! يمكنك الآن طلب كود الربط.")
                    time.sleep(2)
                    st.rerun()
    else:
        st.markdown(f"<div class='status-card'>🟢 سيرفرك جاهز للاستخدام | رقم المعرف: <b>{m_id}</b></div>", unsafe_allow_html=True)
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.write("### 1️⃣ الحصول على الكود")
            if st.button("🔢 طلب كود الربط الآن"):
                with st.spinner("جاري استخراج الكود..."):
                    p_code = get_pairing_code(m_id, m_token, m_phone)
                    if p_code:
                        st.session_state.last_p_code = p_code
                    else:
                        st.error("لم نتمكن من جلب الكود، يرجى المحاولة مرة أخرى.")

            if st.session_state.last_p_code:
                st.markdown(f"<div class='code-box'>{st.session_state.last_p_code}</div>", unsafe_allow_html=True)
                st.info("أدخل هذا الكود في هاتفك: (واتساب > الأجهزة المرتبطة > ربط برقم الهاتف)")

        with col_right:
            st.write("### 2️⃣ فحص الاتصال")
            if st.button("🔄 تحديث الحالة"):
                try:
                    res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}", timeout=10)
                    status = res.json().get('stateInstance')
                    st.metric("حالة الهاتف الآن", status)
                    if status == "authorized":
                        st.balloons()
                        st.success("🎉 مبروك! هاتفك مرتبط بنجاح والرد الآلي يعمل.")
                except:
                    st.error("السيرفر لا يستجيب، حاول لاحقاً.")

        st.write("---")
        if st.button("🗑️ حذف السيرفر الحالي"):
            if st.checkbox("أؤكد رغبتي في مسح بيانات الربط"):
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", m_phone).execute()
                st.session_state.last_p_code = None
                st.rerun()

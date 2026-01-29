import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات (UI) ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; transition: 0.3s; }
    .stButton>button:hover { background-color: #25D366; color: white; border: none; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .code-box { font-size: 35px; font-family: 'Courier New', monospace; color: #075E54; background: #e3f2fd; padding: 20px; border-radius: 12px; text-align: center; border: 2px dashed #2196f3; margin: 15px 0; font-weight: bold; letter-spacing: 5px; }
    .instruction-step { background: #fff3cd; padding: 15px; border-radius: 8px; border-right: 5px solid #ffc107; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ خطأ في الاتصال بـ Supabase: {e}")

# --- 2. المحرك التقني المستقر ---

def create_merchant_instance(phone):
    # استخدام رابط Partner API الصحيح لتجنب 403
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # تحديث قاعدة البيانات فوراً لضمان الاستقرار
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token, 
                "session_status": "starting"
            }).eq("Phone", phone).execute()
            
            # إعداد الويب هوك تلقائياً للرد الآلي
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"💥 عطل أثناء الإنشاء: {e}")
    return None, None

def get_pairing_code(m_id, m_token, phone):
    # تنظيف رقم الهاتف وإرساله لطلب كود الربط الرقمي
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- 3. نظام الجلسة والدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    t1, t2 = st.tabs(["🔐 دخول", "✨ حساب جديد"])
    with t1:
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
                else: st.error("بيانات الدخول خاطئة")
else:
    # --- 4. واجهة التاجر الرئيسية ---
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("🚪 تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

    tabs = st.tabs(["➕ منتج", "✏️ إدارة", "🛒 طلبات", "📲 واتساب"])

    with tabs[3]:
        st.subheader("📲 بوابة ربط الواتساب")
        current_phone = st.session_state.get('merchant_phone')
        
        # جلب أحدث البيانات من Supabase لضمان الثبات
        m_query = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
        m_data = m_query.data[0] if m_query.data else {}
        m_id = m_data.get('instance_id')
        m_token = m_data.get('api_token')

        # الحالة 1: لا يوجد سيرفر مفعل
        if not m_id or m_id == "None":
            st.info("سيرفر متجرك غير نشط حالياً. اضغطي على الزر لبدء التفعيل.")
            if st.button("🚀 تفعيل السيرفر الآن"):
                with st.spinner("جاري إنشاء بوابتك الخاصة..."):
                    new_id, new_token = create_merchant_instance(current_phone)
                    if new_id:
                        st.success(f"تم إنشاء السيرفر بنجاح! رقم الجهاز: {new_id}")
                        time.sleep(2)
                        st.rerun()

        # الحالة 2: السيرفر موجود (واجهة الربط الثابتة)
        else:
            st.markdown(f"""
            <div class='status-card'>
                <h4 style='color: #25D366; margin:0;'>✅ سيرفر متجرك نشط</h4>
                <p style='margin:0;'>المعرف الخاص بك: <b>{m_id}</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            col_l, col_r = st.columns(2)
            
            with col_l:
                st.write("### 🔢 خطوة الربط")
                if st.button("الحصول على كود الربط"):
                    with st.spinner("جاري طلب الكود من السيرفر..."):
                        p_code = get_pairing_code(m_id, m_token, current_phone)
                        if p_code:
                            st.session_state['fixed_p_code'] = p_code
                
                # إظهار الكود بشكل ثابت لكي لا يختفي عند أي تحديث
                if 'fixed_p_code' in st.session_state:
                    st.markdown(f"<div class='code-box'>{st.session_state['fixed_p_code']}</div>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div class='instruction-step'>
                        <b>⚠️ كيفية الربط في هاتفك:</b><br>
                        1. افتح واتساب (رقم {current_phone}).<br>
                        2. الإعدادات > الأجهزة المرتبطة > ربط جهاز.<br>
                        3. اختر <b>الربط برقم الهاتف بدلاً من ذلك</b>.<br>
                        4. أدخل الكود الظاهر أعلاه.
                    </div>
                    """, unsafe_allow_html=True)

            with col_r:
                st.write("### 🔍 فحص الحالة")
                if st.button("🔄 تحديث حالة الهاتف"):
                    try:
                        res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}", timeout=10)
                        status = res.json().get('stateInstance')
                        st.metric("حالة الربط الحالية", status)
                        if status == "authorized":
                            st.balloons()
                            st.success("تم الاتصال بنجاح! البوت جاهز للعمل.")
                    except:
                        st.error("السيرفر لا يستجيب حالياً.")

            st.write("---")
            if st.button("🗑️ إعادة ضبط وحذف السيرفر"):
                if st.checkbox("أؤكد رغبتي في مسح بيانات السيرفر الحالية"):
                    supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", current_phone).execute()
                    st.session_state.pop('fixed_p_code', None)
                    st.rerun()

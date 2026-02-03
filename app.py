import streamlit as st
import requests, time
from supabase import create_client

# 1. الإعدادات الرسمية (تأكدي من صحة هذه البيانات في Streamlit Secrets)
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
API_URL = "https://api.green-api.com"

# 2. الاتصال بـ Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- دالة التشخيص وجلب الكود ---
def diagnose_and_pair(m_id, m_token, phone):
    logs = []
    try:
        # فحص حالة السيرفر
        state_res = requests.get(f"{API_URL}/waInstance{m_id}/getStateInstance/{m_token}")
        logs.append(f"🔍 حالة السيرفر الحالية: {state_res.json().get('stateInstance', 'unknown')}")
        
        # تسجيل الخروج لتنظيف الجلسة المعلقة
        requests.post(f"{API_URL}/waInstance{m_id}/logout/{m_token}")
        time.sleep(4)
        
        # طلب كود الربط
        pair_res = requests.post(f"{API_URL}/waInstance{m_id}/getPairingCode/{m_token}", json={"phoneNumber": phone})
        if pair_res.status_code == 200:
            return True, pair_res.json().get('code'), logs
        else:
            logs.append(f"❌ فشل جلب الكود من السيرفر: {pair_res.text}")
            return False, None, logs
    except Exception as e:
        logs.append(f"⚠️ خطأ فني: {str(e)}")
        return False, None, logs

# --- صفحة تسجيل الدخول ---
def login_page():
    st.title("🔐 تسجيل الدخول - ريم ستور")
    with st.form("login_form"):
        u_phone = st.text_input("رقم الهاتف المسجل")
        u_pass = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            # البحث في قاعدة البيانات
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pass).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.merchant_name = res.data[0].get('Merchant_name') # استخدام الاسم الصحيح
                st.rerun()
            else:
                st.error("❌ رقم الهاتف أو كلمة السر غير صحيحة")

# --- بوابة الربط والتشخيص ---
def pairing_gate(phone):
    st.title(f"👋 مرحباً {st.session_state.merchant_name}")
    st.subheader("📲 بوابة ربط الواتساب")

    # جلب بيانات السيرفر الحالية
    res = supabase.table('merchants').select("*").eq("Phone", phone).execute()
    m_data = res.data[0] if res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    # المرحلة 1: الإنشاء إذا لم يوجد idInstance
    if not m_id or m_id == "None":
        st.warning("ليس لديك سيرفر نشط حالياً.")
        if st.button("🚀 إنشاء وتفعيل سيرفر جديد"):
            with st.spinner("جاري إنشاء السيرفر وحفظ idInstance..."):
                c_res = requests.post(f"{API_URL}/partner/createInstance/{PARTNER_TOKEN}", json={"plan": "developer"})
                if c_res.status_code == 200:
                    d = c_res.json()
                    supabase.table('merchants').update({
                        "instance_id": str(d['idInstance']), 
                        "api_token": d['apiTokenInstance']
                    }).eq("Phone", phone).execute()
                    st.success("تم الإنشاء! يرجى تحديث الصفحة.")
                    st.rerun()
        return

    # المرحلة 2: التشخيص وجلب الكود
    st.info(f"📦 سيرفرك الحالي: {m_id}")
    if st.button("🔢 جلب كود الربط + تشخيص"):
        with st.spinner("جاري التحليل والطلب..."):
            success, code, logs = diagnose_and_pair(m_id, m_token, phone)
            
            with st.expander("📝 لماذا لا يجلب الكود؟ (تقرير التشخيص)"):
                for log in logs:
                    st.write(log)
            
            if success:
                supabase.table('merchants').update({"pairing_code": code}).eq("Phone", phone).execute()
                st.session_state.pairing_code = code
                st.success("✅ تم جلب الكود بنجاح!")
                st.rerun()

    # عرض الكود
    display_code = st.session_state.get('pairing_code') or m_data.get('pairing_code')
    if display_code:
        st.markdown(f"<div style='text-align:center; background:#f0f9ff; padding:20px; border:2px solid #007bff; border-radius:15px;'><h1 style='color:#075E54;'>{display_code}</h1><p>أدخل الكود في واتساب للرقم: {phone}</p></div>", unsafe_allow_html=True)

    if st.sidebar.button("تسجيل خروج"):
        st.session_state.logged_in = False
        st.rerun()

# --- تشغيل التطبيق ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    pairing_gate(st.session_state.merchant_phone)

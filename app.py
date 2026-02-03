import streamlit as st
import requests, time
from supabase import create_client

# 1. الإعدادات الرسمية
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
API_URL = "https://api.green-api.com"

# 2. اتصال Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# 3. دالة جلب الكود (السيناريو الموصى به)
def get_whatsapp_code(m_id, m_token, phone):
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    # محاولة تنظيف الجلسة أولاً
    requests.post(f"{API_URL}/waInstance{m_id}/logout/{m_token}")
    time.sleep(2)
    
    url = f"{API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: return None
    return None

# --- واجهة المستخدم (بوابة الربط الاحترافية) ---
st.title("📲 بوابة الربط الاحترافية")

if 'merchant_phone' not in st.session_state:
    st.error("يرجى تسجيل الدخول.")
    st.stop()

current_phone = st.session_state.merchant_phone

# جلب البيانات باستخدام الأسماء الصحيحة التي ظهرت في صورتك
try:
    # استخدام .execute() لتفادي خطأ APIError الظاهر في صورتك
    res = supabase.table('merchants').select("*").eq("Phone", current_phone).execute()
    m_data = res.data[0] if res.data else {}
except Exception as e:
    st.error(f"خطأ في قراءة الجدول: {e}")
    st.stop()

m_id = m_data.get('instance_id')
m_token = m_data.get('api_token')
p_code = m_data.get('pairing_code')

# عرض الواجهة بناءً على حالة السيرفر
if not m_id or m_id == "None":
    st.info("سيرفرك غير مفعل.")
    if st.button("🚀 إنشاء سيرفر جديد"):
        with st.spinner("جاري إنشاء السيرفر..."):
            create_res = requests.post(f"{API_URL}/partner/createInstance/{PARTNER_TOKEN}", json={"plan": "developer"})
            if create_res.status_code == 200:
                d = create_res.json()
                # التحديث في Supabase باستخدام الأعمدة الصحيحة من صورتك
                supabase.table('merchants').update({
                    "instance_id": str(d['idInstance']), 
                    "api_token": d['apiTokenInstance']
                }).eq("Phone", current_phone).execute()
                st.success("تم إنشاء السيرفر بنجاح!")
                time.sleep(1)
                st.rerun()
else:
    st.success(f"✅ السيرفر الحالي نشط برقم: {m_id}")
    
    if st.button("🔢 اطلب كود الربط الرقمي"):
        with st.spinner("جاري جلب الكود..."):
            code = get_whatsapp_code(m_id, m_token, current_phone)
            if code:
                # حفظ الكود في عمود pairing_code كما في صورتك
                supabase.table('merchants').update({"pairing_code": code}).eq("Phone", current_phone).execute()
                st.session_state.last_code = code
                st.rerun()

    # عرض الكود الرقمي في المربع الأزرق
    final_display = st.session_state.get('last_code') or p_code
    if final_display:
        st.markdown(f"""
            <div style="text-align:center; background:#e3f2fd; padding:30px; border-radius:15px; border:3px dashed #2196f3;">
                <h1 style="font-size:60px; color:#075E54; font-family:monospace;">{final_display}</h1>
            </div>
        """, unsafe_allow_html=True)

if st.button("🗑️ إعادة ضبط البيانات"):
    supabase.table('merchants').update({"instance_id": None, "api_token": None, "pairing_code": None}).eq("Phone", current_phone).execute()
    st.rerun()

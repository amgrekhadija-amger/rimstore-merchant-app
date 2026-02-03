import streamlit as st
import requests, time, os
from supabase import create_client

# --- 1. الإعدادات الرسمية (من التوثيق الذي أرسلتِه) ---
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com" # partnerApiUrl

# اتصال Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def setup_instance_scenario(phone):
    """تطبيق السيناريو الموصى به من Green-API"""
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    
    # الخطوة 1: إنشاء السيرفر
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    try:
        res = requests.post(create_url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data['idInstance'])
            m_token = data['apiTokenInstance']
            
            # حفظ البيانات فوراً لكي يقرأها الكود في المرة القادمة
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            
            # الخطوة 2: انتظار بسيط للتهيئة (كما في المقال)
            time.sleep(5)
            
            # الخطوة 3: طلب كود الربط (Link with phone number)
            code_url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
            code_res = requests.post(code_url, json={"phoneNumber": clean_phone})
            
            if code_res.status_code == 200:
                p_code = code_res.json().get('code')
                supabase.table('merchants').update({"pairing_code": p_code}).eq("Phone", phone).execute()
                return p_code, m_id
    except Exception as e:
        st.error(f"عطل في تنفيذ السيناريو: {e}")
    return None, None

# --- واجهة المستخدم ---
st.title("📲 بوابة الربط الاحترافية")
current_phone = st.session_state.get('merchant_phone')

# قراءة البيانات الحالية
m_data = supabase.table('merchants').select("*").eq("Phone", current_phone).single().execute().data

if m_data:
    m_id = m_data.get('instance_id')
    saved_code = m_data.get('pairing_code')

    # إذا لم يكن هناك سيرفر أو كان هناك تكرار، نبدأ السيناريو
    if not m_id or st.button("🔄 إعادة محاولة الربط (السيناريو الموصى به)"):
        with st.spinner("جاري إنشاء وتهيئة السيرفر وقراءة الكود..."):
            new_code, new_id = setup_instance_scenario(current_phone)
            if new_code:
                st.success(f"تم إنشاء السيرفر {new_id} وجلب الكود بنجاح!")
                st.rerun()

    # عرض النتائج
    if saved_code:
        st.markdown(f"""
            <div style="text-align:center; background:#f0f7ff; padding:25px; border-radius:15px; border:2px solid #2196f3;">
                <h3 style="color:#0d47a1;">كود الربط المباشر:</h3>
                <h1 style="font-size:60px; color:#1565c0; font-family:monospace;">{saved_code}</h1>
                <p>أدخل الكود في هاتفك (الرقم: {current_phone})</p>
            </div>
        """, unsafe_allow_html=True)

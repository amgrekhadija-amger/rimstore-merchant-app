import streamlit as st
import requests, time
from supabase import create_client

# إعدادات الشريك
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"

# اتصال Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def process_whatsapp_pairing(phone):
    st.title("📲 بوابة الربط الآلي")
    
    # جلب بيانات التاجر الحالية
    res = supabase.table('merchants').select("*").eq("Phone", phone).execute()
    m_data = res.data[0] if res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    # الخطوة أ: إنشاء السيرفر وسحب idInstance
    if not m_id or m_id == "None":
        if st.button("🚀 إنشاء سيرفر جديد"):
            with st.spinner("جاري إنشاء السيرفر وسحب idInstance..."):
                create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
                c_res = requests.post(create_url, json={"plan": "developer"})
                if c_res.status_code == 200:
                    data = c_res.json()
                    new_id = str(data['idInstance']) # هذا هو idInstance الذي تطلبينه
                    new_token = data['apiTokenInstance']
                    
                    # حفظ idInstance في Supabase فوراً
                    supabase.table('merchants').update({
                        "instance_id": new_id, 
                        "api_token": new_token
                    }).eq("Phone", phone).execute()
                    st.success(f"✅ تم سحب المعرف: {new_id}")
                    time.sleep(2)
                    st.rerun()

    # الخطوة ب: طلب كود الربط باستخدام idInstance المحفوظ
    else:
        st.info(f"المعرف الحالي: {m_id}")
        if st.button("🔢 طلب كود الربط لهذا السيرفر"):
            with st.spinner("جاري طلب كود الربط من Green-API..."):
                # تسجيل خروج لتهيئة السيرفر للربط
                requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/logout/{m_token}")
                time.sleep(3)
                
                # جلب الكود الثماني
                pair_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
                p_res = requests.post(pair_url, json={"phoneNumber": phone})
                
                if p_res.status_code == 200:
                    code = p_res.json().get('code')
                    supabase.table('merchants').update({"pairing_code": code}).eq("Phone", phone).execute()
                    st.session_state.active_code = code
                    st.rerun()

    # عرض النتيجة النهائية
    final_code = st.session_state.get('active_code') or m_data.get('pairing_code')
    if final_code:
        st.markdown(f"""
            <div style="text-align:center; background:#f0f7ff; padding:30px; border-radius:15px; border:2px solid #2196f3;">
                <h1 style="font-size:60px; color:#075E54;">{final_code}</h1>
                <p>أدخل الكود في هاتفك المتصل برقم {phone}</p>
            </div>
        """, unsafe_allow_html=True)

# استدعاء الدالة بعد تسجيل الدخول
if st.session_state.get('logged_in'):
    process_whatsapp_pairing(st.session_state.merchant_phone)

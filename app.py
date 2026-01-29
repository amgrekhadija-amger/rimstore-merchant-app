import streamlit as st
import os, requests, time
from supabase import create_client

# --- إعدادات ثابتة ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"

# دالة إنشاء السيرفر (محدثة بالرابط الجديد)
def create_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            return str(data.get('idInstance')), data.get('apiTokenInstance')
    except: pass
    return None, None

# دالة طلب كود الربط الرقمي
def get_pairing_code(m_id, m_token, phone):
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- واجهة وتساب في Streamlit ---
def whatsapp_tab():
    st.subheader("📲 ربط وتساب المتجر")
    phone = st.session_state.get('merchant_phone')
    
    # 1. جلب البيانات من Supabase لضمان المزامنة
    res = supabase.table('merchants').select("*").eq("Phone", phone).execute()
    merchant = res.data[0] if res.data else {}
    
    m_id = merchant.get('instance_id')
    m_token = merchant.get('api_token')

    # الحالة أ: التاجر ليس لديه سيرفر
    if not m_id or m_id == "None":
        if st.button("🚀 إنشاء سيرفر وتساب جديد"):
            with st.spinner("جاري التواصل مع Green-API..."):
                new_id, new_token = create_instance(phone)
                if new_id:
                    supabase.table('merchants').update({
                        "instance_id": new_id, "api_token": new_token
                    }).eq("Phone", phone).execute()
                    st.success("✅ تم إنشاء السيرفر!")
                    st.rerun()
                else:
                    st.error("❌ فشل الإنشاء. تأكد من إعدادات الحساب.")

    # الحالة ب: السيرفر موجود، نحتاج للربط
    else:
        st.info(f"سيرفرك جاهز: {m_id}")
        
        # نستخدم مستوعب (Container) لعرض الكود لضمان ظهوره
        code_container = st.container()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔢 الحصول على كود الربط الرقمي"):
                with st.spinner("جاري طلب الكود..."):
                    code = get_pairing_code(m_id, m_token, phone)
                    if code:
                        st.session_state['last_code'] = code
                        st.success("✅ وصل الكود!")
                    else:
                        st.error("❌ فشل طلب الكود. تأكد أن الرقم صحيح.")

        if 'last_code' in st.session_state:
            with code_container:
                st.warning(f"أدخل هذا الكود في هاتفك الآن: **{st.session_state['last_code']}**")
                st.image("https://green-api.com/en/docs/api/introduction/pairing-code.png", caption="طريقة إدخال الكود في الهاتف")

        with col2:
            if st.button("🔄 فحص حالة الاتصال"):
                check_url = f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}"
                state = requests.get(check_url).json().get('stateInstance')
                st.metric("الحالة الحالية", state)
                if state == 'authorized':
                    st.success("🎉 الهاتف مرتبط ويعمل!")

        if st.button("🗑️ حذف السيرفر والبدء من جديد"):
            supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", phone).execute()
            st.session_state.pop('last_code', None)
            st.rerun()

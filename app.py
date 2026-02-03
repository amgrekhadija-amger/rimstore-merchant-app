import streamlit as st
import requests, time
from supabase import create_client

# 1. الإعدادات الثابتة (Green-API)
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"

# 2. اتصال Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- دالة بوابة الربط المنفصلة ---
def pairing_gate(phone):
    st.title("📲 مركز ربط واتساب")
    
    # جلب البيانات باستخدام الاسم الصحيح Merchant_name
    res = supabase.table('merchants').select("*").eq("Phone", phone).execute()
    if not res.data:
        st.error("بيانات التاجر غير موجودة.")
        return
        
    m_data = res.data[0]
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    # المرحلة الأولى: إنشاء السيرفر وحفظ idInstance
    if not m_id or m_id == "None":
        st.info("سيرفرك غير منشأ حالياً.")
        if st.button("🚀 إنشاء سيرفر جديد"):
            with st.spinner("جاري إنشاء السيرفر وسحب idInstance..."):
                create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
                c_res = requests.post(create_url, json={"plan": "developer"})
                if c_res.status_code == 200:
                    d = c_res.json()
                    # حفظ البيانات فوراً (Merchant_name)
                    supabase.table('merchants').update({
                        "instance_id": str(d['idInstance']), 
                        "api_token": d['apiTokenInstance']
                    }).eq("Phone", phone).execute()
                    st.success(f"✅ تم سحب المعرف: {d['idInstance']}")
                    time.sleep(3)
                    st.rerun()
        return

    # المرحلة الثانية: جلب كود الربط للسيرفر الموجود
    st.success(f"📦 السيرفر الرقمي المعتمد: {m_id}")
    
    if st.button("🔢 جلب كود الربط الرقمي"):
        with st.spinner("جاري طلب الكود من Green-API..."):
            # تسجيل خروج لتهيئة السيرفر
            requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/logout/{m_token}")
            time.sleep(3)
            
            # طلب الكود الثماني
            pair_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
            p_res = requests.post(pair_url, json={"phoneNumber": phone})
            
            if p_res.status_code == 200:
                code = p_res.json().get('code')
                # تحديث خانة pairing_code في الجدول
                supabase.table('merchants').update({"pairing_code": code}).eq("Phone", phone).execute()
                st.session_state.current_pair_code = code
                st.rerun()
            else:
                st.error("فشل في استخراج الكود. تأكدي من حالة السيرفر في Green-API.")

    # عرض الكود النهائي بشكل واضح
    display = st.session_state.get('current_pair_code') or m_data.get('pairing_code')
    if display:
        st.markdown(f"""
            <div style="text-align:center; background:#f0f9ff; padding:30px; border-radius:15px; border:2px solid #007bff;">
                <h1 style="font-size:60px; color:#075E54;">{display}</h1>
                <p>أدخل الكود في هاتفك المتصل برقم: <b>{phone}</b></p>
            </div>
        """, unsafe_allow_html=True)

# --- منطق التشغيل (يفترض تسجيل الدخول مسبقاً) ---
if st.session_state.get('logged_in'):
    pairing_gate(st.session_state.merchant_phone)
else:
    st.warning("يرجى تسجيل الدخول أولاً.")

import streamlit as st
import requests, time
from supabase import create_client

# 1. إعدادات الشريك
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
API_URL = "https://api.green-api.com"

# 2. اتصال Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def diagnose_and_pair(m_id, m_token, phone):
    """دالة التشخيص: تجلب الكود أو تشرح سبب الفشل"""
    status_report = [] # لتجميع ملاحظات التشخيص

    try:
        # أ- فحص حالة السيرفر أولاً
        state_res = requests.get(f"{API_URL}/waInstance{m_id}/getStateInstance/{m_token}")
        state = state_res.json().get('stateInstance', 'unknown')
        status_report.append(f"🔍 حالة السيرفر الحالية: {state}")

        # ب- محاولة ضبط الإعدادات
        set_res = requests.post(f"{API_URL}/waInstance{m_id}/setSettings/{m_token}", 
                               json={"delaySendMessagesTextMS": 1000})
        if set_res.status_code != 200:
            status_report.append(f"❌ خطأ في الضبط: {set_res.text}")

        # ج- تسجيل الخروج (مهم جداً للربط)
        requests.post(f"{API_URL}/waInstance{m_id}/logout/{m_token}")
        time.sleep(4)

        # د- طلب الكود ومراقبة الرد بدقة
        pair_url = f"{API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
        res = requests.post(pair_url, json={"phoneNumber": phone})
        
        if res.status_code == 200:
            return True, res.json().get('code'), status_report
        else:
            # هنا يكمن السر: تحليل سبب الرفض
            error_msg = res.json().get('message', res.text)
            status_report.append(f"❌ رفض Green-API طلب الكود: {error_msg}")
            return False, None, status_report

    except Exception as e:
        status_report.append(f"⚠️ خطأ تقني في الاتصال: {str(e)}")
        return False, None, status_report

def pairing_gate(phone):
    st.title("📲 بوابة الربط مع نظام التشخيص")
    
    # جلب البيانات
    res = supabase.table('merchants').select("*").eq("Phone", phone).execute()
    m_data = res.data[0] if res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id or m_id == "None":
        st.warning("السيرفر غير منشأ.")
        if st.button("🚀 إنشاء سيرفر جديد"):
            c_res = requests.post(f"{API_URL}/partner/createInstance/{PARTNER_TOKEN}", json={"plan": "developer"})
            if c_res.status_code == 200:
                d = c_res.json()
                supabase.table('merchants').update({"instance_id": str(d['idInstance']), "api_token": d['apiTokenInstance']}).eq("Phone", phone).execute()
                st.rerun()
        return

    st.info(f"📦 معرف السيرفر الحالي: {m_id}")

    if st.button("🔢 جلب الكود مع فحص الأخطاء"):
        with st.spinner("جاري التشخيص والطلب..."):
            success, code, report = diagnose_and_pair(m_id, m_token, phone)
            
            # عرض تقرير التشخيص للمبرمج (خديجة)
            with st.expander("🛠️ تقرير التشخيص التقني"):
                for line in report:
                    st.write(line)
            
            if success:
                supabase.table('merchants').update({"pairing_code": code}).eq("Phone", phone).execute()
                st.session_state.last_code = code
                st.success("✅ تم جلب الكود بنجاح!")
                st.rerun()
            else:
                st.error("🛑 فشل جلب الكود. راجعي تقرير التشخيص أعلاه.")

    # عرض الكود
    display = st.session_state.get('last_code') or m_data.get('pairing_code')
    if display:
        st.markdown(f"<div style='text-align:center; background:#e3f2fd; padding:20px; border-radius:15px; border:2px solid #2196f3;'><h1 style='font-size:60px; color:#075E54;'>{display}</h1></div>", unsafe_allow_html=True)

    if st.button("🔄 إعادة ضبط (حذف السيرفر المعلق)"):
        supabase.table('merchants').update({"instance_id": None, "api_token": None, "pairing_code": None}).eq("Phone", phone).execute()
        st.rerun()

# تشغيل
if st.session_state.get('logged_in'):
    pairing_gate(st.session_state.merchant_phone)

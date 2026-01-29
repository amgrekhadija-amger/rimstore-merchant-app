import streamlit as st
import requests
import time
from supabase import create_client

# --- إعدادات الشريك (تأكدي من صحة الـ Token) ---
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_URL = "https://api.greenapi.com/partner"

# --- دالة الربط الاحترافية المتكاملة ---
def start_pairing_process(merchant_phone):
    """هذه الدالة تقوم بكل شيء: إنشاء، حفظ، طلب كود الربط"""
    
    # 1. إنشاء المثيل (Instance)
    create_url = f"{PARTNER_URL}/waInstance/create/{PARTNER_TOKEN}"
    try:
        res = requests.post(create_url, json={"plan": "developer"}, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # 2. حفظ المعلومات فوراً في قاعدة البيانات
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", merchant_phone).execute()
            
            # 3. طلب كود الربط الرقمي (Pairing Code)
            # ملاحظة: يجب تنظيف الرقم من أي رموز (مثل +)
            clean_phone = ''.join(filter(str.isdigit, merchant_phone))
            pairing_url = f"https://api.greenapi.com/waInstance{m_id}/getPairingCode/{m_token}"
            
            # ننتظر قليلاً ليتفعل السيرفر الجديد
            time.sleep(2) 
            p_res = requests.post(pairing_url, json={"phoneNumber": clean_phone})
            
            if p_res.status_code == 200:
                return p_res.json().get('code'), m_id
            else:
                st.error("تم إنشاء السيرفر ولكن فشل توليد كود الربط. حاول مجدداً.")
                return None, m_id
    except Exception as e:
        st.error(f"خطأ تقني: {e}")
    return None, None

# --- واجهة المستخدم داخل تبويب (📲 ربط الواتساب) ---
with t4:
    st.header("🔗 ربط متجرك بالواتساب")
    
    # جلب بيانات التاجر الحالية
    m_info = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).single().execute()
    merchant = m_info.data
    
    if not merchant.get('instance_id'):
        st.info("لم تقم بربط هاتفك بعد. اضغط على الزر أدناه لبدء العملية.")
        if st.button("🔌 بدء عملية الربط الآن"):
            with st.spinner("جاري إنشاء بوابتك الخاصة..."):
                code, inst_id = start_pairing_process(st.session_state.merchant_phone)
                if code:
                    st.session_state.pairing_code = code
                    st.rerun()
    else:
        # إذا كان لديه Instance مسبقاً، نتحقق من الحالة
        m_id = merchant['instance_id']
        m_token = merchant['api_token']
        
        status_res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/getStateInstance/{m_token}").json()
        status = status_res.get('stateInstance')

        if status == 'authorized':
            st.success("✅ متجرك مرتبط بنجاح بالواتساب!")
            if st.button("🔴 فصل الارتباط"):
                requests.get(f"https://api.greenapi.com/waInstance{m_id}/logout/{m_token}")
                supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", st.session_state.merchant_phone).execute()
                st.rerun()
        else:
            st.warning("⚠️ هاتفك غير مرتبط بالسيرفر حالياً.")
            if st.button("🔢 الحصول على كود الربط الرقمي"):
                # طلب كود جديد للمثيل الموجود مسبقاً
                clean_phone = ''.join(filter(str.isdigit, st.session_state.merchant_phone))
                p_res = requests.post(f"https://api.greenapi.com/waInstance{m_id}/getPairingCode/{m_token}", json={"phoneNumber": clean_phone})
                if p_res.status_code == 200:
                    st.session_state.pairing_code = p_res.json().get('code')
                else:
                    st.error("فشل طلب الكود. تأكد أن الرقم صحيح.")

    # عرض كود الربط إذا توفر
    if 'pairing_code' in st.session_state:
        st.markdown("---")
        st.subheader("خطوات الربط على هاتفك:")
        st.write("1. افتح واتساب على هاتفك.")
        st.write("2. اذهب إلى **الأجهزة المرتبطة** > **ربط جهاز**.")
        st.write("3. اختر **الربط برقم الهاتف بدلاً من ذلك**.")
        st.write("4. أدخل الكود التالي:")
        st.code(st.session_state.pairing_code, language="text")
        st.balloons()

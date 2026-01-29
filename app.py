import streamlit as st
import requests
import time

# --- ثوابت الربط (Partner API) ---
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"

def run_test_connection(phone):
    """
    دالة الاختبار الكاملة:
    1. تطلب إنشاء المثيل من حساب الشريك.
    2. تستلم ID و Token التاجر.
    3. تطلب كود الربط الرقمي وتعرضه.
    """
    st.write("🔄 جاري الاتصال بـ Green-API...")
    
    # 1. إنشاء المثيل
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    try:
        res = requests.post(create_url, timeout=30)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            st.success(f"✅ تم إنشاء المثيل بنجاح! معرفك هو: {m_id}")
            
            # تحديث قاعدة البيانات بالبيانات الجديدة
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()

            # 2. طلب كود الربط الرقمي (Pairing Code)
            st.write("⏳ جاري توليد كود الربط الرقمي...")
            time.sleep(5) # انتظار بسيط لضمان تفعيل المثيل
            
            clean_phone = ''.join(filter(str.isdigit, str(phone)))
            pairing_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_phone}"
            
            p_res = requests.get(pairing_url, timeout=20)
            if p_res.status_code == 200:
                code = p_res.json().get('code')
                
                # حفظ الكود في عمود qr_code
                supabase.table('merchants').update({"qr_code": code}).eq("Phone", phone).execute()
                return m_id, code
            else:
                st.error("❌ فشل جلب كود الربط. تأكد من إعدادات الحساب.")
        else:
            st.error(f"❌ خطأ من Green-API: {res.text}")
    except Exception as e:
        st.error(f"⚠️ حدث خطأ تقني: {e}")
    return None, None

# --- واجهة التجربة في Streamlit ---
st.title("🧪 تجربة بوابة الربط الذكية")

if st.button("🚀 اضغط هنا لبدء التجربة (إنشاء + ربط)"):
    # نستخدم رقم الهاتف المخزن في الجلسة
    phone_to_test = st.session_state.get('merchant_phone')
    if phone_to_test:
        m_id, pairing_code = run_test_connection(phone_to_test)
        
        if pairing_code:
            st.balloons()
            st.markdown(f"""
            <div style="text-align:center; padding:30px; border:4px solid #128c7e; border-radius:20px; background-color:#f0f7f4;">
                <h2 style="color:#075e54;">🎉 نجحت العملية!</h2>
                <p>أدخل هذا الكود في واتساب هاتفك الآن:</p>
                <h1 style="font-size:80px; color:#128c7e; font-family:monospace;">{pairing_code}</h1>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("يرجى التأكد من تسجيل الدخول أولاً ليتمكن الكود من معرفة رقم هاتفك.")

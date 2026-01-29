import streamlit as st
import requests
import time

# --- ثوابت الربط (تأكدي من وجودها في بداية الملف) ---
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"

def start_full_connection(phone):
    """
    هذه الدالة تنفذ السيناريو الموصى به من Green-API:
    1. إنشاء المثيل عبر Partner API.
    2. استلام ID و Token التاجر.
    3. طلب كود الربط الرقمي (Pairing Code).
    """
    # الخطوة 1: إنشاء المثيل
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    
    try:
        response = requests.post(create_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # الخطوة 2: تحديث قاعدة البيانات (استخدام Merchant_name و Phone)
            # تم التأكد من أسماء الأعمدة هنا
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            
            # الخطوة 3: طلب كود الربط الرقمي
            # ننتظر قليلاً لضمان تشغيل المثيل في سيرفراتهم
            time.sleep(4) 
            
            clean_phone = ''.join(filter(str.isdigit, str(phone)))
            pairing_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_phone}"
            
            pairing_res = requests.get(pairing_url, timeout=20)
            if pairing_res.status_code == 200:
                p_code = pairing_res.json().get('code')
                
                # حفظ كود الـ 8 أرقام في عمود qr_code ليظهر للتاجر
                supabase.table('merchants').update({"qr_code": p_code}).eq("Phone", phone).execute()
                return m_id, p_code
            else:
                st.error(f"فشل جلب الكود: {pairing_res.text}")
        else:
            st.error(f"فشل إنشاء المثيل: {response.text}")
    except Exception as e:
        st.error(f"حدث خطأ في الاتصال: {str(e)}")
    return None, None

# --- واجهة المستخدم في التبويب الرابع ---
with t4:
    st.subheader("📲 بوابة ربط الواتساب الذكية")
    
    # جلب بيانات التاجر الحالية للتأكد من الحالة
    res = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    
    if res.data:
        merchant = res.data[0]
        # استخدام اسم العمود الصحيح Merchant_name كما أكدتِ
        st.write(f"مرحباً يا {merchant.get('Merchant_name')}")

        # إذا لم يكن لديه Instance ID بعد
        if not merchant.get('instance_id') or merchant.get('instance_id') == "None":
            if st.button("🚀 البدء: إنشاء مثيل وطلب كود الربط"):
                with st.spinner("جاري التواصل مع Green-API (قد يستغرق 10 ثوانٍ)..."):
                    m_id, code = start_full_connection(st.session_state.merchant_phone)
                    if code:
                        st.session_state.current_p_code = code
                        st.rerun()
        else:
            # إذا كان لديه مثيل، نعرض زر طلب الكود مباشرة
            st.info(f"الجلسة مفعلة برقم: {merchant.get('instance_id')}")
            if st.button("🔢 طلب كود ربط جديد"):
                with st.spinner("جاري جلب الكود..."):
                    m_id = merchant.get('instance_id')
                    m_token = merchant.get('api_token')
                    clean_phone = ''.join(filter(str.isdigit, str(st.session_state.merchant_phone)))
                    p_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_phone}"
                    p_res = requests.get(p_url).json()
                    st.session_state.current_p_code = p_res.get('code')

            # عرض الكود بشكل كبير وواضح
            if 'current_p_code' in st.session_state:
                st.markdown(f"""
                <div style="text-align:center; padding:30px; background-color:#f0f7f4; border:3px solid #128c7e; border-radius:15px;">
                    <h2 style="color:#075e54; margin-bottom:10px;">كود الربط الخاص بك:</h2>
                    <h1 style="font-size:75px; color:#128c7e; letter-spacing:15px; font-family:monospace;">{st.session_state.current_p_code}</h1>
                    <p style="font-size:16px; color:#555;">أدخل هذه الأرقام في واتساب هاتفك لإتمام الربط</p>
                </div>
                """, unsafe_allow_html=True)

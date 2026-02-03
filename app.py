import streamlit as st
import requests, os, time
from supabase import create_client

# إعدادات ثابتة
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_status(m_id, m_token):
    """فحص هل الجهاز مرتبط بالواتساب أم لا"""
    url = f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}"
    try:
        res = requests.get(url, timeout=10)
        return res.json().get('stateInstance')
    except: return "error"

def force_get_code(m_id, m_token, phone):
    """محاولة جلب الكود الرقمي بقوة"""
    # تنظيف الرقم (يجب أن يبدأ بمفتاح الدولة بدون +)
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        # إرسال طلب الكود
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- واجهة المستخدم ---
if 'logged_in' in st.session_state and st.session_state.logged_in:
    phone = st.session_state.merchant_phone
    
    # 1. جلب بيانات التاجر من Supabase
    res = supabase.table('merchants').select("*").eq("Phone", phone).execute()
    merchant = res.data[0] if res.data else {}
    
    st.subheader(f"🏪 متجر: {merchant.get('Store_name', 'غير معروف')}")
    
    m_id = merchant.get('instance_id')
    m_token = merchant.get('api_token')

    # 2. التحقق من وجود سيرفر
    if not m_id or m_id == "None":
        st.warning("⚠️ لا يوجد سيرفر مربوط بهذا الرقم حالياً.")
        if st.button("🚀 إنشاء سيرفر جديد الآن"):
            # كود إنشاء السيرفر (نفسه السابق)
            create_url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
            res_c = requests.post(create_url, json={"plan": "developer"})
            if res_c.status_code == 200:
                data = res_c.json()
                # حفظ البيانات فوراً
                supabase.table('merchants').update({
                    "instance_id": str(data['idInstance']),
                    "api_token": data['apiTokenInstance']
                }).eq("Phone", phone).execute()
                st.success("تم إنشاء السيرفر! جاري التحديث...")
                time.sleep(2)
                st.rerun()
    else:
        # 3. السيرفر موجود -> فحص الحالة
        status = get_status(m_id, m_token)
        
        if status == "authorized":
            st.success(f"✅ الواتساب مرتبط بنجاح (Instance: {m_id})")
        else:
            st.info(f"🔄 السيرفر جاهز (ID: {m_id}) ولكن يحتاج ربط بالهاتف.")
            
            if st.button("🔢 الحصول على كود الربط الرقمي"):
                with st.spinner("جاري جلب الكود من WhatsApp..."):
                    p_code = force_get_code(m_id, m_token, phone)
                    if p_code:
                        st.session_state['pairing_code'] = p_code
                    else:
                        st.error("فشل جلب الكود. تأكد أن الرقم في هاتفك هو نفس الرقم المسجل.")

            if 'pairing_code' in st.session_state:
                st.markdown(f"""
                <div style="text-align:center; background:#e3f2fd; padding:20px; border-radius:10px; border:2px dashed #2196f3;">
                    <h1 style="color:#075E54; font-size:50px;">{st.session_state['pairing_code']}</h1>
                    <p>أدخل هذا الكود في هاتفك الآن</p>
                </div>
                """, unsafe_allow_html=True)

    # زر إعادة الضبط (للتخلص من السيرفرات المعلقة)
    st.write("---")
    if st.sidebar.button("🗑️ حذف السيرفر الحالي والبدء من جديد"):
        supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", phone).execute()
        st.rerun()

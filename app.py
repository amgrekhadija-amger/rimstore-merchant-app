import streamlit as st
import os, requests, time
from dotenv import load_dotenv
from supabase import create_client

# --- الإعدادات الثابتة ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide")

# الاتصال بـ Supabase
url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# --- الدوال المحسنة ---

def get_pairing_code_logic(m_id, m_token, phone):
    """السر هنا: نجلب الكود، نحفظه في الداتابيز، ونعيده فوراً للمتصفح"""
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    # تسجيل الخروج لضمان استجابة السيرفر لطلب كود جديد
    requests.post(f"{PARTNER_API_URL}/waInstance{m_id}/logout/{m_token}")
    time.sleep(1) 
    
    url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            p_code = res.json().get('code')
            # الأمان: الحفظ في الداتابيز ليبقى هناك للأبد
            supabase.table('merchants').update({"pairing_code": p_code}).eq("Phone", phone).execute()
            return p_code
    except: pass
    return None

# --- نظام الدخول والجلسة ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
# هذا هو المفتاح لظهور الرقم فوراً في المتصفح
if 'last_p_code' not in st.session_state: st.session_state.last_p_code = None

if not st.session_state.logged_in:
    # (كود تسجيل الدخول المعتاد)
    with st.form("login"):
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.rerun()
    st.stop()

# --- واجهة التاجر ---
tabs = st.tabs(["➕ إضافة منتج", "📲 واتساب"])

with tabs[1]:
    st.subheader("📲 ربط الواتساب")
    curr_phone = st.session_state.merchant_phone
    
    # جلب البيانات من الداتابيز (للتأكد من وجود سيرفر)
    m_res = supabase.table('merchants').select("*").eq("Phone", curr_phone).execute()
    m_data = m_res.data[0] if m_res.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')
    db_saved_code = m_data.get('pairing_code') # الكود المخزن في الداتابيز

    if not m_id:
        st.info("السيرفر غير مفعل.")
        if st.button("🚀 إنشاء السيرفر"):
            # (كود إنشاء السيرفر)
            st.rerun()
    else:
        st.success(f"✅ السيرفر نشط: {m_id}")
        
        if st.button("🔢 استخراج الكود الآن"):
            with st.spinner("جاري جلب الكود..."):
                code = get_pairing_code_logic(m_id, m_token, curr_phone)
                if code:
                    # السر الذي اكتشفته في كودك: نضع الكود في الذاكرة المؤقتة ليعرض فوراً
                    st.session_state.last_p_code = code 
                    st.rerun()

        # العرض الذكي: يعرض كود الجلسة فوراً، أو الكود المحفوظ في الداتابيز إذا لم يوجد كود جلسة
        display_code = st.session_state.last_p_code or db_saved_code
        
        if display_code:
            st.markdown(f"""
            <div style="text-align:center; background:#e3f2fd; padding:20px; border-radius:10px; border:2px dashed #2196f3;">
                <h1 style="color:#075E54; font-family:monospace; font-size:50px;">{display_code}</h1>
            </div>
            """, unsafe_allow_html=True)

    if st.button("🗑️ حذف وإعادة ضبط"):
        supabase.table('merchants').update({"pairing_code": None, "instance_id": None}).eq("Phone", curr_phone).execute()
        st.session_state.last_p_code = None
        st.rerun()

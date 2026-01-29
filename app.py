import streamlit as st
import requests
import time
from supabase import create_client

# --- إعدادات الشريك (تأكدي من مطابقتها لحسابك) ---
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
# رابط الشريك يختلف عن رابط المستخدم العادي
PARTNER_API_URL = "https://api.greenapi.com/partner" 

# --- دالة الربط الاحترافية المتكاملة ---
def start_pairing_process(merchant_phone):
    """تقوم بإنشاء المثيل، حفظ البيانات، وطلب كود الربط الرقمي"""
    
    # الخطوة 1: إنشاء المثيل (Instance) باستخدام رابط الشريك الصحيح
    # الرابط الموصى به: {{partnerApiUrl}}/partner/createInstance/{{partnerToken}}
    create_url = f"{PARTNER_API_URL}/waInstance/create/{PARTNER_TOKEN}"
    
    try:
        # إرسال طلب الإنشاء (سيتم خصم المبلغ من رصيد الشريك)
        res = requests.post(create_url, json={"plan": "developer"}, timeout=30)
        
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # الخطوة 2: حفظ المعلومات فوراً في Supabase
            # الأسماء مطابقة للصور التي أرسلتِها (Phone و instance_id و api_token)
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token,
                "session_status": "starting"
            }).eq("Phone", merchant_phone).execute()
            
            # الخطوة 3: طلب كود الربط الرقمي (Pairing Code)
            # تنظيف الرقم من أي رموز أو مسافات
            clean_phone = ''.join(filter(str.isdigit, merchant_phone))
            
            # رابط طلب كود الربط (يستخدم بيانات المثيل الجديد)
            pairing_url = f"https://api.greenapi.com/waInstance{m_id}/getPairingCode/{m_token}"
            
            # ننتظر 3 ثوانٍ لضمان استقرار السيرفر الجديد قبل طلب الكود
            time.sleep(3) 
            p_res = requests.post(pairing_url, json={"phoneNumber": clean_phone}, timeout=20)
            
            if p_res.status_code == 200:
                return p_res.json().get('code'), m_id
            else:
                st.error(f"⚠️ السيرفر جاهز، لكن فشل توليد الكود: {p_res.text}")
                return None, m_id
        else:
            st.error(f"❌ فشل إنشاء المثيل من Green-API: {res.text}")
            return None, None
            
    except Exception as e:
        st.error(f"📡 خطأ في الاتصال: {str(e)}")
        return None, None

# --- واجهة المستخدم (تعديلات على تبويب t4) ---
def render_whatsapp_tab():
    st.header("🔗 ربط متجرك بالواتساب")
    
    # جلب بيانات التاجر الحالية من Supabase
    merchant_res = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    
    if not merchant_res.data:
        st.error("لم يتم العثور على بيانات التاجر.")
        return

    merchant = merchant_res.data[0]
    m_id = merchant.get('instance_id')
    m_token = merchant.get('api_token')

    # الحالة 1: التاجر لم ينشئ مثيل بعد
    if not m_id:
        st.info("لم تقم بتفعيل بوابة الواتساب الخاصة بمتجرك بعد.")
        if st.button("🚀 تفعيل البوابة الآن"):
            with st.spinner("جاري حجز سيرفر مخصص لك..."):
                code, inst_id = start_pairing_process(st.session_state.merchant_phone)
                if code:
                    st.session_state.pairing_code = code
                    st.success("✅ تم تفعيل البوابة بنجاح!")
                    st.rerun()

    # الحالة 2: التاجر لديه بيانات ولكننا نحتاج للتحقق من الاتصال
    else:
        try:
            status_res = requests.get(f"https://api.greenapi.com/waInstance{m_id}/getStateInstance/{m_token}", timeout=10).json()
            status = status_res.get('stateInstance')
        except:
            status = "unknown"

        if status == 'authorized':
            st.success("✅ حسابك مرتبط ونشط.")
            if st.button("🔴 تسجيل الخروج وفصل الحساب"):
                requests.get(f"https://api.greenapi.com/waInstance{m_id}/logout/{m_token}")
                # نمسح البيانات من قاعدة البيانات ليتسنى له الربط من جديد لاحقاً
                supabase.table('merchants').update({"instance_id": None, "api_token": None, "session_status": "disconnected"}).eq("Phone", st.session_state.merchant_phone).execute()
                st.rerun()
        else:
            st.warning("⚠️ البوابة جاهزة ولكن الهاتف غير مرتبط.")
            
            if st.button("🔢 الحصول على كود الربط الرقمي"):
                with st.spinner("جاري طلب الكود..."):
                    clean_phone = ''.join(filter(str.isdigit, st.session_state.merchant_phone))
                    p_res = requests.post(f"https://api.greenapi.com/waInstance{m_id}/getPairingCode/{m_token}", json={"phoneNumber": clean_phone})
                    if p_res.status_code == 200:
                        st.session_state.pairing_code = p_res.json().get('code')
                    else:
                        st.error("فشل طلب الكود. تأكد من رصيد حساب الشريك.")

    # عرض كود الربط الرقمي والتعليمات بشكل واضح
    if 'pairing_code' in st.session_state:
        st.markdown("---")
        st.subheader("📲 كود الربط الخاص بك")
        st.code(st.session_state.pairing_code, language="text")
        st.markdown("""
        **كيف تستخدم الكود؟**
        1. افتح تطبيق **WhatsApp** على هاتفك.
        2. اضغط على **الإعدادات** > **الأجهزة المرتبطة**.
        3. اضغط على **ربط جهاز**.
        4. اختر **الربط برقم الهاتف بدلاً من ذلك** (Link with phone number instead).
        5. أدخل الكود الموضح أعلاه.
        """)
        if st.button("✅ أكملت الربط"):
            del st.session_state.pairing_code
            st.rerun()

# استدعاء الدالة داخل التبويب
with t4:
    render_whatsapp_tab()

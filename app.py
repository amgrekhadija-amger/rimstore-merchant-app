import streamlit as st
import requests
import base64

# --- بياناتكِ الحقيقية من الصور ---
INSTANCE_ID = "7107486495"
API_TOKEN = "ضعي_هنا_التوكن_الخاص_بكِ_الموجود_تحت_رقم_الـ_Instance" # استخرجيه من الصورة الثانية

def get_green_qr(id_instance, api_token):
    # الرابط المباشر للـ Instance الخاص بكِ كما في الصور
    url = f"https://7107.api.greenapi.com/waInstance{id_instance}/qr/{api_token}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            return res.json()
        return None
    except:
        return None

# --- التعديل داخل تبويب t4 ---
with t4:
    st.subheader("📲 ربط واتساب المتجر")
    
    # عرض معلومات الـ Instance الخاص بكِ
    st.info(f"رقم الجهاز الفني: {INSTANCE_ID}")
    
    col_qr, col_status = st.columns(2)
    
    with col_qr:
        st.write("### 1️⃣ استخراج الرمز")
        if st.button("🔄 توليد رمز QR الآن"):
            with st.spinner("جاري الاتصال بالسيرفر..."):
                qr_data = get_green_qr(INSTANCE_ID, API_TOKEN)
                if qr_data:
                    if qr_data.get('type') == 'qrCode':
                        st.session_state.qr_img = qr_data.get('message')
                        st.rerun()
                    elif qr_data.get('type') == 'alreadyLoggedIn':
                        st.success("✅ الهاتف مربوط بالفعل ومستعد لاستقبال الطلبات!")
                else:
                    st.error("⚠️ فشل الاتصال. تأكدي من أن الـ Instance يعمل في لوحة التحكم.")

        if 'qr_img' in st.session_state:
            st.image(base64.b64decode(st.session_state.qr_img), width=300, caption="امسحي الرمز بواتساب المحل")
    
    with col_status:
        st.write("### 2️⃣ فحص حالة الربط")
        if st.button("🔍 هل تم الربط؟"):
            try:
                # رابط فحص الحالة
                status_url = f"https://7107.api.greenapi.com/waInstance{INSTANCE_ID}/getStateInstance/{API_TOKEN}"
                res = requests.get(status_url, timeout=5).json()
                state = res.get('stateInstance')
                if state == 'authorized':
                    st.success("✅ تم الربط بنجاح! متجركِ الآن اونلاين.")
                else:
                    st.warning(f"الحالة الحالية: {state}")
            except:
                st.error("تعذر جلب الحالة.")

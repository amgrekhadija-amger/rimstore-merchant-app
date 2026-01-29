import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64
import time

# --- 1. الإعدادات الثابتة ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com" 
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر - khadija", layout="wide")

# --- 2. الاتصال بـ Supabase ---
load_dotenv() 
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ يرجى ضبط مفاتيح Supabase في إعدادات Secrets")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- 3. الدوال البرمجية (Logic) ---

def set_webhook_url(m_id, m_token):
    """ضبط الويب هوك لاستلام الرسائل"""
    url = f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {
        "webhookUrl": WEBHOOK_URL, 
        "outgoingAPIMessage": "yes", 
        "incomingMsg": "yes",
        "deviceStatus": "yes"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def create_merchant_instance(phone):
    """إنشاء مثيل جديد وحفظه في Supabase"""
    url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            if m_id and m_token:
                # تحديث قاعدة البيانات - نستخدم "Phone" كونه المفتاح الأساسي الآن
                update_res = supabase.table('merchants').update({
                    "instance_id": m_id, 
                    "api_token": m_token
                }).eq("Phone", phone).execute()
                
                if len(update_res.data) > 0:
                    set_webhook_url(m_id, m_token)
                    return m_id, m_token
                else:
                    st.error(f"❌ فشل تحديث البيانات في الجدول للرقم {phone}")
            else:
                st.error("⚠️ البيانات المستلمة من API ناقصة.")
        else:
            st.error(f"❌ خطأ من Green-API: {res.text}")
    except Exception as e:
        st.error(f"⚠️ خطأ تقني أثناء التفعيل: {str(e)}")
    return None, None

def get_pairing_code(id_instance, api_token, phone):
    """جلب كود الربط المكون من 8 أرقام"""
    clean_phone = ''.join(filter(str.isdigit, phone))
    url = f"https://api.green-api.com/waInstance{id_instance}/getPairingCode/{api_token}?phoneNumber={clean_phone}"
    try:
        res = requests.get(url, timeout=20)
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 466:
            return {"type": "alreadyLoggedIn"}
    except:
        pass
    return None

# --- 4. واجهة التطبيق (UI) ---

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 دخول", "✨ تسجيل جديد"])
    
    with tab_signup:
        with st.form("signup_form"):
            s_m_name = st.text_input("اسم التاجر")
            s_s_name = st.text_input("اسم المتجر")
            s_phone = st.text_input("رقم الهاتف (بصيغة 222...)")
            s_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("إنشاء حساب"):
                try:
                    supabase.table('merchants').insert({
                        "Merchant_nar": s_m_name, 
                        "Store_name": s_s_name,
                        "Phone": s_phone, 
                        "password": s_pass, 
                        "session_status": "disconnected"
                    }).execute()
                    st.success("✅ تم التسجيل بنجاح! انتقل لتبويب الدخول.")
                except Exception as e:
                    st.error(f"❌ فشل التسجيل: {e}")

    with tab_login:
        with st.form("login_form"):
            l_phone = st.text_input("رقم الهاتف")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.rerun()
                else:
                    st.error("❌ بيانات الدخول غير صحيحة")
else:
    # لوحة التحكم الرئيسية
    st.sidebar.write(f"👤 مرحباً بك: {st.session_state.merchant_phone}")
    if st.sidebar.button("🚪 خروج"):
        st.session_state.logged_in = False
        st.rerun()

    t1, t2, t3, t4 = st.tabs(["➕ منتج جديد", "📦 الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t1:
        with st.form("add_product"):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر")
            p_img = st.file_uploader("صور المنتج", type=['png','jpg','jpeg'])
            if st.form_submit_button("حفظ المنتج"):
                img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                supabase.table('products').insert({
                    "Product": p_name, 
                    "Price": p_price, 
                    "Image_url": img_data, 
                    "Phone": st.session_state.merchant_phone
                }).execute()
                st.success("✅ تم إضافة المنتج بنجاح!")

    with t3:
        st.subheader("🛒 كشف الطلبات")
        orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
        if orders.data:
            for o in orders.data:
                st.info(f"📦 طلب من: {o['customer_pho']} | المنتج: {o['product_name']} | السعر: {o['total_price']}")
        else:
            st.write("لا توجد طلبات حالياً.")

    with t4:
        st.subheader("📲 إعدادات ربط واتساب")
        
        # جلب بيانات الربط الحالية
        m_res = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = m_res.data[0].get('instance_id') if m_res.data else None
        m_token = m_res.data[0].get('api_token') if m_res.data else None

        if not m_id or m_id in ["None", "NULL", ""]:
            st.warning("⚠️ خدمة الواتساب غير مفعلة لهذا المتجر.")
            if st.button("🚀 تفعيل وربط الحساب الآن"):
                with st.spinner("جاري تهيئة الحساب وحفظ البيانات..."):
                    new_id, new_token = create_merchant_instance(st.session_state.merchant_phone)
                    if new_id:
                        st.success("✅ تم التفعيل بنجاح!")
                        time.sleep(1)
                        st.rerun()
        else:
            col_left, col_right = st.columns(2)
            with col_left:
                st.info(f"🆔 معرف المثيل: {m_id}")
                if st.button("🔢 جلب كود الربط (8 أرقام)"):
                    with st.spinner("جاري طلب الكود..."):
                        p_data = get_pairing_code(m_id, m_token, st.session_state.merchant_phone)
                        if p_data and 'code' in p_data:
                            st.session_state.pairing_code_display = p_data['code']
                        elif p_data and p_data.get('type') == 'alreadyLoggedIn':
                            st.success("✅ الواتساب متصل بالفعل!")
                
                if 'pairing_code_display' in st.session_state:
                    st.success(f"كود الربط الخاص بك: **{st.session_state.pairing_code_display}**")
                    st.markdown("---")
                    st.write("🔧 **طريقة الربط:**")
                    st.write("1. افتح واتساب على هاتفك.")
                    st.write("2. اذهب إلى الأجهزة المرتبطة > ربط جهاز.")
                    st.write("3. اختر 'الربط برقم الهاتف بدلاً من ذلك' وأدخل الكود أعلاه.")

            with col_right:
                if st.button("🔍 فحص حالة الاتصال"):
                    try:
                        res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}").json()
                        st.metric("حالة الجهاز", res.get('stateInstance', 'غير معروف'))
                    except:
                        st.error("فشل في جلب الحالة.")

                if st.button("🗑️ إزالة الربط"):
                    if st.checkbox("أؤكد رغبتي في مسح بيانات الربط"):
                        supabase.table('merchants').update({"instance_id": None, "api_token": None}).eq("Phone", st.session_state.merchant_phone).execute()
                        st.rerun()

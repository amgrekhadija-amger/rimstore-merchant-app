import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import base64

# --- الإعدادات الثابتة ---
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم المتجر المتطورة - WPP", layout="wide")

# جلب الإعدادات من Secrets لضمان عملها على الرابط
load_dotenv() 
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ يرجى ضبط المفاتيح في Advanced Settings -> Secrets")
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

# --- دالة إنشاء Instance ---
def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/waInstance/create/{PARTNER_KEY}"
    try:
        res = requests.post(url)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # تحديث أعمدة التاجر في Supabase
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            
            set_webhook_url(m_id, m_token)
            return m_id, m_token
    except Exception as e: 
        st.error(f"خطأ في إنشاء الـ Instance: {e}")
        return None, None

def set_webhook_url(m_id, m_token):
    url = f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}"
    payload = {
        "webhookUrl": WEBHOOK_URL, 
        "outgoingAPIMessage": "yes", 
        "incomingMsg": "yes",
        "deviceStatus": "yes"
    }
    try: requests.post(url, json=payload)
    except: pass

def get_green_qr(id_instance, api_token):
    if not id_instance or not api_token:
        return None
    url = f"https://api.green-api.com/waInstance{id_instance}/qr/{api_token}"
    try:
        res = requests.get(url)
        if res.status_code == 200: return res.json()
    except: return None

# --- واجهة تسجيل الدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    
    with tab_signup:
        with st.form("signup_form"):
            s_merchant_name = st.text_input("اسم التاجر")
            s_store_name = st.text_input("اسم المحل")
            s_phone = st.text_input("رقم واتساب التاجر")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                try:
                    check = supabase.table('merchants').select("Phone").eq("Phone", s_phone).execute()
                    if check.data: st.error("❌ الرقم مسجل مسبقاً!")
                    elif s_merchant_name and s_store_name and s_phone and s_pass:
                        supabase.table('merchants').insert({
                            "Merchant_name": s_merchant_name, "Store_name": s_store_name, 
                            "Phone": s_phone, "password": s_pass, "session_status": "disconnected"
                        }).execute()
                        st.success("✅ تم إنشاء الحساب!")
                except: st.error("خطأ في الخادم")

    with tab_login:
        with st.form("login_form"):
            l_phone = st.text_input("رقم واتساب")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                try:
                    res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                    if res.data:
                        st.session_state.logged_in = True
                        st.session_state.merchant_phone = l_phone
                        st.session_state.store_name = res.data[0].get('Store_name')
                        st.session_state.m_id = res.data[0].get('instance_id')
                        st.session_state.m_token = res.data[0].get('api_token')
                        st.rerun()
                    else: st.error("بيانات خاطئة")
                except: st.error("تعذر الاتصال بقاعدة البيانات")

else:
    st.title(f"🏪 متجر: {st.session_state.store_name}")
    t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "✏️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

    with t1:
        with st.form("add_p", clear_on_submit=True):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر")
            p_size = st.text_input("المقاس")
            p_color = st.text_input("اللون")
            p_img = st.file_uploader("صورة المنتج", type=['png','jpg'])
            if st.form_submit_button("حفظ"):
                try:
                    img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
                    supabase.table('products').insert({
                        "Product": p_name, "Price": p_price, "Size": p_size, 
                        "Color": p_color, "Image_url": img_data, "Phone": st.session_state.merchant_phone
                    }).execute()
                    st.success("تم الحفظ بنجاح!")
                except: st.error("فشل الحفظ")

    with t2:
        st.subheader("📦 إدارة المنتجات")
        try:
            prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
            if prods.data:
                for p in prods.data:
                    col1, col2 = st.columns([4, 1])
                    col1.write(f"**{p['Product']}** - {p['Price']} MRU")
                    if col2.button("🗑️", key=f"del_{p['id']}"):
                        supabase.table('products').delete().eq("id", p['id']).execute()
                        st.rerun()
            else: st.info("لا توجد منتجات حالياً")
        except: st.error("حدث خطأ أثناء جلب المنتجات")

    with t3:
        st.subheader("🛒 الطلبات")
        try:
            orders = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
            if not orders.data: st.info("لا توجد طلبات")
            for o in orders.data:
                st.write(f"طلب من {o['customer_phone']}: {o['product_name']} - {o['status']}")
        except: st.error("خطأ في جلب الطلبات")

    with t4:
        st.subheader("إعدادات الاتصال عبر Green-API")
        
        # التأكد من جلب أحدث البيانات من سوبابيس لتجنب الأخطاء
        merchant_check = supabase.table('merchants').select("instance_id", "api_token").eq("Phone", st.session_state.merchant_phone).execute()
        m_id = merchant_check.data[0].get('instance_id') if merchant_check.data else None
        m_token = merchant_check.data[0].get('api_token') if merchant_check.data else None

        if not m_id or not m_token:
            st.info("ℹ️ يجب تفعيل الخدمة لمحلك أولاً.")
            if st.button("🚀 تفعيل خدمة الواتساب للمحل"):
                with st.spinner("جاري تهيئة النظام..."):
                    new_id, new_token = create_merchant_instance(st.session_state.merchant_phone)
                    if new_id:
                        st.session_state.m_id = new_id
                        st.session_state.m_token = new_token
                        st.success("✅ تم تفعيل الخدمة! اضغط 'توليد الرمز' الآن.")
                        st.rerun()
        else:
            col_qr, col_status = st.columns(2)
            with col_qr:
                if st.button("🔄 توليد رمز QR الجديد"):
                    with st.spinner("جاري الاتصال بـ Green-API..."):
                        qr_data = get_green_qr(m_id, m_token)
                        if qr_data and qr_data.get('type') == 'qrCode':
                            st.session_state.qr_img = qr_data.get('message')
                            st.rerun()
                        else:
                            st.warning("⚠️ لم يتم جلب الرمز. تأكد من حالة الـ Instance.")

                if 'qr_img' in st.session_state:
                    st.image(base64.b64decode(st.session_state.qr_img), width=300, caption="امسح الرمز بواتساب المتجر")
            
            with col_status:
                if st.button("✅ تحديث حالة الربط"):
                    try:
                        check_url = f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}"
                        state = requests.get(check_url).json().get('stateInstance')
                        if state == 'authorized':
                            supabase.table('merchants').update({"session_status": "connected"}).eq("Phone", st.session_state.merchant_phone).execute()
                            st.success("✅ متصل بنجاح!")
                            if 'qr_img' in st.session_state: del st.session_state.qr_img
                            st.rerun()
                        else:
                            st.info(f"الحالة الحالية: {state}")
                    except: st.error("تعذر الاتصال بـ Green-API")

    if st.sidebar.button("🚪 خروج"):
        st.session_state.logged_in = False
        st.rerun()

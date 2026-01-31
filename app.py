import streamlit as st
import requests
import time
import base64
from supabase import create_client

# --- 1. الإعدادات والاتصال ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. دالة ربط Green-API (تم تحسين سرعة الاستجابة) ---
def start_full_connection(phone):
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    try:
        response = requests.post(create_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            m_id, m_token = str(data.get('idInstance')), data.get('apiTokenInstance')
            
            # تحديث قاعدة البيانات الفوري
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            
            # تقليل وقت الانتظار قليلاً لسرعة التجربة
            time.sleep(3) 
            clean_phone = ''.join(filter(str.isdigit, str(phone)))
            pairing_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_phone}"
            
            p_res = requests.get(pairing_url, timeout=20)
            if p_res.status_code == 200:
                p_code = p_res.json().get('code')
                supabase.table('merchants').update({"qr_code": p_code}).eq("Phone", phone).execute()
                return m_id, p_code
    except Exception as e:
        st.error(f"خطأ في الاتصال: {e}")
    return None, None

# --- 3. نظام الدخول والتسجيل ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 بوابة التاجر - ملحفة")
    t_login, t_signup = st.tabs(["تسجيل دخول", "إنشاء حساب"])
    with t_signup:
        with st.form("signup_form"):
            n_name = st.text_input("اسم التاجر (Merchant_name)")
            n_store = st.text_input("اسم المتجر")
            n_phone = st.text_input("رقم الهاتف")
            n_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("فتح الحساب"):
                supabase.table('merchants').insert({"Merchant_name": n_name, "Store_name": n_store, "Phone": n_phone, "password": n_pass}).execute()
                st.success("✅ تم إنشاء الحساب!")
    with t_login:
        with st.form("login_form"):
            l_phone = st.text_input("رقم الهاتف")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    st.session_state.merchant_name = res.data[0]['Merchant_name']
                    st.rerun()
                else: st.error("بيانات خاطئة")
    st.stop()

# --- 4. واجهة التحكم الرئيسية ---
st.sidebar.title(f"👋 {st.session_state.merchant_name}")
if st.sidebar.button("تسجيل الخروج"):
    st.session_state.logged_in = False
    st.rerun()

t1, t2, t3, t4 = st.tabs(["➕ إضافة منتج", "⚙️ الإدارة", "🛒 الطلبات", "📲 ربط الواتساب"])

with t1:
    st.subheader("إضافة منتج جديد")
    with st.form("add_p", clear_on_submit=True):
        p_name = st.text_input("اسم المنتج")
        p_price = st.text_input("السعر")
        p_size = st.text_input("المقاس")
        p_color = st.text_input("الألوان")
        p_desc = st.text_area("الوصف")
        p_img = st.file_uploader("صورة المنتج", type=['png', 'jpg'])
        if st.form_submit_button("حفظ"):
            img_b64 = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}" if p_img else ""
            supabase.table('products').insert({"Product": p_name, "Price": p_price, "Size": p_size, "Color": p_color, "description": p_desc, "Image_url": img_b64, "Phone": st.session_state.merchant_phone, "Status": True}).execute()
            st.success("✅ تم حفظ المنتج!")

with t2:
    st.subheader("إدارة الأسعار والتوفر")
    prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    for p in prods.data:
        with st.expander(f"📦 {p['Product']} - {p['Price']}"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_p = st.text_input("تعديل السعر", value=p['Price'], key=f"p_{p['created_at']}")
                if st.button("تحديث السعر", key=f"bp_{p['created_at']}"):
                    supabase.table('products').update({"Price": new_p}).eq("created_at", p['created_at']).execute()
                    st.rerun()
            with col_b:
                st.write(f"الحالة: {'✅ متوفر' if p['Status'] else '❌ غير متوفر'}")
                if st.button("تغيير الحالة", key=f"bs_{p['created_at']}"):
                    supabase.table('products').update({"Status": not p['Status']}).eq("created_at", p['created_at']).execute()
                    st.rerun()

with t3:
    st.subheader("🛒 إدارة طلبات الزبائن")
    try:
        orders_res = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
        if orders_res.data:
            for o in orders_res.data:
                with st.container():
                    st.markdown(f"""
                    <div style="border-right: 5px solid #128c7e; padding:15px; background-color:#f9f9f9; border-radius:10px; margin-bottom:10px; color: black;">
                        <h4 style="margin:0;">👤 زبون: {o.get('customer_pho')}</h4>
                        <p style="margin:5px 0;">🛍️ <b>المنتج:</b> {o.get('product_name')} | 💰 <b>السعر:</b> {o.get('total_price')}</p>
                        <p style="margin:5px 0;">📍 <b>العنوان:</b> {o.get('delivery_addre', 'غير محدد')}</p>
                        <p style="margin:5px 0;">⏳ <b>الحالة:</b> {o.get('status', 'طلب جديد')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if o.get('status') != "تم التوصيل":
                        if st.button("✅ تم التوصيل", key=f"done_{o.get('created_at')}"):
                            supabase.table('orders').update({"status": "تم التوصيل"}).eq("created_at", o.get('created_at')).execute()
                            st.success("تم تحديث الطلب!")
                            st.rerun()
                    st.divider()
        else:
            st.info("لا توجد طلبات جديدة حالياً.")
    except Exception as e:
        st.error("⚠️ تنبيه: لا يمكن الوصول لجدول الطلبات.")

with t4:
    st.subheader("📲 ربط الواتساب")
    res = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    if res.data:
        merchant = res.data[0]
        st.write(f"مرحباً يا {merchant.get('Merchant_name')}")
        
        # تحسين: إذا لم يكن هناك Instance ID ابدأ عملية الربط
        if not merchant.get('instance_id') or merchant.get('instance_id') == "None":
            if st.button("🚀 البدء: إنشاء مثيل وطلب كود الربط"):
                with st.spinner("جاري الاتصال بـ Green-API..."):
                    m_id, code = start_full_connection(st.session_state.merchant_phone)
                    if code: 
                        st.session_state.current_p_code = code
                        st.balloons()
                        st.rerun()
        else:
            # إذا كان الحساب مربوطاً مسبقاً
            st.info(f"الجلسة مفعلة: {merchant.get('instance_id')}")
            col_link1, col_link2 = st.columns(2)
            with col_link1:
                if st.button("🔢 طلب كود ربط جديد"):
                    m_id, m_token = merchant.get('instance_id'), merchant.get('api_token')
                    clean_ph = ''.join(filter(str.isdigit, str(st.session_state.merchant_phone)))
                    p_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_ph}"
                    try:
                        resp = requests.get(p_url)
                        if resp.status_code == 200:
                            st.session_state.current_p_code = resp.json().get('code')
                            st.rerun()
                        else:
                            st.error("فشل جلب الكود، تأكد من حالة الجهاز.")
                    except:
                        st.error("خطأ في الاتصال بالسيرفر.")
            
            # عرض كود الربط بتصميم واضح جداً
            if 'current_p_code' in st.session_state:
                st.markdown(f"""
                <div style="text-align:center; padding:20px; border:3px dashed #128c7e; border-radius:15px; background-color:#f0f7f4; margin-top:20px;">
                    <p style="color:#075e54; margin-bottom:5px;">أدخل هذا الكود في واتساب هاتفك الآن:</p>
                    <h1 style="color:#128c7e; font-size:60px; font-family:monospace; letter-spacing:10px;">{st.session_state.current_p_code}</h1>
                </div>
                """, unsafe_allow_html=True)

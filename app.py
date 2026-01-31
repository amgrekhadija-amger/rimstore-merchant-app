import streamlit as st
import requests
import time
import base64
import os
from supabase import create_client

# --- 1. الإعدادات والاتصال بقاعدة البيانات ---
# تأكدي من ضبط هذه القيم في Secrets أو ملف البيئة
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ يرجى ضبط مفاتيح الاتصال بـ Supabase")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. الدوال البرمجية ---

def start_full_connection(phone):
    """ربط Green-API وسيناريو الشريك"""
    create_url = f"{PARTNER_API_URL}/partner/createInstance/{PARTNER_TOKEN}"
    try:
        response = requests.post(create_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            
            # تحديث جدول التجار
            supabase.table('merchants').update({
                "instance_id": m_id, 
                "api_token": m_token
            }).eq("Phone", phone).execute()
            
            time.sleep(4) 
            clean_phone = ''.join(filter(str.isdigit, str(phone)))
            pairing_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_phone}"
            
            pairing_res = requests.get(pairing_url, timeout=20)
            if pairing_res.status_code == 200:
                p_code = pairing_res.json().get('code')
                supabase.table('merchants').update({"qr_code": p_code}).eq("Phone", phone).execute()
                return m_id, p_code
    except Exception as e:
        st.error(f"حدث خطأ في الاتصال: {str(e)}")
    return None, None

# --- 3. واجهة المستخدم (Streamlit) ---
st.title("🛍️ لوحة تحكم التاجر - ملحفة")

# نظام الدخول البسيط (بناءً على Phone)
if 'merchant_phone' not in st.session_state:
    with st.form("login"):
        ph = st.text_input("رقم الهاتف المسجل")
        if st.form_submit_button("دخول"):
            st.session_state.merchant_phone = ph
            st.rerun()
    st.stop()

# إنشاء التبويبات بناءً على طلبك
t1, t2, t3, t4 = st.tabs(["➕ إضافة منتجات", "⚙️ إدارة المتجر", "🛒 الطلبات", "📲 ربط الواتساب"])

# --- التبويب 1: إضافة المنتجات ---
with t1:
    st.subheader("إضافة منتج جديد")
    with st.form("add_product_form", clear_on_submit=True):
        p_name = st.text_input("اسم المنتج")
        p_price = st.text_input("سعر المنتج")
        p_size = st.text_input("مقاس المنتج (Size)")
        p_color = st.text_input("الألوان المتوفرة (Color)")
        p_desc = st.text_area("وصف المنتج (description)")
        p_img = st.file_uploader("رفع صورة منتج", type=['png', 'jpg', 'jpeg'])
        
        if st.form_submit_button("حفظ المنتج"):
            img_data = ""
            if p_img:
                img_data = f"data:image/png;base64,{base64.b64encode(p_img.read()).decode()}"
            
            # الإدخال بناءً على أعمدة جدول products في صورتك
            supabase.table('products').insert({
                "Product": p_name,
                "Price": p_price,
                "Size": p_size,
                "Color": p_color,
                "description": p_desc,
                "Image_url": img_data,
                "Phone": st.session_state.merchant_phone,
                "Status": True
            }).execute()
            st.success("✅ تم حفظ المنتج بنجاح!")

# --- التبويب 2: إدارة الأسعار والحالة ---
with t2:
    st.subheader("إدارة المنتجات المتوفرة")
    prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    
    if prods.data:
        for p in prods.data:
            with st.expander(f"📦 {p['Product']} - السعر الحلي: {p['Price']}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_price = st.text_input("تعديل السعر", value=p['Price'], key=f"price_{p['created_at']}")
                    if st.button("تحديث السعر", key=f"btn_p_{p['created_at']}"):
                        supabase.table('products').update({"Price": new_price}).eq("created_at", p['created_at']).execute()
                        st.rerun()
                with col2:
                    current_status = p.get('Status', True)
                    status_label = "✅ متوفر" if current_status else "❌ غير متوفر"
                    if st.button(f"تغيير إلى ({'غير متوفر' if current_status else 'متوفر'})", key=f"btn_s_{p['created_at']}"):
                        supabase.table('products').update({"Status": not current_status}).eq("created_at", p['created_at']).execute()
                        st.rerun()
                    st.write(f"الحالة الحالية: **{status_label}**")
    else:
        st.info("لا توجد منتجات مضافة بعد.")

# --- التبويب 3: الطلبات ---
with t3:
    st.subheader("🛒 طلبات الزبائن")
    # بناءً على أعمدة جدول orders في صورتك
    orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
    
    if orders.data:
        for o in orders.data:
            st.write(f"---")
            st.write(f"📱 **رقم الزبون:** {o['customer_pho']}")
            st.write(f"🛍️ **المنتج:** {o['product_name']}")
            st.write(f"💰 **الإجمالي:** {o['total_price']}")
            st.write(f"📍 **العنوان:** {o['delivery_addre']}")
            st.write(f"📝 **ملاحظات:** {o['order_notes']}")
            st.write(f"🕒 **التاريخ:** {o['created_at']}")
    else:
        st.info("لا توجد طلبات جديدة حالياً.")

# --- التبويب 4: ربط الواتساب (كما هو) ---
with t4:
    st.subheader("📲 بوابة ربط الواتساب الذكية")
    res = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    
    if res.data:
        merchant = res.data[0]
        st.write(f"مرحباً يا {merchant.get('Merchant_nar')}") # تم استخدام Merchant_nar كما في الصورة

        if not merchant.get('instance_id') or merchant.get('instance_id') == "None":
            if st.button("🚀 البدء: إنشاء مثيل وطلب كود الربط"):
                with st.spinner("جاري التواصل مع Green-API..."):
                    m_id, code = start_full_connection(st.session_state.merchant_phone)
                    if code:
                        st.session_state.current_p_code = code
                        st.rerun()
        else:
            st.info(f"الجلسة مفعلة برقم: {merchant.get('instance_id')}")
            if st.button("🔢 طلب كود ربط جديد"):
                with st.spinner("جاري جلب الكود..."):
                    m_id = merchant.get('instance_id')
                    m_token = merchant.get('api_token')
                    clean_phone = ''.join(filter(str.isdigit, str(st.session_state.merchant_phone)))
                    p_url = f"{PARTNER_API_URL}/waInstance{m_id}/getPairingCode/{m_token}?phoneNumber={clean_phone}"
                    p_res = requests.get(p_url).json()
                    st.session_state.current_p_code = p_res.get('code')

            if 'current_p_code' in st.session_state:
                st.markdown(f"""
                <div style="text-align:center; padding:30px; background-color:#f0f7f4; border:3px solid #128c7e; border-radius:15px;">
                    <h2 style="color:#075e54;">كود الربط الخاص بك:</h2>
                    <h1 style="font-size:75px; color:#128c7e; letter-spacing:15px; font-family:monospace;">{st.session_state.current_p_code}</h1>
                    <p>أدخل هذه الأرقام في واتساب هاتفك لإتمام الربط</p>
                </div>
                """, unsafe_allow_html=True)

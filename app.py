import streamlit as st
from supabase import create_client
import uuid
import time
import requests

# --- 1. إعدادات السحابة ---
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

WEBHOOK_URL = "https://khadija.pythonanywhere.com/whatsapp"

# --- 2. اللغات ---
languages = {
    "العربية": {
        "dir": "rtl", "title": "RimStore",
        "sidebar_title": "🔐 دخول التجار", "phone": "رقم الواتساب",
        "password": "كلمة السر", "store_name": "اسم المتجر",
        "tabs": ["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"],
        "p_name": "📍 اسم المنتج", "p_price": "💰 السعر", "p_size": "📏 المقاسات",
        "p_color": "🎨 الألوان", "p_stock": "📦 الحالة", "stock_true": "متوفر", "stock_false": "نفد",
        "save": "حفظ ونشر", "update": "تحديث", "loading": "جاري الحفظ..."
    }
}

st.set_page_config(page_title="RimStore", layout="wide")
t = languages["العربية"]

def setup_webhook_auto(inst, tok):
    url = f"https://api.ultramsg.com/{inst}/instance/settings"
    params = {"token": tok, "webhook_url": WEBHOOK_URL, "webhook_message_received": "true"}
    try: requests.get(url, params=params, timeout=5)
    except: pass

if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- 3. واجهة الدخول ---
if not st.session_state.logged_in:
    with st.sidebar:
        st.title(t["sidebar_title"])
        auth_mode = st.radio("العملية", ["تسجيل دخول", "إنشاء حساب"])
        u_phone = st.text_input(t["phone"], placeholder="222xxxxxxx")
        u_pwd = st.text_input(t["password"], type="password")
        
        if auth_mode == "إنشاء حساب":
            u_store = st.text_input(t["store_name"])
            if st.button("تأكيد"):
                # استناداً لصورة جدول merchants
                supabase.table('merchants').insert({
                    "Phone": u_phone, 
                    "Store_name": u_store, 
                    "password": u_pwd, 
                    "is_active": False
                }).execute()
                st.success("تم الإنشاء بنجاح!")
        else:
            if st.button("تأكيد"):
                res = supabase.table('merchants').select("*").eq('Phone', u_phone).eq('password', u_pwd).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = u_phone
                    st.session_state.store_name = res.data[0]['Store_name']
                    st.rerun()
                else: st.error("خطأ في البيانات")

# --- 4. واجهة المتجر والربط ---
if st.session_state.logged_in:
    # جلب البيانات المحدثة (مراعاة حالة الأحرف في Instance_id و api_token)
    m_res = supabase.table('merchants').select("*").eq('Phone', st.session_state.merchant_phone).execute()
    m_data = m_res.data[0]
    
    # تصحيح المسميات حسب صورة الجدول: Instance_id و api_token
    inst = m_data.get('instance_id') or m_data.get('Instance_id')
    tok = m_data.get('api_token')

    st.sidebar.success(f"🏪 {st.session_state.store_name}")
    tab1, tab2, tab3, tab4 = st.tabs(t["tabs"])

    with tab4:
        st.subheader("📲 حالة اتصال الواتساب")
        if not inst or not tok:
            st.warning("يرجى تفعيل الحساب من الإدارة (Instance ID غير موجود).")
        else:
            try:
                status_res = requests.get(f"https://api.ultramsg.com/{inst}/instance/status?token={tok}").json()
                current_status = status_res.get("status", "unknown")
            except: current_status = "error"

            if current_status == "authenticated":
                st.success("✅ البوت نشط ومرتبط.")
                setup_webhook_auto(inst, tok)
                if st.button("🔴 تسجيل خروج الجهاز"):
                    requests.get(f"https://api.ultramsg.com/{inst}/instance/logout?token={tok}")
                    st.rerun()
            else:
                qr_url = f"https://api.ultramsg.com/{inst}/instance/qr?token={tok}&t={int(time.time())}"
                st.image(qr_url, caption="امسح الرمز للربط", width=300)
                if st.button("🔄 تحديث"): st.rerun()

    with tab1:
        with st.form("add_p"):
            col1, col2 = st.columns(2)
            with col1:
                p_n = st.text_input(t["p_name"])
                p_p = st.text_input(t["p_price"])
                p_size = st.text_input(t["p_size"])
            with col2:
                p_color = st.text_input(t["p_color"])
                p_stock = st.selectbox(t["p_stock"], [t["stock_true"], t["stock_false"]])
                p_img = st.file_uploader("📸 الصورة", type=['jpg', 'png'])
            
            if st.form_submit_button(t["save"]):
                if p_n and p_p and p_img:
                    img_id = f"{uuid.uuid4()}.png"
                    supabase.storage.from_('product-images').upload(img_id, p_img.read())
                    url = supabase.storage.from_('product-images').get_public_url(img_id)
                    # استناداً لصورة جدول products
                    supabase.table('products').insert({
                        "Phone": st.session_state.merchant_phone, 
                        "Product": p_n, 
                        "Price": p_p, 
                        "Size": p_size,
                        "Color": p_color,
                        "Status": (p_stock == t["stock_true"]), 
                        "Image_url": url
                    }).execute()
                    st.success("تم الحفظ!")
                    st.rerun()

    with tab2:
        prods = supabase.table('products').select("*").eq('Phone', st.session_state.merchant_phone).execute()
        if prods.data:
            for p in prods.data:
                with st.expander(f"📦 {p['Product']} - {p['Price']}"):
                    st.image(p['Image_url'], width=150)
                    if st.button("حذف المنتج", key=p['id']):
                        supabase.table('products').delete().eq('id', p['id']).execute()
                        st.rerun()
        else: st.info("لا توجد منتجات.")

    with tab3:
        st.subheader("🛒 الطلبات الواردة")
        try:
            # تصحيح هام جداً: العمود في صورتك هو merchant_phc وليس merchant_phone
            o_res = supabase.table('orders').select("*").eq('merchant_phc', st.session_state.merchant_phone).execute()
            if o_res.data:
                for o in o_res.data:
                    # تصحيح الحقول حسب صورتك: customer_pho و product_name و total_price
                    st.info(f"طلب من: {o.get('customer_pho', 'غير معروف')} | المنتج: {o.get('product_name', 'غير محدد')} | السعر: {o.get('total_price', '0')}")
            else:
                st.write("لا توجد طلبات جديدة.")
        except Exception as e:
            st.error(f"تأكد من مطابقة أسماء الحقول في جدول الطلبات: {e}")

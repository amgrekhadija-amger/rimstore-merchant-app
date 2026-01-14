import streamlit as st
from supabase import create_client
import uuid
import time
import requests

# --- 1. إعدادات السحاب (Supabase) ---
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

WEBHOOK_URL = "https://khadija.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="RimStore Platform", layout="wide")

# --- 2. نظام اللغات (العربية/الفرنسية) ---
if 'lang' not in st.session_state: st.session_state.lang = 'ar'
def toggle_lang(): st.session_state.lang = 'fr' if st.session_state.lang == 'ar' else 'ar'

texts = {
    'ar': {
        'products': "📦 إدارة المنتجات", 'status': "📊 حالة النظام", 'orders': "🛒 طلبات الزبائن",
        'p_name': "اسم المنتج", 'p_price': "السعر", 'p_size': "المقاس", 'p_color': "اللون",
        'available': "متوفر", 'not_available': "غير متوفر", 'save': "حفظ ونشر آلي",
        'qr_msg': "امسح الرمز لربط متجرك بالبوت:", 'no_inst': "انتظر تفعيل الحساب من الإدارة (Instance ID)."
    },
    'fr': {
        'products': "📦 Produits", 'status': "📊 Système", 'orders': "🛒 Commandes",
        'p_name': "Nom", 'p_price': "Prix", 'p_size': "Taille", 'p_color': "Couleur",
        'available': "Disponible", 'not_available': "Rupture", 'save': "Enregistrer",
        'qr_msg': "Scannez pour lier WhatsApp:", 'no_inst': "Attendez l'activation admin."
    }
}
T = texts[st.session_state.lang]

# زر اللغة في الأعلى
col_l1, col_l2 = st.columns([0.9, 0.1])
with col_l2:
    if st.button("🌐 FR/AR"): toggle_lang(); st.rerun()

# --- 3. واجهة الدخول ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.sidebar.title("🔐 دخول التجار")
    auth_mode = st.sidebar.radio("العملية", ["تسجيل دخول", "إنشاء حساب"])
    u_phone = st.sidebar.text_input("رقم الواتساب (مثال: 222...)")
    u_pwd = st.sidebar.text_input("كلمة السر", type="password")
    
    if st.sidebar.button("تأكيد / Confirmer"):
        if auth_mode == "تسجيل دخول":
            res = supabase.table('merchants').select("*").eq('Phone', u_phone).eq('password', u_pwd).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0]['Store_name']
                st.rerun()
            else: st.error("بيانات غير صحيحة")
        else:
            u_store = st.sidebar.text_input("اسم المتجر")
            # الإدخال حسب أعمدة جدول merchants
            supabase.table('merchants').insert({"Phone": u_phone, "Store_name": u_store, "password": u_pwd, "is_active": False}).execute()
            st.success("تم الإنشاء بنجاح! تواصل مع الإدارة للتفعيل.")

# --- 4. لوحة التحكم (بعد الدخول) ---
if st.session_state.logged_in:
    # جلب بيانات التاجر الحالية لربط UltraMsg
    m_res = supabase.table('merchants').select("*").eq('Phone', st.session_state.merchant_phone).execute()
    m_data = m_res.data[0]
    m_inst = m_data.get('instance_id')
    m_tok = m_data.get('api_token')

    tab1, tab2, tab3 = st.tabs([T['products'], T['status'], T['orders']])

    # --- تبويب إدارة المنتجات ---
    with tab1:
        st.subheader(f"➕ {T['products']}")
        with st.form("add_product", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                p_name = st.text_input(T['p_name'])
                p_price = st.text_input(T['p_price'])
                p_size = st.text_input(T['p_size'])
            with c2:
                p_color = st.text_input(T['p_color'])
                p_stat = st.selectbox("Status", [T['available'], T['not_available']])
                p_img = st.file_uploader("Image", type=['jpg', 'png'])
            
            if st.form_submit_button(T['save']):
                if p_name and p_img:
                    img_id = f"{uuid.uuid4()}.png"
                    supabase.storage.from_('product-images').upload(img_id, p_img.read())
                    img_url = supabase.storage.from_('product-images').get_public_url(img_id)
                    # الإدخال حسب أعمدة جدول products
                    supabase.table('products').insert({
                        "Phone": st.session_state.merchant_phone, "Product": p_name, 
                        "Price": p_price, "Image_url": img_url, "Size": p_size,
                        "Color": p_color, "Status": (p_stat == T['available'])
                    }).execute()
                    st.success("تم الحفظ!")
                    st.rerun()

        st.divider()
        # عرض المنتجات بشكل شبكة احترافية
        st.subheader("🖼️ منتجاتك الحالية")
        p_list = supabase.table('products').select("*").eq('Phone', st.session_state.merchant_phone).execute()
        if p_list.data:
            cols = st.columns(4)
            for i, p in enumerate(p_list.data):
                with cols[i % 4]:
                    st.image(p['Image_url'], use_container_width=True)
                    st.write(f"**{p['Product']}**")
                    st.caption(f"📏 {p.get('Size')} | 🎨 {p.get('Color')}")
                    if st.button("🗑️", key=f"del_{p['id']}"):
                        supabase.table('products').delete().eq('id', p['id']).execute()
                        st.rerun()

    # --- تبويب ربط الواتساب (UltraMsg) ---
    with tab2:
        st.subheader(T['status'])
        if not m_inst or not m_tok:
            st.warning(T['no_inst'])
        else:
            # هنا يظهر الـ QR Code لربط الواتساب مباشرة
            qr_url = f"https://api.ultramsg.com/{m_inst}/instance/qr?token={m_tok}&t={int(time.time())}"
            st.info(T['qr_msg'])
            st.image(qr_url, width=300)
            if st.button("تحديث الحالة / Refresh"): st.rerun()

    # --- تبويب الطلبات (حل مشكلة العمود merchant_phc) ---
    with tab3:
        st.subheader(T['orders'])
        # استخدام العمود merchant_phc كما في صورتك
        try:
            o_res = supabase.table('orders').select("*").eq('merchant_phc', st.session_state.merchant_phone).execute()
            if o_res.data:
                for o in o_res.data:
                    with st.expander(f"طلب من: {o['customer_pho']}"):
                        st.write(f"📦 المنتج: {o['product_name']}")
                        st.write(f"💰 السعر: {o['total_price']}")
                        st.write(f"📊 الحالة: {o['status']}")
            else: st.info("لا توجد طلبات بعد.")
        except Exception as e:
            st.error(f"حدث خطأ أثناء جلب الطلبات: {e}")

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

# --- 2. نظام اللغات ---
if 'lang' not in st.session_state: st.session_state.lang = 'ar'

def toggle_lang():
    st.session_state.lang = 'fr' if st.session_state.lang == 'ar' else 'ar'

# نصوص الواجهة
texts = {
    'ar': {
        'title': "لوحة تحكم RimStore", 'products': "📦 إدارة المنتجات", 'status': "📊 حالة النظام", 
        'orders': "🛒 طلبات الزبائن", 'add_prod': "إضافة منتج جديد", 'p_name': "اسم المنتج",
        'p_price': "السعر (أوقية)", 'p_size': "المقاسات", 'p_color': "الألوان", 'p_status': "الحالة",
        'available': "متوفر", 'not_available': "غير متوفر", 'save': "حفظ ونشر آلي", 'my_prods': "معرض منتجاتك",
        'logout_wa': "🔴 تسجيل خروج الواتساب", 'orders_title': "الطلبات المستلمة على الواتساب"
    },
    'fr': {
        'title': "Tableau de Bord RimStore", 'products': "📦 Produits", 'status': "📊 Système", 
        'orders': "🛒 Commandes", 'add_prod': "Ajouter un produit", 'p_name': "Nom du produit",
        'p_price': "Prix (UM)", 'p_size': "Tailles", 'p_color': "Couleurs", 'p_status': "Statut",
        'available': "Disponible", 'not_available': "Rupture de stock", 'save': "Enregistrer", 'my_prods': "Mes Produits",
        'logout_wa': "🔴 Déconnecter WhatsApp", 'orders_title': "Commandes reçues via WhatsApp"
    }
}
T = texts[st.session_state.lang]

# زر تغيير اللغة في الأعلى
col_l1, col_l2 = st.columns([0.9, 0.1])
with col_l2:
    if st.button("🌐 FR/AR"): toggle_lang(); st.rerun()

# --- 3. الوظائف التقنية ---
def check_whatsapp_status(inst, tok):
    if not inst or not tok: return "disconnected"
    try:
        url = f"https://api.ultramsg.com/{inst}/instance/status?token={tok}"
        res = requests.get(url, timeout=5).json()
        return res.get("status", "disconnected")
    except: return "error"

def setup_webhook(inst, tok):
    url = f"https://api.ultramsg.com/{inst}/instance/settings"
    params = {"token": tok, "webhook_url": WEBHOOK_URL, "webhook_message_received": "true"}
    try: requests.get(url, params=params)
    except: pass

if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- 4. واجهة الدخول ---
if not st.session_state.logged_in:
    auth_mode = st.sidebar.radio("Menu", ["تسجيل دخول / Login", "إنشاء حساب / Sign Up"])
    u_phone = st.sidebar.text_input("WhatsApp")
    u_pwd = st.sidebar.text_input("Password", type="password")
    
    if "إنشاء" in auth_mode:
        u_store = st.sidebar.text_input("Store Name")
        if st.sidebar.button("Register"):
            supabase.table('merchants').insert({"Phone": u_phone, "Store_name": u_store, "password": u_pwd}).execute()
            st.success("Success!")
    else:
        if st.sidebar.button("Login"):
            res = supabase.table('merchants').select("*").eq('Phone', u_phone).eq('password', u_pwd).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0]['Store_name']
                st.rerun()

# --- 5. لوحة التحكم الرئيسية ---
if st.session_state.logged_in:
    # جلب بيانات التاجر الحالية
    res_m = supabase.table('merchants').select("*").eq('Phone', st.session_state.merchant_phone).execute()
    m_data = res_m.data[0]
    m_inst, m_tok = m_data.get('instance_id'), m_data.get('api_token')

    ws_status = check_whatsapp_status(m_inst, m_tok)
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    
    tab1, tab2, tab3 = st.tabs([T['products'], T['status'], T['orders']])

    # --- تبويب المنتجات ---
    with tab1:
        st.subheader(f"➕ {T['add_prod']}")
        with st.form("new_prod", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                p_name = st.text_input(T['p_name'])
                p_price = st.text_input(T['p_price'])
                p_size = st.text_input(T['p_size'], placeholder="XL, L, M...")
            with c2:
                p_color = st.text_input(T['p_color'], placeholder="Red, Blue...")
                p_stat = st.selectbox(T['p_status'], [T['available'], T['not_available']])
                p_img = st.file_uploader("Image", type=['jpg', 'png'])
            
            if st.form_submit_button(T['save']):
                if p_name and p_img:
                    img_id = f"{uuid.uuid4()}.png"
                    supabase.storage.from_('product-images').upload(img_id, p_img.read())
                    img_url = supabase.storage.from_('product-images').get_public_url(img_id)
                    # الحفظ مع كافة الأعمدة الجديدة
                    supabase.table('products').insert({
                        "Phone": st.session_state.merchant_phone, "Product": p_name, 
                        "Price": p_price, "Image_url": img_url, "Size": p_size,
                        "Color": p_color, "Status": (p_stat == T['available'])
                    }).execute()
                    st.rerun()

        st.divider()
        st.subheader(f"🖼️ {T['my_prods']}")
        p_res = supabase.table('products').select("*").eq('Phone', st.session_state.merchant_phone).execute()
        if p_res.data:
            cols = st.columns(4)
            for idx, p in enumerate(p_res.data):
                with cols[idx % 4]:
                    st.image(p['Image_url'], use_container_width=True)
                    st.write(f"**{p['Product']}**")
                    st.caption(f"📏 {p.get('Size')} | 🎨 {p.get('Color')}")
                    # زر لتعديل الحالة فوراً
                    new_stat = st.toggle("Available", value=p['Status'], key=f"stat_{p['id']}")
                    if new_stat != p['Status']:
                        supabase.table('products').update({"Status": new_stat}).eq('id', p['id']).execute()
                        st.rerun()
                    if st.button("🗑️", key=f"del_{p['id']}"):
                        supabase.table('products').delete().eq('id', p['id']).execute()
                        st.rerun()

    # --- تبويب الحالات والربط ---
    with tab2:
        st.subheader(f"📲 {T['status']}")
        if not m_inst or not m_tok:
            st.warning("Admin must assign Instance ID and Token first.")
        elif ws_status != "authenticated":
            st.info("Scan QR to Link WhatsApp")
            qr_url = f"https://api.ultramsg.com/{m_inst}/instance/qr?token={m_tok}&t={int(time.time())}"
            st.image(qr_url, width=300)
        else:
            st.success("Connected ✅")
            setup_webhook(m_inst, m_tok)
            if st.button(T['logout_wa']):
                requests.get(f"https://api.ultramsg.com/{m_inst}/instance/logout?token={m_tok}")
                st.rerun()

    # --- تبويب الطلبات ---
    with tab3:
        st.subheader(f"🛒 {T['orders_title']}")
        # جلب الطلبات من جدول orders
        o_res = supabase.table('orders').select("*").eq('merchant_phc', st.session_state.merchant_phone).order('created_at', desc=True).execute()
        if o_res.data:
            for o in o_res.data:
                with st.expander(f"Order from: {o['customer_pho']} - {o['status']}"):
                    st.write(f"📦 **Product:** {o['product_name']}")
                    st.write(f"💰 **Total:** {o['total_price']} UM")
                    st.write(f"📅 **Date:** {o['created_at']}")
                    # تغيير حالة الطلب
                    new_o_status = st.selectbox("Update Status", ["طلب جديد", "قيد التوصيل", "تم التسليم"], index=0, key=f"o_{o['id']}")
                    if st.button("Update", key=f"btn_o_{o['id']}"):
                        supabase.table('orders').update({"status": new_o_status}).eq('id', o['id']).execute()
                        st.rerun()
        else:
            st.info("No orders received yet.")

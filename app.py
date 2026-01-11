import streamlit as st
from supabase import create_client
import pandas as pd
import uuid
import requests

# --- 1. إعدادات السحابة (Supabase) ---
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. إعدادات UltraMsg ---
INSTANCE_ID = "instance158049" 
API_TOKEN = "vs7zx4mnvuim0l1h"

# --- 3. قاموس اللغات (تحديث التراجم لتشمل الأزرار الجديدة) ---
languages = {
    "العربية": {
        "dir": "rtl",
        "title": "RimStore - لوحة تحكم التاجر",
        "sidebar_title": "🔐 بوابة التاجر",
        "auth_mode": ["تسجيل دخول", "إنشاء حساب جديد"],
        "login": "دخول",
        "signup": "إنشاء الحساب والدخول",
        "phone": "رقم الواتساب",
        "password": "كلمة السر",
        "store_name": "اسم المتجر",
        "tabs": ["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"],
        "add_prod_title": "إضافة بضاعة جديدة",
        "p_name": "📍 اسم المنتج",
        "p_price": "💰 السعر",
        "save": "حفظ ونشر المنتج",
        "qr_btn": "توليد رمز الـ QR",
        "logout": "تسجيل الخروج",
        "delete": "حذف",
        "update": "تحديث السعر"
    },
    "Français": {
        "dir": "ltr",
        "title": "RimStore - Dashboard Marchand",
        "sidebar_title": "🔐 Portail Marchand",
        "auth_mode": ["Connexion", "Créer un compte"],
        "login": "Se connecter",
        "signup": "S'inscrire",
        "phone": "Numéro WhatsApp",
        "password": "Mot de passe",
        "store_name": "Nom de la boutique",
        "tabs": ["➕ Ajouter Produit", "✏️ Gestion Prix", "🛒 Commandes", "📲 Liaison WhatsApp"],
        "add_prod_title": "Ajouter un nouveau produit",
        "p_name": "📍 Nom du produit",
        "p_price": "💰 Prix",
        "save": "Enregistrer le produit",
        "qr_btn": "Générer le code QR",
        "logout": "Déconnexion",
        "delete": "Supprimer",
        "update": "Modifier le prix"
    }
}

# --- إعدادات الصفحة واللغة ---
if 'lang' not in st.session_state: st.session_state.lang = "العربية"
st.sidebar.title("🌐 Language / اللغة")
st.session_state.lang = st.sidebar.selectbox("", ["العربية", "Français"])
t = languages[st.session_state.lang]

st.set_page_config(page_title=t["title"], layout="wide")

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- بوابة التوثيق (Login/Signup) ---
if not st.session_state.logged_in:
    st.sidebar.title(t["sidebar_title"])
    auth_mode = st.sidebar.radio("", t["auth_mode"])

    if auth_mode in ["تسجيل دخول", "Connexion"]:
        auth_phone = st.sidebar.text_input(t["phone"])
        password = st.sidebar.text_input(t["password"], type="password")
        if st.sidebar.button(t["login"]):
            res = supabase.table('merchants').select("*").eq('Phone', auth_phone).eq('password', password).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = auth_phone
                st.session_state.store_name = res.data[0]['Store_name']
                st.rerun()
            else: st.sidebar.error("❌ الخطأ في البيانات")
    else:
        new_phone = st.sidebar.text_input(t["phone"])
        new_store = st.sidebar.text_input(t["store_name"])
        new_pass = st.sidebar.text_input(t["password"], type="password")
        if st.sidebar.button(t["signup"]):
            supabase.table('merchants').insert({"Phone": new_phone, "Store_name": new_store, "password": new_pass}).execute()
            st.session_state.logged_in = True
            st.session_state.merchant_phone = new_phone
            st.session_state.store_name = new_store
            st.rerun()

# --- لوحة التحكم الرئيسية بعد الدخول ---
if st.session_state.logged_in:
    st.sidebar.success(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button(t["logout"]):
        st.session_state.logged_in = False
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(t["tabs"])

    # 1. إضافة منتج
    with tab1:
        st.subheader(t["add_prod_title"])
        with st.form("add_form"):
            p_name = st.text_input(t["p_name"])
            p_price = st.text_input(t["p_price"])
            uploaded_file = st.file_uploader("📸 Image", type=['jpg', 'png', 'jpeg'])
            if st.form_submit_button(t["save"]):
                if p_name and p_price and uploaded_file:
                    file_name = f"{uuid.uuid4()}.png"
                    supabase.storage.from_('product-images').upload(file_name, uploaded_file.read())
                    img_url = supabase.storage.from_('product-images').get_public_url(file_name)
                    supabase.table('products').insert({
                        "Phone": st.session_state.merchant_phone,
                        "Product": p_name, "Price": p_price, "Image_url": img_url
                    }).execute()
                    st.success("✅ تم حفظ المنتج")
                    st.rerun()

    # 2. إدارة الأسعار (تعديل وحذف) - ميزة جديدة
    with tab2:
        st.subheader(t["tabs"][1])
        prods = supabase.table('products').select("*").eq('Phone', st.session_state.merchant_phone).execute()
        if prods.data:
            for p in prods.data:
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                with col1: st.write(f"**{p['Product']}**")
                with col2: new_val = st.text_input(f"السعر لـ {p['Product']}", value=p['Price'], key=f"p_{p['id']}")
                with col3:
                    if st.button(t["update"], key=f"up_{p['id']}"):
                        supabase.table('products').update({"Price": new_val}).eq('id', p['id']).execute()
                        st.rerun()
                with col4:
                    if st.button(t["delete"], key=f"del_{p['id']}"):
                        supabase.table('products').delete().eq('id', p['id']).execute()
                        st.rerun()

    # 3. الطلبات (مباشرة من البوت)
    with tab3:
        st.subheader(t["tabs"][2])
        orders = supabase.table('orders').select("*").eq('merchant_phone', st.session_state.merchant_phone).execute()
        if orders.data:
            df = pd.DataFrame(orders.data)
            st.dataframe(df[["customer_phone", "product_name", "total_price", "status", "created_at"]])
        else: st.info("لا توجد طلبات جديدة")

    # 4. ربط الواتساب (QR Code)
    with tab4:
        st.subheader(t["tabs"][3])
        qr_url = f"https://api.ultramsg.com/{INSTANCE_ID}/instance/qr?token={API_TOKEN}"
        if st.button(t["qr_btn"]):
            st.image(qr_url, caption="Scan this with your WhatsApp", width=300)

import streamlit as st
from supabase import create_client
import pandas as pd
import uuid
import time

# --- 1. إعدادات السحابة (Supabase) ---
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. إعدادات UltraMsg ---
INSTANCE_ID = "instance158049" 
API_TOKEN = "vs7zx4mnvuim0l1h"

# --- 3. قاموس اللغات الاحترافي ---
languages = {
    "العربية": {
        "dir": "rtl", "title": "RimStore - التاجر الذكي",
        "sidebar_title": "🔐 دخول التجار", "phone": "رقم الواتساب",
        "password": "كلمة السر", "store_name": "اسم المتجر",
        "tabs": ["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"],
        "add_prod_title": "إضافة بضاعة جديدة", "p_name": "📍 اسم المنتج",
        "p_price": "💰 السعر (أوقية)", "save": "حفظ ونشر المنتج",
        "qr_btn": "توليد رمز الـ QR الآن", "logout": "تسجيل الخروج",
        "delete": "حذف", "update": "تعديل", "loading": "جاري التحميل..."
    },
    "Français": {
        "dir": "ltr", "title": "RimStore - Smart Merchant",
        "sidebar_title": "🔐 Accès Marchand", "phone": "WhatsApp Number",
        "password": "Mot de passe", "store_name": "Nom Boutique",
        "tabs": ["➕ Produit", "✏️ Prix", "🛒 Commandes", "📲 Liaison"],
        "add_prod_title": "Nouveau Produit", "p_name": "📍 Nom",
        "p_price": "💰 Prix", "save": "Enregistrer",
        "qr_btn": "Générer QR Code", "logout": "Déconnexion",
        "delete": "Suppr.", "update": "Modifier", "loading": "Chargement..."
    }
}

# --- إعدادات الصفحة الافتراضية ---
if 'lang' not in st.session_state: st.session_state.lang = "العربية"
st.sidebar.title("🌐")
st.session_state.lang = st.sidebar.selectbox("Language", ["العربية", "Français"])
t = languages[st.session_state.lang]

st.set_page_config(page_title=t["title"], layout="wide", initial_sidebar_state="expanded")

# --- وظائف سريعة (Caching) لتحسين السرعة ---
def get_products(phone):
    return supabase.table('products').select("*").eq('Phone', phone).execute()

def get_orders(phone):
    return supabase.table('orders').select("*").eq('merchant_phone', phone).execute()

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.sidebar:
        st.title(t["sidebar_title"])
        auth_mode = st.radio("", ["Login", "Signup"] if st.session_state.lang == "Français" else ["تسجيل دخول", "إنشاء حساب"])
        
        phone = st.text_input(t["phone"], placeholder="222xxxxxxx")
        pwd = st.text_input(t["password"], type="password")
        
        if "Signup" in auth_mode or "إنشاء" in auth_mode:
            store = st.text_input(t["store_name"])
            if st.button(t["save"]):
                supabase.table('merchants').insert({"Phone": phone, "Store_name": store, "password": pwd}).execute()
                st.success("Success!")
        else:
            if st.button(t["logout"].replace("الخروج", "الدخول")):
                res = supabase.table('merchants').select("*").eq('Phone', phone).eq('password', pwd).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = phone
                    st.session_state.store_name = res.data[0]['Store_name']
                    st.rerun()
                else: st.error("❌ Error")

# --- لوحة التحكم ---
if st.session_state.logged_in:
    st.title(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button(t["logout"]):
        st.session_state.logged_in = False
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(t["tabs"])

    with tab1:
        st.subheader(t["add_prod_title"])
        with st.form("fast_add", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            name = col_a.text_input(t["p_name"])
            price = col_b.text_input(t["p_price"])
            img = st.file_uploader("📸 Image", type=['jpg', 'png', 'jpeg'])
            if st.form_submit_button(t["save"]):
                with st.spinner(t["loading"]):
                    img_id = f"{uuid.uuid4()}.png"
                    supabase.storage.from_('product-images').upload(img_id, img.read())
                    url = supabase.storage.from_('product-images').get_public_url(img_id)
                    supabase.table('products').insert({
                        "Phone": st.session_state.merchant_phone,
                        "Product": name, "Price": price, "Image_url": url
                    }).execute()
                    st.balloons()
                    st.success("✅ Done")

    with tab2:
        st.subheader(t["tabs"][1])
        prods = get_products(st.session_state.merchant_phone)
        for p in prods.data:
            with st.expander(f"📦 {p['Product']} - {p['Price']} MRU"):
                c1, c2 = st.columns(2)
                new_p = c1.text_input(t["p_price"], value=p['Price'], key=f"v_{p['id']}")
                if c2.button(t["update"], key=f"u_{p['id']}"):
                    supabase.table('products').update({"Price": new_p}).eq('id', p['id']).execute()
                    st.rerun()
                if st.button(t["delete"], key=f"d_{p['id']}", type="secondary"):
                    supabase.table('products').delete().eq('id', p['id']).execute()
                    st.rerun()

    with tab3:
        st.subheader(t["tabs"][2])
        ord_data = get_orders(st.session_state.merchant_phone)
        if ord_data.data:
            st.table(pd.DataFrame(ord_data.data)[["customer_phone", "product_name", "total_price", "status"]])
        else: st.info("No orders yet")

    with tab4:
        st.subheader(t["tabs"][3])
        # ميزة الـ QR Code المستقر
        qr_url = f"https://api.ultramsg.com/{INSTANCE_ID}/instance/qr?token={API_TOKEN}&timestamp={int(time.time())}"
        st.info("💡 امسحي الرمز من هاتفك لربط البوت بالمتجر.")
        if st.button(t["qr_btn"]):
            with st.spinner(t["loading"]):
                st.image(qr_url, width=350)
                st.markdown(f"**[رابط مباشر للرمز في حال لم يظهر اضغطي هنا]({qr_url})**")

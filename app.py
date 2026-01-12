import streamlit as st
from supabase import create_client
import pandas as pd
import uuid
import time

# --- 1. إعدادات السحابة ---
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. إعدادات UltraMsg ---
INSTANCE_ID = "instance158049" 
API_TOKEN = "vs7zx4mnvuim0l1h"

# --- 3. اللغات مع إضافة المقاس واللون والحالة ---
languages = {
    "العربية": {
        "dir": "rtl", "tabs": ["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"],
        "p_name": "📍 اسم المنتج", "p_price": "💰 السعر", "p_size": "📏 المقاسات",
        "p_color": "🎨 الألوان", "p_stock": "📦 الحالة", "stock_true": "متوفر", "stock_false": "نفد",
        "save": "حفظ ونشر", "qr_btn": "توليد الرمز", "loading": "جاري الحفظ...", "update": "تحديث"
    },
    "Français": {
        "dir": "ltr", "tabs": ["➕ Produit", "✏️ Prix", "🛒 Commandes", "📲 Liaison"],
        "p_name": "📍 Nom", "p_price": "💰 Prix", "p_size": "📏 Tailles",
        "p_color": "🎨 Couleurs", "p_stock": "📦 État", "stock_true": "Disponible", "stock_false": "Rupture",
        "save": "Enregistrer", "qr_btn": "Générer QR", "loading": "Chargement...", "update": "Modifier"
    }
}

if 'lang' not in st.session_state: st.session_state.lang = "العربية"
st.sidebar.title("🌐")
st.session_state.lang = st.sidebar.selectbox("Language", ["العربية", "Français"])
t = languages[st.session_state.lang]

st.set_page_config(page_title="RimStore Dashboard", layout="wide")

# (جزء تسجيل الدخول يظل كما هو...)
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- لوحة التحكم ---
if st.session_state.logged_in:
    tab1, tab2, tab3, tab4 = st.tabs(t["tabs"])

    with tab1:
        st.subheader("➕ إضافة بضاعة جديدة")
        with st.form("advanced_add", clear_on_submit=True):
            col1, col2 = st.columns(2)
            name = col1.text_input(t["p_name"])
            price = col2.text_input(t["p_price"])
            sizes = col1.text_input(t["p_size"])
            colors = col2.text_input(t["p_color"])
            
            # خانة حالة المنتج (متوفر أم لا)
            status = st.selectbox(t["p_stock"], [t["stock_true"], t["stock_false"]])
            
            img = st.file_uploader("📸 صورة المنتج", type=['jpg', 'png', 'jpeg'])
            
            if st.form_submit_button(t["save"]):
                if name and price and img:
                    with st.spinner(t["loading"]):
                        img_id = f"{uuid.uuid4()}.png"
                        supabase.storage.from_('product-images').upload(img_id, img.read())
                        url = supabase.storage.from_('product-images').get_public_url(img_id)
                        
                        supabase.table('products').insert({
                            "Phone": st.session_state.merchant_phone,
                            "Product": name, "Price": price, 
                            "Size": sizes, "Color": colors,
                            "Status": True if status == t["stock_true"] else False, # حالة المنتج
                            "Image_url": url
                        }).execute()
                        st.success("✅ تم الحفظ")

    with tab2:
        st.subheader(t["tabs"][1])
        res = supabase.table('products').select("*").eq('Phone', st.session_state.merchant_phone).execute()
        for p in res.data:
            with st.expander(f"📦 {p['Product']} ({t['stock_true'] if p['Status'] else t['stock_false']})"):
                c1, c2, c3 = st.columns(3)
                new_p = c1.text_input(t["p_price"], value=p['Price'], key=f"v_{p['id']}")
                new_s = c2.selectbox(t["p_stock"], [t["stock_true"], t["stock_false"]], 
                                     index=0 if p['Status'] else 1, key=f"s_{p['id']}")
                if c3.button(t["update"], key=f"u_{p['id']}"):
                    supabase.table('products').update({
                        "Price": new_p, 
                        "Status": True if new_s == t["stock_true"] else False
                    }).eq('id', p['id']).execute()
                    st.rerun()

    with tab4:
        qr_url = f"https://api.ultramsg.com/{INSTANCE_ID}/instance/qr?token={API_TOKEN}&timestamp={int(time.time())}"
        if st.button(t["qr_btn"]):
            st.image(qr_url, width=350)
            st.markdown(f"[رابط مباشر للرمز]({qr_url})")

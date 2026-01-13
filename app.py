import streamlit as st
from supabase import create_client
import uuid
import time
import requests

# --- 1. إعدادات السحابة (Supabase) ---
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. إعدادات UltraMsg ---
INSTANCE_ID = "instance158049" 
API_TOKEN = "vs7zx4mnvuim0l1h"

# --- 3. قاموس اللغات ---
languages = {
    "العربية": {
        "dir": "rtl", "title": "RimStore - لوحة التاجر",
        "sidebar_title": "🔐 دخول التجار", "phone": "رقم الواتساب",
        "password": "كلمة السر", "store_name": "اسم المتجر",
        "tabs": ["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"],
        "p_name": "📍 اسم المنتج", "p_price": "💰 السعر", "p_size": "📏 المقاسات",
        "p_color": "🎨 الألوان", "p_stock": "📦 الحالة", "stock_true": "متوفر", "stock_false": "ماه خالك عندنا ظرك",
        "save": "حفظ ونشر", "update": "تحديث", "loading": "جاري الحفظ..."
    },
    "Français": {
        "dir": "ltr", "title": "RimStore - Dashboard",
        "sidebar_title": "🔐 Connexion", "phone": "Numéro WhatsApp",
        "password": "Mot de passe", "store_name": "Nom Boutique",
        "tabs": ["➕ Ajouter", "✏️ Prix", "🛒 Commandes", "📲 Liaison"],
        "p_name": "📍 Nom", "p_price": "💰 Prix", "p_size": "📏 Tailles",
        "p_color": "🎨 Couleurs", "p_stock": "📦 État", "stock_true": "Disponible", "stock_false": "Rupture",
        "save": "Enregistrer", "update": "Modifier", "loading": "Chargement..."
    }
}

st.set_page_config(page_title="RimStore", layout="wide")

if 'lang' not in st.session_state: st.session_state.lang = "العربية"
st.sidebar.title("🌐 Language")
st.session_state.lang = st.sidebar.selectbox("اختر اللغة / Langue", ["العربية", "Français"])
t = languages[st.session_state.lang]

if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- إصلاح واجهة الدخول وإنشاء الحساب ---
if not st.session_state.logged_in:
    with st.sidebar:
        st.title(t["sidebar_title"])
        auth_mode = st.radio("العملية", ["تسجيل دخول", "إنشاء حساب"] if st.session_state.lang == "العربية" else ["Connexion", "Signup"])
        
        phone = st.text_input(t["phone"], placeholder="222xxxxxxx")
        pwd = st.text_input(t["password"], type="password")
        
        store_name = ""
        if "إنشاء" in auth_mode or "Signup" in auth_mode:
            store_name = st.text_input(t["store_name"], placeholder="اسم متجرك هنا")
        
        if st.button("تأكيد / Confirmer"):
            if "إنشاء" in auth_mode or "Signup" in auth_mode:
                if phone and pwd and store_name:
                    supabase.table('merchants').insert({"Phone": phone, "Store_name": store_name, "password": pwd}).execute()
                    st.success("تم إنشاء الحساب! يمكنك الدخول الآن.")
                else:
                    st.error("يرجى ملء جميع الحقول")
            else:
                res = supabase.table('merchants').select("*").eq('Phone', phone).eq('password', pwd).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = phone
                    st.session_state.store_name = res.data[0]['Store_name']
                    st.rerun()
                else: st.error("❌ خطأ في رقم الهاتف أو كلمة السر")

# --- واجهة المتجر بعد الدخول ---
if st.session_state.logged_in:
    st.sidebar.success(f"🏪 {st.session_state.store_name}")
    if st.sidebar.button("تسجيل الخروج"):
        st.session_state.logged_in = False
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(t["tabs"])

    with tab1:
        st.subheader(t["tabs"][0])
        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            p_name = col1.text_input(t["p_name"])
            p_price = col2.text_input(t["p_price"])
            p_size = col1.text_input(t["p_size"])
            p_color = col2.text_input(t["p_color"])
            p_stock = st.selectbox(t["p_stock"], [t["stock_true"], t["stock_false"]])
            img = st.file_uploader("📸 Image", type=['jpg', 'png', 'jpeg'])
            
            if st.form_submit_button(t["save"]):
                if p_name and p_price and img:
                    with st.spinner(t["loading"]):
                        img_id = f"{uuid.uuid4()}.png"
                        supabase.storage.from_('product-images').upload(img_id, img.read())
                        url = supabase.storage.from_('product-images').get_public_url(img_id)
                        supabase.table('products').insert({
                            "Phone": st.session_state.merchant_phone,
                            "Product": p_name, "Price": p_price, 
                            "Size": p_size, "Color": p_color,
                            "Status": True if p_stock == t["stock_true"] else False,
                            "Image_url": url
                        }).execute()
                        st.success("✅ تم نشر المنتج")

    with tab2:
        st.subheader(t["tabs"][1])
        prods = supabase.table('products').select("*").eq('Phone', st.session_state.merchant_phone).execute()
        if prods.data:
            for p in prods.data:
                with st.expander(f"📦 {p['Product']}"):
                    c1, c2 = st.columns(2)
                    new_val = c1.text_input(t["p_price"], value=p['Price'], key=f"v_{p['id']}")
                    new_st = c2.selectbox(t["p_stock"], [t["stock_true"], t["stock_false"]], 
                                          index=0 if p['Status'] else 1, key=f"s_{p['id']}")
                    if st.button(t["update"], key=f"u_{p['id']}"):
                        supabase.table('products').update({
                            "Price": new_val, 
                            "Status": True if new_st == t["stock_true"] else False
                        }).eq('id', p['id']).execute()
                        st.rerun()

    with tab4:
        st.subheader(t["tabs"][3])
        status_url = f"https://api.ultramsg.com/{INSTANCE_ID}/instance/status?token={API_TOKEN}"
        
        try:
            res = requests.get(status_url, timeout=10).json()
            server_status = res.get("status", "unknown")
        except:
            server_status = "error"

        if server_status == "authenticated":
            st.success("✅ البوت مرتبط تماماً ونشط.")
            st.info("البوت يعمل الآن في الخلفية، يمكنك إضافة المنتجات وسيرد تلقائياً على الزبائن.")
            if st.button("🔄 تحديث الحالة"):
                st.rerun()
            with st.expander("⚙️ خيارات متقدمة"):
                if st.button("🔴 إلغاء ربط الجهاز الحالي"):
                    requests.get(f"https://api.ultramsg.com/{INSTANCE_ID}/instance/logout?token={API_TOKEN}")
                    st.rerun()
        
        else:
            st.warning("⚠️ مطلوب ربط الواتساب لتفعيل الرد التلقائي.")
            qr_url = f"https://api.ultramsg.com/{INSTANCE_ID}/instance/qr?token={API_TOKEN}&t={int(time.time())}"
            st.image(qr_url, caption="افتح واتساب > الأجهزة المرتبطة > ربط جهاز", width=300)
            
            if st.button("🧹 تنظيف الجلسة وإعادة المحاولة"):
                requests.get(f"https://api.ultramsg.com/{INSTANCE_ID}/instance/logout?token={API_TOKEN}")
                time.sleep(2)
                st.rerun()

    with tab3:
        st.subheader("🛒 الطلبات القادمة")
        st.info("سيتم عرض طلبات الزبائن هنا فور وصولها عبر الواتساب.")

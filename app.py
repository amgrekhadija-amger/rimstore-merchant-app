import streamlit as st
from supabase import create_client
import uuid
import time
import requests

# إعدادات ثابتة
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
INSTANCE_ID = "instance158049" 
API_TOKEN = "vs7zx4mnvuim0l1h"

st.set_page_config(page_title="RimStore Platform", layout="wide")

# التحقق من حالة الواتساب لربطها بوضعية التاجر
def check_whatsapp_status():
    try:
        res = requests.get(f"https://api.ultramsg.com/{INSTANCE_ID}/instance/status?token={API_TOKEN}", timeout=5).json()
        return res.get("status", "disconnected")
    except:
        return "error"

if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- واجهة الدخول الذكية ---
if not st.session_state.logged_in:
    auth_mode = st.sidebar.radio("العملية", ["تسجيل دخول", "إنشاء حساب تاجر جديد"])
    u_phone = st.sidebar.text_input("رقم الواتساب")
    u_pwd = st.sidebar.text_input("كلمة السر", type="password")
    
    if auth_mode == "إنشاء حساب تاجر جديد":
        u_store = st.sidebar.text_input("اسم المتجر")
        if st.sidebar.button("تأسيس المتجر"):
            supabase.table('merchants').insert({"Phone": u_phone, "Store_name": u_store, "password": u_pwd}).execute()
            st.success("تم التأسيس بنجاح!")

    if auth_mode == "تسجيل دخول":
        if st.sidebar.button("دخول اللوحة"):
            res = supabase.table('merchants').select("*").eq('Phone', u_phone).eq('password', u_pwd).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0]['Store_name']
                st.rerun()

# --- لوحة التحكم المتكاملة ---
if st.session_state.logged_in:
    # فحص الارتباط فوراً
    ws_status = check_whatsapp_status()
    
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    
    # إذا تم حذف الجهاز من واتساب، تظهر علامة حمراء في الجانب
    if ws_status != "authenticated":
        st.sidebar.error("⚠️ الواتساب غير مرتبط!")
    else:
        st.sidebar.success("✅ النظام نشط ومترابط")

    tab1, tab2, tab3 = st.tabs(["📦 إدارة المنتجات", "📊 حالة النظام", "🛒 طلبات الزبائن"])

    with tab1:
        st.subheader("إضافة منتج جديد (سيظهر فوراً في البوت)")
        with st.form("product_sync", clear_on_submit=True):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر (أوقية)")
            p_img = st.file_uploader("صورة المنتج", type=['jpg', 'png'])
            if st.form_submit_button("حفظ ونشر آلي"):
                if p_name and p_price and p_img:
                    img_id = f"{uuid.uuid4()}.png"
                    supabase.storage.from_('product-images').upload(img_id, p_img.read())
                    img_url = supabase.storage.from_('product-images').get_public_url(img_id)
                    # الحفظ في Supabase يجعل البوت يراه فوراً
                    supabase.table('products').insert({
                        "Phone": st.session_state.merchant_phone,
                        "Product": p_name, "Price": p_price,
                        "Image_url": img_url, "Status": True
                    }).execute()
                    st.success("تم التحديث! البوت الآن يعرف المنتج الجديد.")

    with tab2:
        st.subheader("📲 تسلسل الربط (UltraMsg)")
        if ws_status != "authenticated":
            st.info("قم بمسح الرمز لربط متجرك بالواتساب:")
            qr_url = f"https://api.ultramsg.com/{INSTANCE_ID}/instance/qr?token={API_TOKEN}&t={int(time.time())}"
            st.image(qr_url, width=300)
            if st.button("تحديث بعد المسح"): st.rerun()
        else:
            st.success("النظام يعمل بتسلسل صحيح. الرسائل تصل لـ PythonAnywhere والبيانات تُجلب من Supabase.")
            if st.button("🔴 تسجيل خروج الجهاز"):
                requests.get(f"https://api.ultramsg.com/{INSTANCE_ID}/instance/logout?token={API_TOKEN}")
                st.rerun()

import streamlit as st
from supabase import create_client
import uuid
import time
import requests

# --- 1. إعدادات السحاب (Supabase) ---
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# رابط Webhook الخاص بملف bot.py على PythonAnywhere
WEBHOOK_URL = "https://khadija.pythonanywhere.com/whatsapp"

st.set_page_config(page_title="RimStore Platform", layout="wide")

# دالة للتحقق من حالة الواتساب لكل تاجر بشكل مستقل
def check_whatsapp_status(inst, tok):
    if not inst or not tok: return "disconnected"
    try:
        url = f"https://api.ultramsg.com/{inst}/instance/status?token={tok}"
        res = requests.get(url, timeout=5).json()
        return res.get("status", "disconnected")
    except:
        return "error"

# دالة لتفعيل الـ Webhook آلياً لضمان عمل الردود
def setup_webhook(inst, tok):
    url = f"https://api.ultramsg.com/{inst}/instance/settings"
    params = {"token": tok, "webhook_url": WEBHOOK_URL, "webhook_message_received": "true"}
    try: requests.get(url, params=params)
    except: pass

if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- واجهة الدخول ---
if not st.session_state.logged_in:
    auth_mode = st.sidebar.radio("العملية", ["تسجيل دخول", "إنشاء حساب تاجر جديد"])
    u_phone = st.sidebar.text_input("رقم الواتساب (بدون +)")
    u_pwd = st.sidebar.text_input("كلمة السر", type="password")
    
    if auth_mode == "إنشاء حساب تاجر جديد":
        u_store = st.sidebar.text_input("اسم المتجر")
        if st.sidebar.button("تأسيس المتجر"):
            # إنشاء الحساب مع إبقاء instance_id و api_token فارغين ليتم تعبئتهما من الإدارة
            supabase.table('merchants').insert({
                "Phone": u_phone, 
                "Store_name": u_store, 
                "password": u_pwd,
                "is_active": False
            }).execute()
            st.success("تم التأسيس بنجاح! تواصل مع الإدارة لتفعيل البوت.")

    if auth_mode == "تسجيل دخول":
        if st.sidebar.button("دخول اللوحة"):
            res = supabase.table('merchants').select("*").eq('Phone', u_phone).eq('password', u_pwd).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0]['Store_name']
                st.rerun()
            else:
                st.error("بيانات الدخول غير صحيحة")

# --- لوحة التحكم ---
if st.session_state.logged_in:
    # جلب بيانات التاجر الحالية من السحاب
    res_m = supabase.table('merchants').select("*").eq('Phone', st.session_state.merchant_phone).execute()
    m_data = res_m.data[0]
    m_inst = m_data.get('instance_id')
    m_tok = m_data.get('api_token')

    # فحص حالة الارتباط
    ws_status = check_whatsapp_status(m_inst, m_tok)
    
    st.sidebar.title(f"🏪 {st.session_state.store_name}")
    
    if ws_status != "authenticated":
        st.sidebar.error("⚠️ الواتساب غير مرتبط!")
    else:
        st.sidebar.success("✅ النظام نشط ومترابط")
        # تفعيل الـ Webhook فورياً عند التأكد من الارتباط لضمان عمل bot.py
        setup_webhook(m_inst, m_tok)

    tab1, tab2, tab3 = st.tabs(["📦 إدارة المنتجات", "📊 حالة النظام", "🛒 طلبات الزبائن"])

    with tab1:
        st.subheader("إضافة منتج جديد")
        with st.form("product_sync", clear_on_submit=True):
            p_name = st.text_input("اسم المنتج")
            p_price = st.text_input("السعر (أوقية)")
            p_img = st.file_uploader("صورة المنتج", type=['jpg', 'png'])
            if st.form_submit_button("حفظ ونشر آلي"):
                if p_name and p_price and p_img:
                    img_id = f"{uuid.uuid4()}.png"
                    supabase.storage.from_('product-images').upload(img_id, p_img.read())
                    img_url = supabase.storage.from_('product-images').get_public_url(img_id)
                    # ربط المنتج برقم هاتف التاجر
                    supabase.table('products').insert({
                        "Phone": st.session_state.merchant_phone,
                        "Product": p_name, "Price": p_price,
                        "Image_url": img_url, "Status": True
                    }).execute()
                    st.success("تم الحفظ! البوت سيتعرف عليه فوراً.")

    with tab2:
        st.subheader("📲 ربط الواتساب")
        if not m_inst or not m_tok:
            st.warning("لم يتم تخصيص خط بوت لهذا الحساب بعد. يرجى مراجعة الإدارة.")
        elif ws_status != "authenticated":
            st.info("امسح الرمز لربط متجرك:")
            qr_url = f"https://api.ultramsg.com/{m_inst}/instance/qr?token={m_tok}&t={int(time.time())}"
            st.image(qr_url, width=300)
            if st.button("تحديث الحالة"): st.rerun()
        else:
            st.success("حسابك مرتبط وجاهز للرد على الزبائن.")
            if st.button("🔴 تسجيل خروج الجهاز"):
                requests.get(f"https://api.ultramsg.com/{m_inst}/instance/logout?token={m_tok}")
                # تحديث الحالة في السحاب ليظهر كغير متصل
                supabase.table('merchants').update({"is_active": False}).eq('Phone', st.session_state.merchant_phone).execute()
                st.rerun()

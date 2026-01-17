import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
import requests
import time 

# 1. إعداد الصفحة
st.set_page_config(page_title="لوحة تحكم المتجر", layout="wide")

# 2. تحميل الإعدادات
env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MY_GATEWAY_URL = os.getenv("MY_GATEWAY_URL", "http://46.224.250.252:3000")

# 3. الاتصال بقاعدة البيانات
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ خطأ في ملف .env")
    st.stop()

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ خطأ اتصال: {e}")
    st.stop()

# --- 4. واجهة الدخول وإنشاء الحساب ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "✨ إنشاء حساب جديد"])
    
    with tab_login:
        with st.form("login_form"):
            st.subheader("تسجيل الدخول")
            l_phone = st.text_input("رقم واتساب التاجر")
            l_pass = st.text_input("كلمة السر", type="password")
            if st.form_submit_button("دخول"):
                res = supabase.table('merchants').select("*").eq("Phone", l_phone).eq("password", l_pass).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.merchant_phone = l_phone
                    # تخزين اسم المتجر في الـ session لاستخدامه في العناوين
                    st.session_state.store_name = res.data[0].get('Store_name', 'المتجر')
                    st.rerun()
                else:
                    st.error("بيانات الدخول غير صحيحة")

    with tab_signup:
        with st.form("signup_form"):
            st.subheader("فتح متجر جديد")
            s_name = st.text_input("اسم التاجر (أو المحل)")
            s_phone = st.text_input("رقم الواتساب")
            s_pass = st.text_input("كلمة سر للمتجر", type="password")
            if st.form_submit_button("إنشاء الحساب"):
                try:
                    supabase.table('merchants').insert({"Store_name": s_name, "Phone": s_phone, "password": s_pass}).execute()
                    st.success("تم إنشاء الحساب بنجاح! انتقل لتسجيل الدخول.")
                except Exception as e:
                    st.error(f"حدث خطأ: تأكد أن الرقم غير مسجل مسبقاً")

else:
    # جلب اسم المتجر المسجل
    current_store = st.session_state.get('store_name', 'متجرك')

    # --- 5. لوحة التحكم الرئيسية بعد الدخول ---
    # هنا تم استبدال RimStore باسم المتجر الخاص بالتاجر
    st.title(f"🏪 لوحة تحكم: {current_store}")
    
    tab1, tab2, tab3, tab4 = st.tabs(["➕ إضافة منتج", "✏️ إدارة الأسعار", "🛒 الطلبات", "📲 ربط الواتساب"])
    
    # قسم إضافة منتج
    with tab1:
        st.subheader(f"📦 إضافة بضاعة جديدة لـ {current_store}")
        with st.form("add_product", clear_on_submit=True):
            p_name = st.text_input("📍 اسم المنتج")
            p_price = st.number_input("💰 سعر المنتج", min_value=0)
            p_sizes = st.text_input("📏 المقاسات (مثال: S, M, L, XL)")
            p_colors = st.text_input("🎨 الألوان (مثال: أحمر, أزرق)")
            p_img = st.file_uploader("🖼️ رفع صورة المنتج", type=['jpg', 'png', 'jpeg'])
            if st.form_submit_button("حفظ المنتج"):
                try:
                    product_data = {
                        "Product": p_name, 
                        "Price": str(p_price), 
                        "Size": p_sizes, 
                        "Color": p_colors, 
                        "Phone": st.session_state.merchant_phone
                    }
                    supabase.table('products').insert(product_data).execute()
                    st.success(f"تمت إضافة {p_name} بنجاح!")
                except Exception as e:
                    st.error(f"خطأ في الحفظ: {e}")

    # قسم إدارة الأسعار
    with tab2:
        st.subheader("✏️ إدارة المنتجات والأسعار")
        res_p = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        if res_p.data:
            df = pd.DataFrame(res_p.data)
            for index, row in df.iterrows():
                cols = st.columns([2, 1, 1, 1])
                cols[0].write(row['Product']) 
                cols[1].write(f"{row['Price']} MRU") 
                status = cols[2].selectbox("الحالة", ["متوفر", "غير متوفر"], index=0 if row['Status'] else 1, key=f"status_{row['id']}")
                if cols[3].button("تحديث", key=f"btn_{row['id']}"):
                    new_status = True if status == "متوفر" else False
                    supabase.table('products').update({"Status": new_status}).eq("id", row['id']).execute()
                    st.rerun()
        else:
            st.info("لا توجد منتجات مضافة بعد.")

    # قسم الطلبات
    with tab3:
        st.subheader("🛒 طلبات الزبائن")
        res_o = supabase.table('orders').select("*").eq("merchant_phone", st.session_state.merchant_phone).execute()
        if res_o.data:
            st.table(res_o.data)
        else:
            st.info("في انتظار استقبال أول طلب...")

    # قسم ربط الواتساب
    with tab4:
        st.subheader("📲 ربط واتساب المتجر")
        merchant_id = st.session_state.merchant_phone
        
        res = supabase.table('merchants').select('session_status, qr_code').eq('Phone', merchant_id).execute()
        current_status = res.data[0].get('session_status') if res.data else "disconnected"
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("توليد رمز QR جديد"):
                try:
                    requests.post(f"{MY_GATEWAY_URL}/init-session", json={"phone": merchant_id}, timeout=5)
                    st.info("جاري تحضير الرمز...")
                    time.sleep(2)
                    st.rerun()
                except:
                    st.error("السيرفر لا يستجيب")
            
            if current_status == 'waiting_qr':
                st.warning("⚠️ الصفحة ستتحدث تلقائياً كل 10 ثوانٍ لظهار الرمز.")
                time.sleep(10)
                st.rerun()

            if res.data and res.data[0].get('qr_code'):
                qr_code_raw = res.data[0].get('qr_code')
                qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_code_raw}"
                st.image(qr_url, caption=f"امسح الرمز لربط {current_store}")

        with col2:
            if current_status == 'connected':
                st.success(f"✅ متصل الآن - بوت {current_store} يعمل")
            elif current_status == 'waiting_qr':
                st.info("⌛ في انتظار مسح الرمز...")
            else:
                st.error("❌ غير متصل حالياً")

    if st.sidebar.button("تسجيل الخروج"):
        st.session_state.logged_in = False
        st.rerun()

import streamlit as st
import os, requests, time
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# --- 1. الإعدادات والجماليات ---
load_dotenv()
PARTNER_KEY = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
WEBHOOK_URL = "https://rimstorebot.pythonanywhere.com/whatsapp" 

st.set_page_config(page_title="لوحة تحكم ريم ستور", layout="wide", page_icon="📲")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .status-card { padding: 20px; border-radius: 12px; background: white; border-right: 5px solid #25D366; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; color: black; }
    .code-box { font-size: 32px; font-family: monospace; color: #075E54; background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center; border: 2px dashed #2196f3; font-weight: bold; margin: 15px 0; }
    </style>
    """, unsafe_allow_html=True)

# الاتصال بـ Supabase
try:
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"⚠️ خطأ اتصال بـ Supabase: {e}")

# --- 2. الدوال التقنية ---

def create_merchant_instance(phone):
    url = f"https://api.green-api.com/partner/createInstance/{PARTNER_KEY}"
    try:
        res = requests.post(url, json={"plan": "developer"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            m_id = str(data.get('idInstance'))
            m_token = data.get('apiTokenInstance')
            supabase.table('merchants').update({
                "instance_id": m_id, "api_token": m_token
            }).eq("Phone", phone).execute()
            # ربط الويب هوك الخاص بـ Botpress
            requests.post(f"https://api.green-api.com/waInstance{m_id}/setSettings/{m_token}", 
                          json={"webhookUrl": WEBHOOK_URL, "incomingMsg": "yes"})
            return m_id, m_token
    except Exception as e:
        st.error(f"💥 خطأ في إنشاء السيرفر: {e}")
    return None, None

def get_pairing_code(m_id, m_token, phone):
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    url = f"https://api.green-api.com/waInstance{m_id}/getPairingCode/{m_token}"
    try:
        res = requests.post(url, json={"phoneNumber": clean_phone}, timeout=20)
        if res.status_code == 200:
            return res.json().get('code')
    except: pass
    return None

# --- 3. نظام الجلسة والدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'last_p_code' not in st.session_state:
    st.session_state.last_p_code = None

if not st.session_state.logged_in:
    with st.form("login"):
        st.title("🔑 دخول التاجر")
        u_phone = st.text_input("رقم الهاتف")
        u_pw = st.text_input("كلمة السر", type="password")
        if st.form_submit_button("دخول"):
            res = supabase.table('merchants').select("*").eq("Phone", u_phone).eq("password", u_pw).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.merchant_phone = u_phone
                st.session_state.store_name = res.data[0].get('Store_name')
                st.rerun()
            else: st.error("بيانات الدخول غير صحيحة")
    st.stop()

# --- 4. الواجهة الرئيسية ---
st.sidebar.title(f"🏪 {st.session_state.store_name}")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.logged_in = False
    st.rerun()

tabs = st.tabs(["➕ إدارة المنتجات", "🛒 الطلبات الواردة", "📲 ربط الواتساب"])

# -- تبويب المنتجات --
with tabs[0]:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📦 أضف منتج جديد")
        with st.form("add_p", clear_on_submit=True):
            name = st.text_input("اسم المنتج")
            price = st.text_input("السعر (أوقية)")
            if st.form_submit_button("حفظ المنتج"):
                supabase.table('products').insert({"Product": name, "Price": price, "Phone": st.session_state.merchant_phone}).execute()
                st.success("تمت إضافة المنتج بنجاح!")
                st.rerun()
    with col2:
        st.subheader("✏️ قائمة المنتجات")
        prods = supabase.table('products').select("*").eq("Phone", st.session_state.merchant_phone).execute()
        if prods.data:
            for p in prods.data:
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{p.get('Product')}** - {p.get('Price')} أوقية")
                if c2.button("🗑️", key=f"del_{p.get('id')}"):
                    supabase.table('products').delete().eq("id", p.get('id')).execute()
                    st.rerun()

# -- تبويب الطلبات --
with tabs[1]:
    st.subheader("🛒 طلبات الزبائن الأخيرة")
    orders = supabase.table('orders').select("*").eq("merchant_phc", st.session_state.merchant_phone).execute()
    if orders.data:
        for o in orders.data:
            st.info(f"👤 الزبون: {o.get('customer_pho')} | طلب: {o.get('product_name')}")
    else: st.write("لا توجد طلبات جديدة حالياً.")

# -- تبويب الواتساب المطور (التعديل المطلوب) --
with tabs[2]:
    st.subheader("📲 ربط الرد الآلي بالواتساب")
    
    m_query = supabase.table('merchants').select("*").eq("Phone", st.session_state.merchant_phone).execute()
    m_data = m_query.data[0] if m_query.data else {}
    m_id = m_data.get('instance_id')
    m_token = m_data.get('api_token')

    if not m_id or m_id == "None":
        st.warning("سيرفر الواتساب غير مفعل حالياً.")
        if st.button("🚀 تفعيل وإنشاء السيرفر"):
            with st.spinner("جاري التواصل مع Green-API..."):
                new_id, new_token = create_merchant_instance(st.session_state.merchant_phone)
                if new_id:
                    st.success(f"✅ تم إنشاء السيرفر {new_id}")
                    time.sleep(3)
                    st.rerun()
    else:
        st.markdown(f"<div class='status-card'>🟢 سيرفرك جاهز (ID: {m_id})</div>", unsafe_allow_html=True)
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("🔢 اطلب كود الربط (8 أرقام)"):
                with st.spinner("جاري جلب الكود..."):
                    found_code = None
                    for attempt in range(3): # محاولة جلب الكود 3 مرات
                        found_code = get_pairing_code(m_id, m_token, st.session_state.merchant_phone)
                        if found_code:
                            st.session_state.last_p_code = found_code
                            break
                        time.sleep(2)
                    
                    if not found_code:
                        st.error("السيرفر مشغول، حاول مرة أخرى بعد قليل.")

        with col_c2:
            if st.button("🔄 تحديث حالة الاتصال"):
                try:
                    res = requests.get(f"https://api.green-api.com/waInstance{m_id}/getStateInstance/{m_token}", timeout=10)
                    state = res.json().get('stateInstance')
                    if state == "authorized":
                        st.balloons()
                        st.success("🎉 متصل بنجاح!")
                    else:
                        st.info(f"الحالة: {state}")
                except:
                    st.error("خطأ في الاتصال.")

        if st.session_state.last_p_code:
            st.markdown("### 📝 الكود المطلوب:")
            st.markdown(f"<div class='code-box'>{st.session_state.last_p_code}</div>", unsafe_allow_html=True)
            st.info("أدخل هذا الكود في واتساب الهاتف (الأجهزة المرتبطة).")
            if st.button("🗑️ مسح الكود من الشاشة"):
                st.session_state.last_p_code = None
                st.rerun()

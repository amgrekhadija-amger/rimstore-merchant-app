import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
import requests

# 1. يجب أن يكون هذا أول أمر متعلق بـ streamlit
st.set_page_config(page_title="RimStore Merchant", layout="wide")

# 2. تحميل الإعدادات
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MY_GATEWAY_URL = os.getenv("MY_GATEWAY_URL", "http://46.224.250.252:3000")

# التأكد من المفاتيح
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ خطأ: ملف .env غير مكتمل أو غير موجود في المجلد الحالي")
    st.stop()

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"فشل الاتصال بـ Supabase: {e}")
    st.stop()

# --- التتمة كما في كودكِ الأصلي ---
st.title("RimStore - لوحة تحكم التاجر")
# ... ضعي هنا بقية كود اللغات والـ Tabs الخاص بكِ

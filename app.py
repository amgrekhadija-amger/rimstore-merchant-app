import requests
import streamlit as st
import time

# الإعدادات
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"

def force_cleanup():
    st.info("🔍 جاري محاولة تنظيف الحساب...")
    
    # 1. جلب القائمة
    list_url = f"{PARTNER_API_URL}/partner/getInstances/{PARTNER_TOKEN}"
    try:
        res = requests.get(list_url)
        if res.status_code == 200:
            instances = res.json()
            st.write(f"عدد السيرفرات المكتشفة: {len(instances)}")
            
            for inst in instances:
                inst_id = inst.get('idInstance')
                # 2. محاولة الحذف باستخدام الرابط المخصص للشركاء
                # نستخدم هنا التنسيق الذي يتوقعه السيرفر بدقة
                delete_url = f"{PARTNER_API_URL}/partner/deleteInstance/{PARTNER_TOKEN}/{inst_id}"
                
                response = requests.delete(delete_url)
                
                if response.status_code == 200:
                    st.write(f"✅ تم حذف {inst_id} بنجاح")
                else:
                    # إذا فشل الحذف، نحاول معرفة السبب (ربما السيرفر مدفوع أو مرتبط بجلسة نشطة)
                    st.write(f"⚠️ فشل حذف {inst_id}: استجابة السيرفر {response.status_code}")
                    # محاولة إضافية: إيقاف السيرفر قبل حذفه
                    requests.post(f"{PARTNER_API_URL}/waInstance{inst_id}/logout/{inst.get('apiTokenInstance', '')}")
            
            st.success("تمت محاولة تنظيف جميع السيرفرات.")
            st.rerun()
        else:
            st.error(f"فشل جلب القائمة: {res.status_code}")
    except Exception as e:
        st.error(f"خطأ تقني: {e}")

if st.button("🗑️ محاولة حذف السيرفرات الزائدة"):
    force_cleanup()

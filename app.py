import requests
import streamlit as st

# إعدادات الشريك الخاصة بكِ
PARTNER_TOKEN = "gac.797de6c64eb044699bb14882e34aaab52fda1d5b1de643"
PARTNER_API_URL = "https://api.green-api.com"

def cleanup_all_instances():
    st.write("🔄 جاري فحص الحساب لجلب السيرفرات...")
    
    # 1. جلب قائمة بجميع السيرفرات (Instances)
    list_url = f"{PARTNER_API_URL}/partner/getInstances/{PARTNER_TOKEN}"
    try:
        response = requests.get(list_url)
        if response.status_code == 200:
            instances = response.json() # قائمة السيرفرات
            total = len(instances)
            st.write(f"📢 وجدنا {total} سيرفر في حسابك.")
            
            # 2. حلقة لحذف كل سيرفر
            deleted_count = 0
            for inst in instances:
                inst_id = inst.get('idInstance')
                
                # تنفيذ أمر الحذف
                delete_url = f"{PARTNER_API_URL}/partner/deleteInstance/{PARTNER_TOKEN}/{inst_id}"
                del_res = requests.delete(delete_url)
                
                if del_res.status_code == 200:
                    deleted_count += 1
                    st.write(f"✅ تم حذف السيرفر: {inst_id}")
                else:
                    st.write(f"❌ فشل حذف السيرفر: {inst_id}")
            
            st.success(f"🎊 اكتملت العملية! تم حذف {deleted_count} سيرفر بنجاح.")
        else:
            st.error("فشل في جلب قائمة السيرفرات. تأكدي من PARTNER_TOKEN")
    except Exception as e:
        st.error(f"حدث خطأ تقني: {e}")

# زر التشغيل في Streamlit
if st.button("🗑️ ابدأ تنظيف الحساب الآن (حذف الكل)"):
    cleanup_all_instances()

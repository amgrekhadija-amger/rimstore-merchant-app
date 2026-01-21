import os
from flask import Flask, request, jsonify
from supabase import create_client
import requests
import google.generativeai as genai
from dotenv import load_dotenv
import base64

# --- 1. إعداد البيئة ---
load_dotenv()
app = Flask(__name__)

# إعدادات Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# إعدادات Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# إعدادات WPPConnect (التعديل الجديد)
WPP_URL = os.getenv("WPP_URL", "http://127.0.0.1:2136")
SECRET_KEY = os.getenv("SECRET_KEY", "THISISMYSECUREKEY")

# --- دالات الإرسال المعدلة لـ WPPConnect ---

def send_text(instance, to, body):
    url = f"{WPP_URL}/api/{instance}/send-message"
    headers = {"Authorization": f"Bearer {SECRET_KEY}", "Content-Type": "application/json"}
    payload = {"phone": to, "message": body}
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Error sending text: {e}")

def send_image_base64(instance, to, base64_string, caption):
    url = f"{WPP_URL}/api/{instance}/send-image"
    headers = {"Authorization": f"Bearer {SECRET_KEY}", "Content-Type": "application/json"}
    
    # تحويل الصورة إلى التنسيق الذي يقبله WPPConnect
    payload = {
        "phone": to,
        "base64": base64_string,
        "caption": caption
    }
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Error sending image: {e}")

# --- معالجة الرسائل القادمة ---

@app.route("/webhook", methods=['POST'])
def whatsapp_reply():
    data = request.json
    # WPPConnect يرسل الحدث باسم 'chat:received' أو 'message'
    if not data:
        return "OK", 200
    
    # استخراج البيانات حسب هيكلة WPPConnect
    instance_name = data.get('session') 
    customer_num = data.get('from') # رقم الزبون
    incoming_msg = data.get('content', '').strip().lower() # نص الرسالة

    if not customer_num or not incoming_msg:
        return "OK", 200

    # استخراج رقم التاجر من اسم الجلسة (مثال: store_222666)
    merchant_phone = instance_name.replace('store_', '').replace('v2_', '')

    merchant_res = supabase.table('merchants').select("*").eq("Phone", merchant_phone).execute()
    store_info = merchant_res.data[0] if merchant_res.data else {}
    store_name = store_info.get('Store_name', 'المتجر')

    # --- الردود بالحسانية (كما هي بدون تغيير) ---
    if any(word in incoming_msg for word in ['سلام', 'السلام']):
        send_text(instance_name, customer_num, "عليكم وسلام ومرحب بيك.")
        return "OK", 200
    
    if any(word in incoming_msg for word in ['شحالك', 'شحالكم', 'خبارك']):
        send_text(instance_name, customer_num, "مافين حد حاس بشي الحمدالله.")
        return "OK", 200

    if any(word in incoming_msg for word in ['بنكيلي', 'رقم الحساب', 'حسابكم']):
        send_text(instance_name, customer_num, "لاهي يتواصل معاك صاحب متجر ظرك او تبقي تعدل طلبية بين صيب صاحب متجر ويعدلهالك.")
        return "OK", 200

    # معالجة طلبات الصور والبحث
    try:
        res = supabase.table('products').select("*").eq('Phone', merchant_phone).execute()
        products_list = res.data if res.data else []

        if any(word in incoming_msg for word in ['صورة', 'مشيلي', 'ريني']):
            for p in products_list:
                if p['Product'].lower() in incoming_msg:
                    if p.get('Image_url'):
                        send_image_base64(instance_name, customer_num, p['Image_url'], f"تفضل، ذي صورة {p['Product']}")
                    else:
                        send_text(instance_name, customer_num, "المعذرة، ذي المنتج ماعندي صورتو ظرك.")
                    return "OK", 200

        # ردود Gemini الذكية بالحسانية (نفس منطقك السابق)
        prompt = f"""
        أنت مساعد مبيعات في متجر "{store_name}". أجب بالحسانية فقط.
        قائمة المنتجات المتاحة: {products_list}
        رسالة الزبون: {incoming_msg}
        """

        response = model.generate_content(prompt)
        send_text(instance_name, customer_num, response.text)
        
    except Exception as e:
        print(f"Error logic: {e}")
        send_text(instance_name, customer_num, "عدل خطأ، جرب شوي ثانية.")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

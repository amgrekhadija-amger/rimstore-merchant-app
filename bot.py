import os
from flask import Flask, request, jsonify
from supabase import create_client
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. تحميل الإعدادات من ملف .env ---
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

# إعدادات السيرفر الخاص (الاتصال داخلياً بالـ Node.js)
MY_GATEWAY_URL = os.getenv("MY_GATEWAY_URL", "http://localhost:3000")

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    data = request.json
    if not data or 'data' not in data:
        return "No Data", 200
    
    msg_data = data['data']
    incoming_msg = msg_data.get('body', '').strip().lower()
    customer_num = msg_data.get('from', '') 
    merchant_num = msg_data.get('merchant', '').split('@')[0]

    # --- الجزء 1: الردود الترحيبية الثابتة بالحسانية (لا تغيير هنا) ---
    greetings = ['سلام عليكم', 'السلام عليكم', 'سلام', 'مرحب']
    if any(word in incoming_msg for word in greetings):
        send_text_message(customer_num, "عليكم وسلام ومرحب بيك في RimStore.")
        return "OK", 200
    
    status_queries = ['شحالكم', 'شحالك', 'شخبارك', 'خبارك']
    if any(word in incoming_msg for word in status_queries):
        send_text_message(customer_num, "لباس ماشاء مافين حد حاس بشي الحمدالله.")
        return "OK", 200

    # --- الجزء 2: معالجة الطلبات والبحث عبر Gemini ---
    try:
        res = supabase.table('products').select("*").eq('Phone', merchant_num).execute()
        products_list = res.data if res.data else []

        prompt = f"""
        أنت مساعد مبيعات في متجر موريتاني لتاجر رقمه {merchant_num}. أجب باللهجة الحسانية فقط وبإيجاز شديد.
        قائمة المنتجات المتاحة حالياً: {products_list}
        
        القواعد:
        1. إذا سأل عن منتج موجود: "المنتج (اسم المنتج) خالك وسعرو (السعر)".
        2. إذا سأل عن منتج غير موجود: "المنتج (اسم المنتج) ماه خالك ظرك، نقدو نعدلو لك طلبية".
        3. إذا سأل "بكم" أو "شحال": أعطه السعر من القائمة المذكورة.
        4. لا تزد أي كلام فلسفي، جاوب فقط على سؤال الزبون بلهجة موريتانية بسيطة.
        
        رسالة الزبون: {incoming_msg}
        """

        response = model.generate_content(prompt)
        reply_text = response.text
        send_text_message(customer_num, reply_text)
        
        for p in products_list:
            if p['Product'].lower() in incoming_msg and p.get('Image_url'):
                send_image_message(customer_num, p['Product'], p['Image_url'])
                break
    except Exception as e:
        print(f"Error: {e}")
        send_text_message(customer_num, "المعذرة، عدل خطأ فالسيرفر، جرب شوي ثانية.")

    return "OK", 200

# --- دالات الإرسال ---
def send_text_message(to, body):
    url = f"{MY_GATEWAY_URL}/send-text"
    payload = {"to": to, "message": body}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        print("❌ فشل الاتصال ببوابة الواتساب (Node.js Server)")

def send_image_message(to, caption, image_url):
    url = f"{MY_GATEWAY_URL}/send-text"
    payload = {"to": to, "message": f"🖼️ {caption}\nرابط الصورة: {image_url}"}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

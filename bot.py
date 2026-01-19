import os
from flask import Flask, request, jsonify
from supabase import create_client
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. تحميل الإعدادات ---
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

# إعدادات Evolution API الجديد
EVO_URL = "http://localhost:8080"
EVO_API_KEY = "123456"  # تأكدي أنه نفس الكود في السيرفر

@app.route("/webhook", methods=['POST']) # قمنا بتغيير المسار ليكون متوافقاً مع Webhook
def whatsapp_reply():
    data = request.json
    
    # التأكد من أن الحدث هو رسالة جديدة (تنسيق Evolution API)
    if not data or data.get('event') != 'messages.upsert':
        return "Not a message event", 200
    
    message_data = data.get('data', {})
    instance_name = data.get('instance') # اسم الجلسة (مثلاً merchant_222422...)
    
    # استخراج نص الرسالة ورقم الزبون
    # Evolution API يرسل الرسالة في هيكل متداخل
    msg_obj = message_data.get('message', {})
    incoming_msg = ""
    
    if 'conversation' in msg_obj:
        incoming_msg = msg_obj['conversation']
    elif 'extendedTextMessage' in msg_obj:
        incoming_msg = msg_obj['extendedTextMessage'].get('text', '')
        
    incoming_msg = incoming_msg.strip().lower()
    customer_num = message_data.get('key', {}).get('remoteJid')
    
    # معرفة رقم التاجر من اسم الـ instance
    merchant_num = instance_name.replace('merchant_', '')

    if not incoming_msg:
        return "Empty message", 200

    # --- الجزء 1: الردود الترحيبية الثابتة بالحسانية ---
    greetings = ['سلام عليكم', 'السلام عليكم', 'سلام', 'مرحب']
    if any(word in incoming_msg for word in greetings):
        send_text_message(instance_name, customer_num, "عليكم وسلام ومرحب بيك في RimStore.")
        return "OK", 200
    
    status_queries = ['شحالكم', 'شحالك', 'شخبارك', 'خبارك']
    if any(word in incoming_msg for word in status_queries):
        send_text_message(instance_name, customer_num, "لباس ماشاء مافين حد حاس بشي الحمدالله.")
        return "OK", 200

    # --- الجزء 2: معالجة الطلبات والبحث عبر Gemini ---
    try:
        # جلب منتجات التاجر بناءً على رقمه
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
        send_text_message(instance_name, customer_num, reply_text)
        
    except Exception as e:
        print(f"Error: {e}")
        send_text_message(instance_name, customer_num, "المعذرة، عدل خطأ فالسيرفر، جرب شوي ثانية.")

    return "OK", 200

# --- دالات الإرسال المعدلة لتناسب Evolution API ---
def send_text_message(instance, to, body):
    url = f"{EVO_URL}/message/sendText/{instance}"
    headers = {
        "apikey": EVO_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": to,
        "text": body,
        "delay": 1200, # تأخير بسيط لتبدو كأنها كتابة بشرية
        "linkPreview": True
    }
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"❌ فشل الإرسال عبر Evolution API: {e}")

if __name__ == "__main__":
    # تشغيل البوت على منفذ 5000
    app.run(host="0.0.0.0", port=5000)

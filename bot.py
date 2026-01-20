import os
from flask import Flask, request, jsonify
from supabase import create_client
import requests
import google.generativeai as genai
from dotenv import load_dotenv

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

# إعدادات Evolution API
EVO_URL = os.getenv("EVO_URL", "http://127.0.0.1:8080")
EVO_API_KEY = os.getenv("EVO_API_KEY", "123456")

# --- دالات الإرسال (نص وصور بوضوح كامل) ---

def send_text(instance, to, body):
    url = f"{EVO_URL}/message/sendText/{instance}"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    payload = {"number": to, "text": body, "delay": 1000}
    requests.post(url, json=payload, headers=headers)

def send_image(instance, to, image_url, caption):
    url = f"{EVO_URL}/message/sendMedia/{instance}"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": to,
        "media": image_url, # رابط الصورة المباشر من Storage
        "mediatype": "image",
        "caption": caption
    }
    requests.post(url, json=payload, headers=headers)

# --- معالجة الرسائل القادمة ---

@app.route("/webhook", methods=['POST'])
def whatsapp_reply():
    data = request.json
    if not data or data.get('event') != 'messages.upsert':
        return "OK", 200
    
    message_data = data.get('data', {})
    instance_name = data.get('instance') 
    customer_num = message_data.get('key', {}).get('remoteJid')
    
    # استخراج النص من واتساب
    msg_obj = message_data.get('message', {})
    incoming_msg = ""
    if 'conversation' in msg_obj:
        incoming_msg = msg_obj['conversation']
    elif 'extendedTextMessage' in msg_obj:
        incoming_msg = msg_obj['extendedTextMessage'].get('text', '')
    
    incoming_msg = incoming_msg.strip().lower()
    merchant_phone = instance_name.replace('merchant_', '')

    # جلب معلومات المحل من قاعدة البيانات
    merchant_res = supabase.table('merchants').select("*").eq("Phone", merchant_phone).execute()
    store_info = merchant_res.data[0] if merchant_res.data else {}
    store_name = store_info.get('Store_name', 'المتجر')

    # 1. الردود الترحيبية الثابتة بالحسانية
    if any(word in incoming_msg for word in ['سلام', 'السلام']):
        send_text(instance_name, customer_num, "عليكم وسلام ومرحب بيك.")
        return "OK", 200
    
    if any(word in incoming_msg for word in ['شحالك', 'شحالكم', 'خبارك']):
        send_text(instance_name, customer_num, "مافين حد حاس بشي الحمدالله.")
        return "OK", 200

    # 2. الرد على السؤال عن الحساب البنكي
    if any(word in incoming_msg for word in ['بنكيلي', 'رقم الحساب', 'حسابكم']):
        send_text(instance_name, customer_num, "لاهي يتواصل معاك صاحب متجر ظرك او تبقي تعدل طلبية بين صيب صاحب متجر ويعدلهالك.")
        return "OK", 200

    # 3. معالجة طلبات الصور والبحث في المنتجات
    try:
        res = supabase.table('products').select("*").eq('Phone', merchant_phone).execute()
        products_list = res.data if res.data else []

        # إذا طلب صورة لمنتج معين
        if any(word in incoming_msg for word in ['صورة', 'مشيلي', 'ريني']):
            for p in products_list:
                if p['Product'].lower() in incoming_msg:
                    send_text(instance_name, customer_num, "أوكي ظرك")
                    if p.get('Image'):
                        send_image(instance_name, customer_num, p['Image'], f"تفضل، ذي صورة {p['Product']}")
                    else:
                        send_text(instance_name, customer_num, "المعذرة، ذي المنتج ماعندي صورتو ظرك.")
                    return "OK", 200

        # ردود Gemini الذكية بالحسانية
        prompt = f"""
        أنت مساعد مبيعات في متجر "{store_name}". أجب بالحسانية فقط.
        قائمة المنتجات: {products_list}
        
        القواعد:
        1. إذا سأل "ذى عندكم" أو "خالك": إذا موجود قل "أهيه خالك" واذكر (السعر، المقاس، اللون).
        2. إذا سأل "شحال" أو "بكم": أعطه السعر من القائمة.
        3. إذا قال "دور ذى": رد بـ "دور ظرك ودور من كم ولا تخلص ظرك ول".
        4. إذا سأل عن اسم المحل: قل "اسم محلنا {store_name}".
        5. لا تزد أي كلام من عندك، التزم بالمعلومات المتاحة.
        
        رسالة الزبون: {incoming_msg}
        """

        response = model.generate_content(prompt)
        send_text(instance_name, customer_num, response.text)
        
    except Exception as e:
        print(f"Error: {e}")
        send_text(instance_name, customer_num, "عدل خطأ، جرب شوي ثانية.")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

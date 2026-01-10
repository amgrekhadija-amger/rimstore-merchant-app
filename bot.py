from flask import Flask, request, jsonify
from supabase import create_client
import requests

app = Flask(__name__)

# --- 1. إعدادات السحاب (Supabase) ---
SUPABASE_URL = "https://pxgpkdrwsrwaldntpsca.supabase.co"
SUPABASE_KEY = "sb_publishable_-P0AEpUa4db_HGTCQE1mhw_AWus1FBB"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. إعدادات UltraMsg (تحديث بناءً على صوركِ) ---
# تم استخراج هذه البيانات من صور لوحة التحكم الخاصة بكِ
INSTANCE_ID = 'instance158049' 
API_TOKEN = 's7zx4mnvuim0l1h' 

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    data = request.json # استقبال البيانات بصيغة JSON من UltraMsg
    
    # التحقق من نوع البيانات الواردة (تجنب الأخطاء إذا كانت الرسالة فارغة)
    if not data or 'data' not in data:
        return "No Data", 200
    
    msg_data = data['data']
    incoming_msg = msg_data.get('body', '').strip().lower()
    customer_num = msg_data.get('from', '')  # رقم الزبون الذي أرسل الرسالة
    merchant_num = msg_data.get('to', '').split('@')[0] # رقم التاجر (بدون زوائد)
    
    # --- الجزء 1: الردود الترحيبية بالحسانية ---
    if any(word in incoming_msg for word in ['سلام عليكم', 'السلام عليكم', 'slm', 'مرحبا']):
        send_text_message(customer_num, "عليكم وسلام، مرحب بيك في متجرنا. اكتب اسم المنتج لتعرف سعره وصورته.")
        return "OK", 200
    
    if any(word in incoming_msg for word in ['شحالكم', 'شحالك', 'شماسين']):
        send_text_message(customer_num, "مافين حد حاس بشي، الحمد لله. شنهو اللي تدور اليوم؟")
        return "OK", 200

    # --- الجزء 2: نظام الطلبات (اطلب) ---
    if "اطلب" in incoming_msg:
        product_to_order = incoming_msg.replace("اطلب", "").strip()
        # البحث عن المنتج المرتبط برقم التاجر الحالي
        res = supabase.table('products').select("*").eq('Phone', merchant_num).eq('Product', product_to_order).execute()
        
        if res.data:
            p = res.data[0]
            supabase.table('orders').insert({
                "customer_phone": customer_num,
                "product_name": p['Product'],
                "total_price": p['Price'],
                "merchant_phone": merchant_num,
                "status": "طلب جديد"
            }).execute()
            send_text_message(customer_num, f"تم تسجيل طلبك لـ {p['Product']} بنجاح ✅. سيتواصل معك التاجر قريباً.")
        else:
            send_text_message(customer_num, "المعذرة، ذا المنتج ما جلبته أو تأكد من كتابه اسمه بشكل صحيح.")
        return "OK", 200

    # --- الجزء 3: البحث التلقائي عن المنتجات ---
    try:
        res = supabase.table('products').select("*").eq('Phone', merchant_num).execute()
        for p in res.data:
            if p['Product'].lower() in incoming_msg:
                if p.get('Status') == "غير متوفر":
                    send_text_message(customer_num, f"المعذرة، {p['Product']} حالياً نفدت الكمية.")
                    return "OK", 200

                price_msg = f"أهلاً بيك، {p['Product']} سعرها {p['Price']} أوقية."
                image_url = p.get('Image_url', '')
                
                if image_url:
                    send_image_message(customer_num, price_msg, image_url)
                else:
                    send_text_message(customer_num, price_msg)
                return "OK", 200

    except Exception as e:
        print(f"Error: {e}")

    return "OK", 200

# --- دالات المساعدة للإرسال عبر UltraMsg API ---
def send_text_message(to, body):
    url = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"
    payload = {"token": API_TOKEN, "to": to, "body": body}
    requests.post(url, data=payload)

def send_image_message(to, caption, image_url):
    url = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/image"
    payload = {"token": API_TOKEN, "to": to, "image": image_url, "caption": caption}
    requests.post(url, data=payload)

if __name__ == "__main__":
    app.run()
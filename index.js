// استدعاء مكتبة dotenv في أول سطر
require('dotenv').config(); 

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require("@whiskeysockets/baileys");
const pino = require("pino");
const { Boom } = require("@hapi/boom");
const express = require("express");
const axios = require("axios");
const { createClient } = require('@supabase/supabase-js');

// --- 1. إعدادات Supabase (قراءة من ملف .env) ---
const SUPABASE_URL = process.env.SUPABASE_URL; 
const SUPABASE_KEY = process.env.SUPABASE_KEY; 

// التحقق من وجود المفاتيح لضمان عدم توقف السيرفر
if (!SUPABASE_URL || !SUPABASE_KEY) {
    console.error("❌ خطأ: لم يتم العثور على SUPABASE_URL أو SUPABASE_KEY في ملف .env");
    process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

const app = express();
app.use(express.json());
const port = process.env.PORT || 3000; // استخدام المنفذ من .env أو 3000 كافتراضي

let sock;
// يمكنك أيضاً وضع رقم الهاتف في .env إذا أردتِ
const merchantPhone = process.env.MERCHANT_PHONE || "222XXXXXXXX"; 

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(`./sessions/${merchantPhone}`);

    sock = makeWASocket({
        auth: state,
        printQRInTerminal: true, 
        logger: pino({ level: "silent" }),
        browser: ["RimStore Bot", "Ubuntu", "1.0.0"] 
    });

    sock.ev.on("connection.update", async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log("📍 تم توليد QR جديد، جاري إرساله لـ Supabase...");
            await supabase
                .from('merchants')
                .update({ qr_code: qr, session_status: 'waiting_qr' })
                .eq('Phone', merchantPhone);
        }

        if (connection === "close") {
            const shouldReconnect = (lastDisconnect.error instanceof Boom)?.output?.statusCode !== DisconnectReason.loggedOut;
            if (shouldReconnect) connectToWhatsApp();
            
            await supabase.from('merchants').update({ session_status: 'disconnected' }).eq('Phone', merchantPhone);
        } 
        
        else if (connection === "open") {
            console.log("✅ تم الاتصال بنجاح وتحديث الحالة في Supabase");
            await supabase
                .from('merchants')
                .update({ session_status: 'connected', qr_code: null, last_seen: new Date().toISOString() })
                .eq('Phone', merchantPhone);
        }
    });

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("messages.upsert", async (m) => {
        const msg = m.messages[0];
        if (!msg.key.fromMe && m.type === "notify") {
            const sender = msg.key.remoteJid;
            const text = msg.message?.conversation || msg.message?.extendedTextMessage?.text;

            try {
                // إرسال البيانات لـ Flask المحلي
                await axios.post("http://localhost:5000/whatsapp", { 
                    data: { from: sender, body: text, merchant: merchantPhone }
                });
            } catch (err) {
                console.log("❌ خطأ في إرسال البيانات للـ Flask المحلي (تأكدي من تشغيل app.py)");
            }
        }
    });
}

// مسار لإرسال الرسائل (اختياري للتحكم من الخارج)
app.post("/send-text", async (req, res) => {
    const { to, message } = req.body;
    try {
        await sock.sendMessage(to, { text: message });
        res.json({ status: "success" });
    } catch (err) {
        res.status(500).json({ status: "error" });
    }
});

app.listen(port, "0.0.0.0", () => {
    console.log(`🚀 Gateway تعمل على المنفذ ${port}`);
    connectToWhatsApp();
});
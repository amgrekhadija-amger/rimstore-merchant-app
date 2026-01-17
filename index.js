require('dotenv').config(); 
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require("@whiskeysockets/baileys");
const pino = require("pino");
const { Boom } = require("@hapi/boom");
const express = require("express");
const { createClient } = require('@supabase/supabase-js');
const fs = require('fs'); // مكتبة النظام لمسح المجلدات التالفة

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);
const app = express();
app.use(express.json());

let sessions = {}; 

async function connectToWhatsApp(merchantPhone) {
    const sessionPath = `./sessions/${merchantPhone}`;
    
    // إعداد حالة المصادقة
    const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
    
    // جلب أحدث نسخة من مكتبة الواتساب لضمان الاستقرار
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        auth: state,
        version,
        printQRInTerminal: true, 
        logger: pino({ level: "silent" }),
        // محاكاة متصفح حقيقي لتجنب حظر فيسبوك
        browser: ["RimStore", "Chrome", "1.0.0"] 
    });

    sessions[merchantPhone] = sock;

    sock.ev.on("connection.update", async (update) => {
        const { connection, lastDisconnect, qr } = update;

        // تحديث رمز QR في قاعدة البيانات فور توليده
        if (qr) {
            console.log(`📍 تم توليد رمز QR جديد للتاجر: ${merchantPhone}`);
            await supabase.from('merchants').update({ 
                qr_code: qr, 
                session_status: 'waiting_qr' 
            }).eq('Phone', merchantPhone);
        }

        if (connection === "close") {
            const statusCode = (lastDisconnect.error instanceof Boom)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

            console.log(`📡 انقطع الاتصال للرقم ${merchantPhone}. السبب: ${statusCode}`);

            // إذا انتهت الجلسة أو كانت تالفة (السبب الرئيسي لخطأ QR غير صحيح)
            if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                console.log("⚠️ الجلسة منتهية، جاري مسح الملفات التالفة لبدء اتصال نظيف...");
                if (fs.existsSync(sessionPath)) {
                    fs.rmSync(sessionPath, { recursive: true, force: true });
                }
            }

            if (shouldReconnect) {
                connectToWhatsApp(merchantPhone);
            }
            
            await supabase.from('merchants').update({ session_status: 'disconnected' }).eq('Phone', merchantPhone);
        } 
        
        else if (connection === "open") {
            console.log(`✅ المتجر ${merchantPhone} متصل الآن بنجاح`);
            await supabase.from('merchants').update({ 
                session_status: 'connected', 
                qr_code: null 
            }).eq('Phone', merchantPhone);
        }
    });

    sock.ev.on("creds.update", saveCreds);
}

// نقطة الربط مع لوحة التحكم Streamlit
app.post("/init-session", async (req, res) => {
    const { phone } = req.body;
    if (!phone) return res.status(400).send("Phone number is required");
    
    console.log(`🚀 بدء جلسة جديدة للرقم: ${phone}`);
    connectToWhatsApp(phone);
    res.send("Initialization process started");
});

app.listen(3000, "0.0.0.0", () => {
    console.log(`🚀 Gateway تعمل بكفاءة على المنفذ 3000`);
});

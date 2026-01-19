require('dotenv').config(); 
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require("@whiskeysockets/baileys");
const pino = require("pino");
const { Boom } = require("@hapi/boom");
const express = require("express");
const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);
const app = express();
app.use(express.json());

let sessions = {}; 

async function connectToWhatsApp(merchantPhone) {
    // 1. استخدام مسار ديناميكي فريد لكل تاجر لضمان عدم تداخل الملفات
    const sessionPath = `./sessions/session-${merchantPhone}`;
    const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        auth: state,
        version,
        printQRInTerminal: false,
        logger: pino({ level: "silent" }),
        // 2. التعديل الاحترافي: جعل اسم المتصفح فريداً لكل رقم هاتف لمنع الرفض من واتساب
        browser: ["RimStore", `Merchant-${merchantPhone}`, "1.0.0"] 
    });

    sessions[merchantPhone] = sock;

    sock.ev.on("connection.update", async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log(`📡 تحديث الرمز للرقم: ${merchantPhone}`);
            // تحديث الرمز والتأكد من تصفير الحالات القديمة لضمان نظافة البيانات
            await supabase.from('merchants').update({ 
                qr_code: qr, 
                session_status: 'waiting_qr' 
            }).eq('Phone', merchantPhone);
        }

        if (connection === "close") {
            const statusCode = (lastDisconnect.error instanceof Boom)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

            console.log(`📡 انقطع الاتصال للرقم ${merchantPhone}. السبب: ${statusCode}`);

            // 3. تنظيف احترافي: مسح المجلد فقط في حالة الخروج النهائي
            if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                console.log("⚠️ تنظيف الجلسة التالفة نهائياً...");
                if (fs.existsSync(sessionPath)) {
                    fs.rmSync(sessionPath, { recursive: true, force: true });
                }
            }

            if (shouldReconnect) {
                connectToWhatsApp(merchantPhone);
            }
            
            await supabase.from('merchants').update({ 
                session_status: 'disconnected',
                qr_code: null 
            }).eq('Phone', merchantPhone);
        } 
        
        else if (connection === "open") {
            console.log(`✅ نجاح الربط: ${merchantPhone}`);
            // إرسال إشارة النجاح النهائية لـ Streamlit
            await supabase.from('merchants').update({ 
                session_status: 'connected', 
                qr_code: 'LINKED_SUCCESSFULLY' 
            }).eq('Phone', merchantPhone);
        }
    });

    sock.ev.on("creds.update", saveCreds);
}

app.post("/init-session", async (req, res) => {
    const { phone } = req.body;
    if (!phone) return res.status(400).send("Phone is required");
    
    // 4. خطوة احترافية: إغلاق أي جلسة قديمة لنفس الرقم في الذاكرة قبل بدء جلسة جديدة
    if (sessions[phone]) {
        try { sessions[phone].logout(); } catch (e) {}
        delete sessions[phone];
    }
    
    await supabase.from('merchants').update({ qr_code: null }).eq('Phone', phone);
    
    connectToWhatsApp(phone);
    res.send("Initialization triggered");
});

app.listen(3000, "0.0.0.0", () => {
    console.log(`🚀 Gateway Active on Port 3000`);
});

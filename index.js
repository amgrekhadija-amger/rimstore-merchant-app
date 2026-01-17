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
    const sessionPath = `./sessions/${merchantPhone}`;
    const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        auth: state,
        version,
        printQRInTerminal: false, // تم إيقافه للاعتماد على قاعدة البيانات فقط
        logger: pino({ level: "silent" }),
        browser: ["RimStore", "Chrome", "1.0.0"] 
    });

    sessions[merchantPhone] = sock;

    sock.ev.on("connection.update", async (update) => {
        const { connection, lastDisconnect, qr } = update;

        // 1. عند توليد رمز QR (مرحلة الانتظار)
        if (qr) {
            console.log(`📡 تحديث الرمز المؤقت للرقم: ${merchantPhone}`);
            await supabase.from('merchants').update({ 
                qr_code: qr, 
                session_status: 'waiting_qr' 
            }).eq('Phone', merchantPhone);
        }

        if (connection === "close") {
            const statusCode = (lastDisconnect.error instanceof Boom)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

            console.log(`📡 انقطع الاتصال للرقم ${merchantPhone}. السبب: ${statusCode}`);

            if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                console.log("⚠️ تنظيف الجلسة التالفة...");
                if (fs.existsSync(sessionPath)) {
                    fs.rmSync(sessionPath, { recursive: true, force: true });
                }
            }

            if (shouldReconnect) {
                connectToWhatsApp(merchantPhone);
            }
            
            // عند الانقطاع، نفرغ عمود الـ QR
            await supabase.from('merchants').update({ 
                session_status: 'disconnected',
                qr_code: null 
            }).eq('Phone', merchantPhone);
        } 
        
        // 2. عند نجاح الربط (هذا هو التعديل المطلوب)
        else if (connection === "open") {
            console.log(`✅ تم الربط بنجاح للتاجر: ${merchantPhone}`);
            
            // تخزين تأكيد النجاح فقط في عمود qr_code
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
    if (!phone) return res.status(400).send("Phone number is required");
    
    // مسح أي رمز قديم قبل البدء لضمان عدم التضارب
    await supabase.from('merchants').update({ qr_code: null }).eq('Phone', phone);
    
    connectToWhatsApp(phone);
    res.send("Session initialization started");
});

app.listen(3000, "0.0.0.0", () => {
    console.log(`🚀 Gateway Active on Port 3000`);
});

Require('dotenv').config(); 
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
let lastTempQR = {}; // مخزن مؤقت للرموز في الذاكرة فقط وليس في القاعدة

async function connectToWhatsApp(merchantPhone) {
    const sessionPath = `./sessions/session-${merchantPhone}`;
    const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        auth: state,
        version,
        printQRInTerminal: false,
        logger: pino({ level: "silent" }),
        browser: ["RimStore", `Merchant-${merchantPhone}`, "1.0.0"] 
    });

    sessions[merchantPhone] = sock;

    sock.ev.on("connection.update", async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log(`📡 رمز جديد تولد للرقم: ${merchantPhone} (محفوظ في الذاكرة فقط)`);
            // حفظ الرمز في الذاكرة المؤقتة للسيرفر فقط ليعرضه Streamlit
            lastTempQR[merchantPhone] = qr; 
            
            // تحديث الحالة فقط في القاعدة دون لمس عمود الـ qr_code
            await supabase.from('merchants').update({ 
                session_status: 'waiting_qr' 
            }).eq('Phone', merchantPhone);
        }

        if (connection === "close") {
            const statusCode = (lastDisconnect.error instanceof Boom)?.output?.statusCode;
            console.log(`📡 انقطع الاتصال للرقم ${merchantPhone}. السبب: ${statusCode}`);

            if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                if (fs.existsSync(sessionPath)) {
                    fs.rmSync(sessionPath, { recursive: true, force: true });
                }
            }

            // عند الانقطاع أو الفشل، نتأكد أن العمود فارغ
            await supabase.from('merchants').update({ 
                session_status: 'disconnected',
                qr_code: null 
            }).eq('Phone', merchantPhone);
        } 
        
        else if (connection === "open") {
            console.log(`✅ نجاح الربط للرقم: ${merchantPhone}`);
            
            // الآن فقط، وبعد النجاح، نحفظ الرمز في القاعدة كدليل
            const successfulQR = lastTempQR[merchantPhone] || "LINKED_SUCCESSFULLY";
            
            await supabase.from('merchants').update({ 
                session_status: 'connected', 
                qr_code: successfulQR // حفظ الرمز الذي أدى للنجاح فقط
            }).eq('Phone', merchantPhone);
            
            delete lastTempQR[merchantPhone]; // تنظيف الذاكرة المؤقتة
        }
    });

    sock.ev.on("creds.update", saveCreds);
}

// إضافة API جديد ليتمكن Streamlit من رؤية الرمز دون أن يكون في القاعدة
app.get("/get-qr/:phone", (res, req) => {
    const phone = req.params.phone;
    const qr = lastTempQR[phone];
    if (qr) {
        res.json({ qr: qr });
    } else {
        res.status(404).json({ message: "No active QR" });
    }
});

app.post("/init-session", async (req, res) => {
    const { phone } = req.body;
    if (!phone) return res.status(400).send("Phone is required");
    
    if (sessions[phone]) {
        try { sessions[phone].logout(); } catch (e) {}
        delete sessions[phone];
    }
    
    // تصفير العمود عند كل محاولة جديدة لضمان النظافة التي طلبتِها
    await supabase.from('merchants').update({ qr_code: null }).eq('Phone', phone);
    
    connectToWhatsApp(phone);
    res.send("Initialization triggered");
});

app.listen(3000, "0.0.0.0", () => {
    console.log(`🚀 Gateway Active on Port 3000`);
});

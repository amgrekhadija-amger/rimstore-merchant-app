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
let lastTempQR = {}; // مخزن الرموز الحية التي يطلبها Streamlit

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
            // تخزين الرمز في الذاكرة ليرسله السيرفر لـ Streamlit عند الطلب
            lastTempQR[merchantPhone] = qr;
            
            await supabase.from('merchants').update({ 
                session_status: 'waiting_qr' 
            }).eq('Phone', merchantPhone);
        }

        if (connection === "close") {
            const statusCode = (lastDisconnect.error instanceof Boom)?.output?.statusCode;
            if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                if (fs.existsSync(sessionPath)) {
                    fs.rmSync(sessionPath, { recursive: true, force: true });
                }
            }
            delete lastTempQR[merchantPhone];
            await supabase.from('merchants').update({ 
                session_status: 'disconnected',
                qr_code: null 
            }).eq('Phone', merchantPhone);
        } 
        
        else if (connection === "open") {
            // الآن فقط يتم حفظ الرمز الناجح في القاعدة
            const finalQR = lastTempQR[merchantPhone] || "SUCCESS";
            await supabase.from('merchants').update({ 
                session_status: 'connected', 
                qr_code: finalQR 
            }).eq('Phone', merchantPhone);
            delete lastTempQR[merchantPhone];
        }
    });

    sock.ev.on("creds.update", saveCreds);
}

// --- التعديل المطلوب لحل خطأ "السيرفر لا يستجيب" ---
app.get("/get-qr/:phone", (req, res) => {
    const phone = req.params.phone;
    const qr = lastTempQR[phone];
    if (qr) {
        res.json({ qr: qr });
    } else {
        res.status(404).json({ error: "No active QR found" });
    }
});
// ------------------------------------------------

app.post("/init-session", async (req, res) => {
    const { phone } = req.body;
    if (!phone) return res.status(400).send("Phone required");
    
    if (sessions[phone]) {
        try { sessions[phone].end(); } catch (e) {}
        delete sessions[phone];
    }
    
    await supabase.from('merchants').update({ qr_code: null }).eq('Phone', phone);
    connectToWhatsApp(phone);
    res.send("Session Init Started");
});

app.listen(3000, "0.0.0.0", () => {
    console.log(`🚀 Gateway Running on Port 3000`);
});

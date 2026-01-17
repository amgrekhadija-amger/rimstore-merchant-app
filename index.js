require('dotenv').config(); 
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require("@whiskeysockets/baileys");
const pino = require("pino");
const { Boom } = require("@hapi/boom");
const express = require("express");
const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);
const app = express();
app.use(express.json());

let sessions = {}; // لتخزين جلسات التجار المختلفين

async function connectToWhatsApp(merchantPhone) {
    const { state, saveCreds } = await useMultiFileAuthState(`./sessions/${merchantPhone}`);

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: true, 
        logger: pino({ level: "silent" }),
        browser: ["RimStore Bot", "Ubuntu", "1.0.0"] 
    });

    sessions[merchantPhone] = sock;

    sock.ev.on("connection.update", async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log(`📍 تم توليد QR لـ ${merchantPhone}`);
            await supabase.from('merchants').update({ qr_code: qr, session_status: 'waiting_qr' }).eq('Phone', merchantPhone);
        }

        if (connection === "close") {
            const shouldReconnect = (lastDisconnect.error instanceof Boom)?.output?.statusCode !== DisconnectReason.loggedOut;
            if (shouldReconnect) connectToWhatsApp(merchantPhone);
            await supabase.from('merchants').update({ session_status: 'disconnected' }).eq('Phone', merchantPhone);
        } else if (connection === "open") {
            console.log(`✅ ${merchantPhone} متصل الآن`);
            await supabase.from('merchants').update({ session_status: 'connected', qr_code: null }).eq('Phone', merchantPhone);
        }
    });

    sock.ev.on("creds.update", saveCreds);
}

// نقطة الربط مع لوحة التحكم (Streamlit)
app.post("/init-session", async (req, res) => {
    const { phone } = req.body;
    if (!phone) return res.status(400).send("Phone required");
    connectToWhatsApp(phone);
    res.send("Session initialization started");
});

app.listen(3000, "0.0.0.0", () => {
    console.log(`🚀 Gateway تعمل على المنفذ 3000`);
});

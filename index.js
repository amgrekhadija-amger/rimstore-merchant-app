require('dotenv').config();
const { default: makeWASocket, useMultiFileAuthState } = require("@whiskeysockets/baileys");
const { GoogleGenerativeAI } = require("@google/generative-ai");
const { createClient } = require('@supabase/supabase-js');
const qrcode = require('qrcode');
const express = require("express");
const pino = require("pino");

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-pro" });

const app = express();
app.use(express.json());

let sessions = {};
let lastTempQR = {};

async function startBot(merchantPhone) {
    const { state, saveCreds } = await useMultiFileAuthState(`./sessions/session-${merchantPhone}`);
    const sock = makeWASocket({
        auth: state,
        logger: pino({ level: "silent" }),
        browser: ["RimStore", "Chrome", "1.0.0"]
    });

    sessions[merchantPhone] = sock;

    sock.ev.on("connection.update", async (update) => {
        const { connection, qr } = update;
        if (qr) lastTempQR[merchantPhone] = qr;
        if (connection === "open") {
            await supabase.from('merchants').update({ session_status: 'connected' }).eq('Phone', merchantPhone);
            delete lastTempQR[merchantPhone];
        }
    });

    sock.ev.on("creds.update", saveCreds);

    // استقبال الرسائل والرد بالحسانية (نفس منطقك في Python)
    sock.ev.on("messages.upsert", async (m) => {
        const msg = m.messages[0];
        if (!msg.message || msg.key.fromMe) return;

        const customerNum = msg.key.remoteJid;
        const incomingMsg = (msg.message.conversation || msg.message.extendedTextMessage?.text || "").toLowerCase();

        try {
            const { data: merchant } = await supabase.from('merchants').select("*").eq("Phone", merchantPhone).single();
            const { data: products } = await supabase.from('products').select("*").eq("Phone", merchantPhone);

            // ردود مباشرة بالحسانية
            if (incomingMsg.includes("سلام")) return await sock.sendMessage(customerNum, { text: "عليكم وسلام ومرحب بيك." });
            if (incomingMsg.includes("شحالك")) return await sock.sendMessage(customerNum, { text: "مافين حد حاس بشي الحمدالله." });
            if (incomingMsg.includes("رقم الحساب")) return await sock.sendMessage(customerNum, { text: "لاهي يتواصل معاك صاحب متجر ظرك." });

            // رد Gemini الذكي بالحسانية
            const prompt = `أنت مساعد مبيعات في متجر "${merchant.Store_name}". أجب بالحسانية فقط. المنتجات: ${JSON.stringify(products)}. رسالة الزبون: ${incomingMsg}`;
            const result = await model.generateContent(prompt);
            await sock.sendMessage(customerNum, { text: result.response.text() });

        } catch (e) { console.log(e); }
    });
}

// الرابط الذي يحتاجه ملف app.py
app.get("/get-qr/:phone", async (req, res) => {
    const qr = lastTempQR[req.params.phone];
    if (qr) {
        const qrImage = await qrcode.toDataURL(qr);
        res.json({ qr: qrImage });
    } else { res.status(404).json({ error: "QR not ready" }); }
});

app.post("/init-session", (req, res) => {
    startBot(req.body.phone);
    res.send("Started");
});

app.listen(3000, "0.0.0.0", () => console.log("🚀 Server running on port 3000"));

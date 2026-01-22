require('dotenv').config();
const { default: makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion } = require("@whiskeysockets/baileys");
const { GoogleGenerativeAI } = require("@google/generative-ai");
const { createClient } = require('@supabase/supabase-js');
const express = require("express");
const pino = require("pino");
const qrcode = require('qrcode');

// 1. إعداد الاتصالات
const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-pro" });

const app = express();
app.use(express.json());

let sessions = {};
let lastTempQR = {};

// 2. دالة تشغيل البوت لكل تاجر
async function startBot(merchantPhone) {
    const { state, saveCreds } = await useMultiFileAuthState(`./sessions/session-${merchantPhone}`);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        auth: state,
        version,
        printQRInTerminal: true,
        logger: pino({ level: "silent" }),
        browser: ["RimStore", "Chrome", "1.0.0"]
    });

    sessions[merchantPhone] = sock;

    // تحديث الحالة والـ QR
    sock.ev.on("connection.update", async (update) => {
        const { connection, qr } = update;
        if (qr) lastTempQR[merchantPhone] = qr;
        
        if (connection === "open") {
            console.log(`✅ متجر ${merchantPhone} متصل الآن!`);
            await supabase.from('merchants').update({ session_status: 'connected' }).eq('Phone', merchantPhone);
            delete lastTempQR[merchantPhone];
        }
    });

    sock.ev.on("creds.update", saveCreds);

    // 3. معالجة الرسائل القادمة (نفس منطقك تماماً)
    sock.ev.on("messages.upsert", async (m) => {
        const msg = m.messages[0];
        if (!msg.message || msg.key.fromMe) return;

        const customerNum = msg.key.remoteJid;
        const incomingMsg = (msg.message.conversation || msg.message.extendedTextMessage?.text || "").toLowerCase().strip();

        try {
            // جلب بيانات التاجر والمنتجات من Supabase
            const { data: merchant } = await supabase.from('merchants').select("*").eq("Phone", merchantPhone).single();
            const { data: products } = await supabase.from('products').select("*").eq("Phone", merchantPhone);
            const storeName = merchant?.Store_name || "المتجر";

            // --- الردود بالحسانية الثابتة ---
            if (incomingMsg.includes('سلام')) {
                return await sock.sendMessage(customerNum, { text: "عليكم وسلام ومرحب بيك." });
            }
            if (incomingMsg.includes('شحالك') || incomingMsg.includes('خبارك')) {
                return await sock.sendMessage(customerNum, { text: "مافين حد حاس بشي الحمدالله." });
            }
            if (incomingMsg.includes('بنكيلي') || incomingMsg.includes('رقم الحساب')) {
                return await sock.sendMessage(customerNum, { text: "لاهي يتواصل معاك صاحب متجر ظرك او تبقي تعدل طلبية بين صيب صاحب متجر ويعدلهالك." });
            }

            // --- معالجة طلبات الصور والبحث عن منتج ---
            if (incomingMsg.includes('صورة') || incomingMsg.includes('مشيلي') || incomingMsg.includes('ريني')) {
                for (let p of products) {
                    if (incomingMsg.includes(p.Product.toLowerCase())) {
                        if (p.Image_url) {
                            const base64Data = p.Image_url.split(',')[1];
                            return await sock.sendMessage(customerNum, { 
                                image: Buffer.from(base64Data, 'base64'), 
                                caption: `تفضل، ذي صورة ${p.Product}` 
                            });
                        } else {
                            return await sock.sendMessage(customerNum, { text: "المعذرة، ذي المنتج ماعندي صورتو ظرك." });
                        }
                    }
                }
            }

            // --- رد Gemini الذكي بالحسانية ---
            const prompt = `
            أنت مساعد مبيعات في متجر "${storeName}". أجب بالحسانية فقط.
            قائمة المنتجات المتاحة: ${JSON.stringify(products)}
            رسالة الزبون: ${incomingMsg}
            `;

            const result = await model.generateContent(prompt);
            const responseText = result.response.text();
            await sock.sendMessage(customerNum, { text: responseText });

        } catch (e) {
            console.error("Error Logic:", e);
            await sock.sendMessage(customerNum, { text: "عدل خطأ، جرب شوي ثانية." });
        }
    });
}

// 4. واجهة API لربطها بـ Streamlit
app.get("/get-qr/:phone", async (req, res) => {
    const qr = lastTempQR[req.params.phone];
    if (qr) {
        const qrImage = await qrcode.toDataURL(qr);
        res.json({ qr: qrImage });
    } else {
        res.status(404).json({ error: "الرمز غير جاهز" });
    }
});

app.post("/init-session", (req, res) => {
    const { phone } = req.body;
    startBot(phone);
    res.send("تم بدء الجلسة");
});

app.listen(3000, "0.0.0.0", () => {
    console.log("🚀 بوت الواتساب يعمل على المنفذ 3000");
});

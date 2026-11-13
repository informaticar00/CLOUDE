// Jarvis za WhatsApp: prima poruke preko službenog WhatsApp Cloud API webhooka,
// pita Claude i šalje odgovor natrag u isti razgovor.
import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";
import Anthropic from "@anthropic-ai/sdk";

const env = (name, fallback) => {
  const v = process.env[name] ?? fallback;
  if (v === undefined || v === "") throw new Error(`Nedostaje varijabla okruženja ${name} (vidi .env.example)`);
  return v;
};

const PORT = Number(process.env.PORT || 3000);
const VERIFY_TOKEN = env("WHATSAPP_VERIFY_TOKEN");
const WA_TOKEN = env("WHATSAPP_TOKEN");
const PHONE_NUMBER_ID = env("WHATSAPP_PHONE_NUMBER_ID");
const APP_SECRET = process.env.WHATSAPP_APP_SECRET || "";
// Samo ovi brojevi smiju razgovarati s asistentom (međunarodni format bez +, odvojeni zarezom).
const ALLOWED = env("ALLOWED_NUMBERS").split(",").map((s) => s.replace(/\D/g, "")).filter(Boolean);
const ASSISTANT_NAME = process.env.ASSISTANT_NAME || "Jarvis";
const USER_NAME = process.env.USER_NAME || "";
const ABOUT_ME = process.env.ABOUT_ME || "";
const GRAPH_VERSION = process.env.GRAPH_API_VERSION || "v21.0";
const HISTORY_FILE = process.env.HISTORY_FILE || "./history.json";
const MAX_TURNS = 30;

const client = new Anthropic(); // čita ANTHROPIC_API_KEY

const SYSTEM = `Ti si ${ASSISTANT_NAME}, osobni AI asistent koji s korisnikom razgovara preko WhatsAppa.
Ton: smiren, uglađen i koristan, s malo diskretnog humora.${USER_NAME ? ` Korisnika oslovljavaj s "${USER_NAME}".` : ""}
Odgovaraj na jeziku kojim ti se korisnik obrati (najčešće hrvatski/bosanski).
Ovo je chat na mobitelu: piši kratko i jasno, koristi kratke odlomke i liste s crticama kad pomažu.
Za naglašavanje koristi WhatsApp oblikovanje (*podebljano*, _kurziv_), nikad markdown naslove (#) ni tablice.
Ne možeš upravljati telefonom, slati poruke drugim ljudima ni pretraživati internet; ako se to traži, reci kako to korisnik može brzo sam napraviti.${ABOUT_ME ? `\n\nŠto znaš o korisniku:\n${ABOUT_ME}` : ""}`;

// ---------- povijest razgovora (po broju telefona) ----------
let history = {};
try { history = JSON.parse(fs.readFileSync(HISTORY_FILE, "utf8")); } catch { history = {}; }
function saveHistory() {
  try { fs.writeFileSync(HISTORY_FILE, JSON.stringify(history)); } catch (e) { console.warn("Ne mogu spremiti povijest:", e.message); }
}
function turnsFor(number) {
  const t = history[number] || [];
  // razgovor mora početi korisnikovom porukom
  while (t.length && t[0].role !== "user") t.shift();
  return t;
}

// ---------- WhatsApp slanje ----------
async function sendWhatsApp(to, body) {
  // WhatsApp dopušta do 4096 znakova po poruci
  const parts = [];
  for (let rest = body; rest.length; ) {
    let cut = rest.length <= 4000 ? rest.length : rest.lastIndexOf("\n", 4000);
    if (cut < 1000) cut = Math.min(4000, rest.length);
    parts.push(rest.slice(0, cut));
    rest = rest.slice(cut).trimStart();
  }
  for (const text of parts) {
    const res = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${PHONE_NUMBER_ID}/messages`, {
      method: "POST",
      headers: { Authorization: `Bearer ${WA_TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify({ messaging_product: "whatsapp", to, type: "text", text: { body: text, preview_url: false } }),
    });
    if (!res.ok) console.error("WhatsApp greška pri slanju:", res.status, await res.text());
  }
}

async function markRead(messageId) {
  await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${PHONE_NUMBER_ID}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${WA_TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify({ messaging_product: "whatsapp", status: "read", message_id: messageId }),
  }).catch(() => {});
}

// ---------- Claude ----------
async function askClaude(number, text) {
  const turns = turnsFor(number);
  turns.push({ role: "user", content: text });
  const now = new Date().toLocaleString("hr-HR", { dateStyle: "full", timeStyle: "short", timeZone: process.env.TZ || "Europe/Sarajevo" });

  let reply;
  try {
    const response = await client.beta.messages.create({
      model: "claude-opus-5-5",
      max_tokens: 16000,
      output_config: { effort: "low" }, // brzi odgovori za chat
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default", // ako model odbije zahtjev, API ga sam ponovi na rezervnom modelu
      system: [{ type: "text", text: SYSTEM, cache_control: { type: "ephemeral" } }],
      messages: [...turns.slice(-MAX_TURNS), { role: "system", content: `Trenutni datum i vrijeme: ${now}.` }],
    });
    if (response.stop_reason === "refusal") {
      reply = "Na to ne mogu odgovoriti. Probaj pitati drugačije.";
    } else {
      reply = response.content.filter((b) => b.type === "text").map((b) => b.text).join("\n").trim()
        || "Hmm, nisam ništa smislio. Pokušaj ponovno.";
    }
  } catch (err) {
    turns.pop();
    if (err instanceof Anthropic.RateLimitError) return "Previše poruka u kratkom vremenu. Pričekaj minutu pa pokušaj ponovno.";
    if (err instanceof Anthropic.AuthenticationError) { console.error("Neispravan ANTHROPIC_API_KEY"); return "Asistent nije ispravno podešen (API ključ)."; }
    if (err instanceof Anthropic.APIError) { console.error("Claude API greška:", err.status, err.message); return "Claude trenutno nije dostupan. Pokušaj malo kasnije."; }
    console.error("Neočekivana greška:", err);
    return "Nešto je pošlo po zlu. Pokušaj ponovno.";
  }

  turns.push({ role: "assistant", content: reply });
  history[number] = turns.slice(-MAX_TURNS);
  saveHistory();
  return reply;
}

// ---------- obrada dolaznih poruka ----------
const seen = new Set(); // Meta ponekad pošalje istu poruku više puta
async function handleMessage(msg) {
  if (seen.has(msg.id)) return;
  seen.add(msg.id);
  if (seen.size > 1000) seen.delete(seen.values().next().value);

  const from = msg.from;
  if (!ALLOWED.includes(from)) { console.log(`Ignoriram poruku s nepoznatog broja ${from}`); return; }
  markRead(msg.id);

  if (msg.type !== "text") {
    await sendWhatsApp(from, "Za sada razumijem samo tekstualne poruke. Glasovne poruke i slike dolaze uskoro.");
    return;
  }
  const text = msg.text.body.trim();
  if (/^\/?(reset|novi razgovor|zaboravi)$/i.test(text)) {
    delete history[from]; saveHistory();
    await sendWhatsApp(from, "Gotovo, počinjemo ispočetka. Što trebaš?");
    return;
  }
  const reply = await askClaude(from, text);
  await sendWhatsApp(from, reply);
}

function validSignature(raw, header) {
  if (!APP_SECRET) return true; // preporučeno je postaviti WHATSAPP_APP_SECRET
  if (!header?.startsWith("sha256=")) return false;
  const expected = crypto.createHmac("sha256", APP_SECRET).update(raw).digest("hex");
  const a = Buffer.from(header.slice(7)), b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// ---------- HTTP server ----------
http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");

  if (req.method === "GET" && url.pathname === "/") {
    res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" }).end(`${ASSISTANT_NAME} radi.`);
    return;
  }

  // Meta provjera webhooka
  if (req.method === "GET" && url.pathname === "/webhook") {
    const ok = url.searchParams.get("hub.mode") === "subscribe" && url.searchParams.get("hub.verify_token") === VERIFY_TOKEN;
    res.writeHead(ok ? 200 : 403).end(ok ? url.searchParams.get("hub.challenge") : "Forbidden");
    return;
  }

  if (req.method === "POST" && url.pathname === "/webhook") {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const raw = Buffer.concat(chunks);
      if (!validSignature(raw, req.headers["x-hub-signature-256"])) { res.writeHead(401).end(); return; }
      res.writeHead(200).end(); // odmah potvrdi Meti, inače ponavlja slanje
      let body;
      try { body = JSON.parse(raw.toString("utf8")); } catch { return; }
      for (const entry of body.entry || []) {
        for (const change of entry.changes || []) {
          for (const msg of change.value?.messages || []) {
            handleMessage(msg).catch((e) => console.error("Greška u obradi poruke:", e));
          }
        }
      }
    });
    return;
  }

  res.writeHead(404).end();
}).listen(PORT, () => console.log(`${ASSISTANT_NAME} sluša na portu ${PORT}`));

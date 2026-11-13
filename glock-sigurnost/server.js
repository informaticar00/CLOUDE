// Glock Sigurnost: web server (Node 22+).
// Servira /public, prima upite na POST /api/upit, sprema ih u data/upiti.jsonl,
// a klijentu i firmi šalje potvrdu i obavijest putem WhatsAppa (Cloud API) i emaila (SMTP).
import { createServer } from 'node:http';
import { readFile, appendFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import nodemailer from 'nodemailer';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const PUBLIC = join(ROOT, 'public');
const DATA = join(ROOT, 'data');
const env = process.env;
const PORT = Number(env.PORT || 3000);
const RATE_LIMIT = Number(env.RATE_LIMIT || 5); // upita po IP adresi u 10 minuta

const WA = {
  token: env.WHATSAPP_TOKEN,
  phoneId: env.WHATSAPP_PHONE_NUMBER_ID,
  version: env.WHATSAPP_API_VERSION || 'v21.0',
  lang: env.WHATSAPP_TEMPLATE_LANG || 'bs',
  clientTemplate: env.WHATSAPP_TEMPLATE_CLIENT || 'upit_zaprimljen',
  companyTemplate: env.WHATSAPP_TEMPLATE_COMPANY || '',
  // Službeni WhatsApp broj firme; javan je, pa ima podrazumijevanu vrijednost.
  companyNumber: toE164(env.COMPANY_WHATSAPP || '067 104 2939'),
};
const waEnabled = Boolean(WA.token && WA.phoneId);

// Email preko SMTP-a (npr. Gmail: smtp.gmail.com, port 465, lozinka za aplikacije).
const MAIL = {
  host: env.SMTP_HOST || 'smtp.gmail.com',
  port: Number(env.SMTP_PORT || 465),
  user: env.SMTP_USER,
  pass: env.SMTP_PASS,
  from: env.MAIL_FROM || (env.SMTP_USER ? `"Glock Sigurnost" <${env.SMTP_USER}>` : ''),
  company: env.COMPANY_EMAIL || env.SMTP_USER || '',
};
let mailTransport = MAIL.user && MAIL.pass
  ? nodemailer.createTransport({ host: MAIL.host, port: MAIL.port, secure: MAIL.port === 465, auth: { user: MAIL.user, pass: MAIL.pass } })
  : null;
// Za testove: zamjena SMTP transporta.
export function setMailTransport(t, { from = '"Glock Sigurnost" <test@example.com>', company = 'firma@example.com' } = {}) {
  mailTransport = t;
  MAIL.from = from;
  MAIL.company = company;
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.ico': 'image/x-icon' };
const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Frame-Options': 'DENY',
};

// Lokalni BiH broj (06x..., 03x...) u međunarodni format bez "+", npr. 38761123456.
export function toE164(raw, country = '387') {
  let d = String(raw).replace(/\D/g, '');
  if (d.startsWith('00')) d = d.slice(2);
  else if (d.startsWith('0')) d = country + d.slice(1);
  return d.length >= 8 && d.length <= 15 ? d : '';
}

// WhatsApp parametri šablona ne smiju imati nove redove, tabove ni više od 4 razmaka zaredom.
const tplText = (s, max = 900) => String(s).replace(/[\r\n\t]+/g, ' ').replace(/ {2,}/g, ' ').trim().slice(0, max) || '-';

async function sendTemplate(to, name, params) {
  const res = await fetch(`https://graph.facebook.com/${WA.version}/${WA.phoneId}/messages`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${WA.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messaging_product: 'whatsapp',
      to,
      type: 'template',
      template: {
        name,
        language: { code: WA.lang },
        components: params.length ? [{ type: 'body', parameters: params.map(text => ({ type: 'text', text: tplText(text) })) }] : [],
      },
    }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`WhatsApp ${res.status}: ${await res.text()}`);
}

const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const mailShell = inner => `<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#1f2937;line-height:1.6">
<div style="background:#0a0f1c;color:#e3b04b;padding:18px 24px;font-weight:700;letter-spacing:.08em">GLOCK SIGURNOST</div>
<div style="padding:24px;border:1px solid #e5e7eb;border-top:0">${inner}</div></div>`;

// Potvrda klijentu da je upit zaprimljen.
function clientMail(u) {
  const text = `Poštovani/a ${u.ime},

Vaš upit je uspješno zaprimljen u agenciji Glock Sigurnost. Kada upit bude obrađen, naš tim će Vas kontaktirati.

Usluga: ${u.usluga}
Vaš upit: ${u.poruka}

Hvala na povjerenju!
Agencija „GLOCK-SIGURNOST“ d.o.o. Sarajevo
Muhameda ef. Pandže 199, 71000 Sarajevo · 033 222 214`;
  const html = mailShell(`<p>Poštovani/a <b>${esc(u.ime)}</b>,</p>
<p>Vaš upit je uspješno zaprimljen u agenciji Glock Sigurnost. Kada upit bude obrađen, naš tim će Vas kontaktirati.</p>
<p style="background:#f9fafb;padding:12px 16px;border-left:3px solid #e3b04b"><b>Usluga:</b> ${esc(u.usluga)}<br><b>Vaš upit:</b><br>${esc(u.poruka).replace(/\n/g, '<br>')}</p>
<p>Hvala na povjerenju!</p>
<p style="font-size:13px;color:#6b7280">Agencija „GLOCK-SIGURNOST“ d.o.o. Sarajevo<br>Muhameda ef. Pandže 199, 71000 Sarajevo · 033 222 214</p>`);
  return { from: MAIL.from, to: u.email, subject: 'Vaš upit je zaprimljen | Glock Sigurnost', text, html };
}

// Obavijest firmi o novom upitu; "Odgovori" ide direktno klijentu.
function companyMail(u) {
  const rows = [['Ime / firma', u.ime], ['Telefon', u.telefon], ['Email', u.email], ['Usluga', u.usluga], ['Upit', u.poruka]];
  const text = rows.map(([k, v]) => `${k}: ${v}`).join('\n');
  const html = mailShell(`<p><b>Novi upit sa web stranice</b></p><table style="border-collapse:collapse;width:100%">${rows
    .map(([k, v]) => `<tr><td style="padding:6px 10px 6px 0;color:#6b7280;vertical-align:top;white-space:nowrap">${k}</td><td style="padding:6px 0">${esc(v).replace(/\n/g, '<br>')}</td></tr>`)
    .join('')}</table>`);
  return { from: MAIL.from, to: MAIL.company, replyTo: u.email, subject: `Novi upit: ${u.ime} (${u.usluga})`, text, html };
}

// Jednostavno ograničenje broja upita po IP adresi u 10 minuta.
const hits = new Map();
function rateLimited(ip) {
  const now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < 10 * 60_000);
  recent.push(now);
  hits.set(ip, recent);
  return recent.length > RATE_LIMIT;
}

function validate(b) {
  const s = k => (typeof b[k] === 'string' ? b[k].trim() : '');
  const upit = { ime: s('ime'), telefon: s('telefon'), email: s('email'), usluga: s('usluga') || 'Nije navedeno', poruka: s('poruka') };
  if (upit.ime.length < 2 || upit.ime.length > 100) return { error: 'Unesite ime i prezime ili naziv firme.' };
  if (!toE164(upit.telefon)) return { error: 'Broj telefona nije ispravan.' };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(upit.email) || upit.email.length > 120) return { error: 'Email adresa nije ispravna.' };
  if (upit.poruka.length < 10 || upit.poruka.length > 1500) return { error: 'Upit mora imati između 10 i 1500 znakova.' };
  if (upit.usluga.length > 60) upit.usluga = upit.usluga.slice(0, 60);
  if (b.saglasnost !== 'on' && b.saglasnost !== true) return { error: 'Potrebna je saglasnost za kontakt.' };
  return { upit };
}

async function readJson(req, limit = 20_000) {
  let size = 0;
  const chunks = [];
  for await (const c of req) {
    size += c.length;
    if (size > limit) throw Object.assign(new Error('Prevelik zahtjev.'), { status: 413 });
    chunks.push(c);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}');
}

function send(res, status, body, headers = {}) {
  const isJson = typeof body !== 'string' && !Buffer.isBuffer(body);
  res.writeHead(status, { ...SECURITY_HEADERS, ...(isJson ? { 'Content-Type': 'application/json; charset=utf-8' } : {}), ...headers });
  res.end(isJson ? JSON.stringify(body) : body);
}

async function handleUpit(req, res) {
  const ip = (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim();
  if (rateLimited(ip)) return send(res, 429, { error: 'Previše upita. Pokušajte ponovo za nekoliko minuta.' });

  let body;
  try { body = await readJson(req); } catch (e) { return send(res, e.status || 400, { error: 'Neispravan zahtjev.' }); }
  if (body.website) return send(res, 200, { ok: true, whatsappSent: false, emailSent: false }); // honeypot: bot, tiho ignorišemo

  const { upit, error } = validate(body);
  if (error) return send(res, 400, { error });

  const zapis = { ...upit, telefonE164: toE164(upit.telefon), vrijeme: new Date().toISOString(), ip };
  await mkdir(DATA, { recursive: true });
  await appendFile(join(DATA, 'upiti.jsonl'), JSON.stringify(zapis) + '\n');

  // Obavijesti firmi idu u pozadini; potvrde klijentu čekamo da bismo mu rekli šta je stiglo.
  const log = what => e => { console.error(`[upit] ${what} nije poslana:`, e.message); return false; };
  if (waEnabled && WA.companyTemplate && WA.companyNumber) {
    sendTemplate(WA.companyNumber, WA.companyTemplate, [upit.ime, upit.telefon, upit.email, upit.usluga, upit.poruka]).catch(log('WhatsApp obavijest firmi'));
  }
  if (mailTransport && MAIL.company) mailTransport.sendMail(companyMail(upit)).catch(log('email obavijest firmi'));

  const [whatsappSent, emailSent] = await Promise.all([
    waEnabled ? sendTemplate(zapis.telefonE164, WA.clientTemplate, [upit.ime]).then(() => true, log('WhatsApp potvrda klijentu')) : false,
    mailTransport ? mailTransport.sendMail(clientMail(upit)).then(() => true, log('email potvrda klijentu')) : false,
  ]);
  if (!waEnabled && !mailTransport) console.log('[upit] WhatsApp i email nisu podešeni, upit je samo sačuvan:', zapis.ime, zapis.telefonE164);
  send(res, 200, { ok: true, whatsappSent, emailSent });
}

async function serveStatic(req, res) {
  const url = new URL(req.url, 'http://x');
  let path = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, '');
  if (path.endsWith('/')) path += 'index.html';
  const file = join(PUBLIC, path);
  if (!file.startsWith(PUBLIC)) return send(res, 403, 'Zabranjeno', { 'Content-Type': 'text/plain; charset=utf-8' });
  try {
    const data = await readFile(file);
    send(res, 200, data, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream', 'Cache-Control': extname(file) === '.html' ? 'no-cache' : 'public, max-age=3600' });
  } catch {
    send(res, 404, 'Stranica nije pronađena', { 'Content-Type': 'text/plain; charset=utf-8' });
  }
}

const server = createServer(async (req, res) => {
  try {
    if (req.method === 'POST' && req.url === '/api/upit') return await handleUpit(req, res);
    if (req.method === 'GET' && req.url === '/api/config') return send(res, 200, { whatsapp: WA.companyNumber || null });
    if (req.method === 'GET' || req.method === 'HEAD') return await serveStatic(req, res);
    send(res, 405, { error: 'Metoda nije dozvoljena.' });
  } catch (e) {
    console.error(e);
    if (!res.headersSent) send(res, 500, { error: 'Greška na serveru.' });
  }
});

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  server.listen(PORT, () => console.log(`Glock Sigurnost radi na http://localhost:${PORT} (WhatsApp: ${waEnabled ? 'uključen' : 'nije podešen'})`));
}
export { server };

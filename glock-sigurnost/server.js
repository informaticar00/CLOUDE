// Glock Sigurnost: web server bez zavisnosti (Node 22+).
// Servira /public, prima upite na POST /api/upit, sprema ih u data/upiti.jsonl
// i preko WhatsApp Cloud API-ja šalje potvrdu klijentu i obavijest firmi.
import { createServer } from 'node:http';
import { readFile, appendFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

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
  companyNumber: toE164(env.COMPANY_WHATSAPP || ''),
};
const waEnabled = Boolean(WA.token && WA.phoneId);

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
  if (body.website) return send(res, 200, { ok: true, whatsappSent: false }); // honeypot: bot, tiho ignorišemo

  const { upit, error } = validate(body);
  if (error) return send(res, 400, { error });

  const zapis = { ...upit, telefonE164: toE164(upit.telefon), vrijeme: new Date().toISOString(), ip };
  await mkdir(DATA, { recursive: true });
  await appendFile(join(DATA, 'upiti.jsonl'), JSON.stringify(zapis) + '\n');

  let whatsappSent = false;
  if (waEnabled) {
    try {
      await sendTemplate(zapis.telefonE164, WA.clientTemplate, [upit.ime]);
      whatsappSent = true;
    } catch (e) { console.error('[upit] potvrda klijentu nije poslana:', e.message); }
    if (WA.companyTemplate && WA.companyNumber) {
      sendTemplate(WA.companyNumber, WA.companyTemplate, [upit.ime, upit.telefon, upit.email, upit.usluga, upit.poruka])
        .catch(e => console.error('[upit] obavijest firmi nije poslana:', e.message));
    }
  } else {
    console.log('[upit] WhatsApp nije podešen, upit je samo sačuvan:', zapis.ime, zapis.telefonE164);
  }
  send(res, 200, { ok: true, whatsappSent });
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

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';

process.env.WHATSAPP_TOKEN = 'test-token';
process.env.WHATSAPP_PHONE_NUMBER_ID = '123';
process.env.COMPANY_WHATSAPP = '061 000 111';
process.env.WHATSAPP_TEMPLATE_COMPANY = 'novi_upit';
process.env.RATE_LIMIT = '100';

// Hvata pozive prema WhatsApp API-ju, a ostale pozive (prema test serveru) propušta.
const realFetch = globalThis.fetch;
const waCalls = [];
globalThis.fetch = async (url, init) => {
  if (String(url).startsWith('https://graph.facebook.com/')) {
    waCalls.push({ url: String(url), body: JSON.parse(init.body), auth: init.headers.Authorization });
    return new Response('{"messages":[{"id":"x"}]}', { status: 200 });
  }
  return realFetch(url, init);
};

const { server, toE164 } = await import('./server.js');
let base;
before(async () => {
  await new Promise(r => server.listen(0, r));
  base = `http://localhost:${server.address().port}`;
});
after(() => server.close());

const post = body => fetch(`${base}/api/upit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const valid = { ime: 'Amar Hodžić', telefon: '061 123 456', email: 'amar@primjer.ba', usluga: 'GPS praćenje vozila', poruka: 'Treba mi GPS za 3 vozila.\nHitno.', saglasnost: 'on' };

test('toE164 pretvara BiH brojeve', () => {
  assert.equal(toE164('061 123 456'), '38761123456');
  assert.equal(toE164('+387 61 123-456'), '38761123456');
  assert.equal(toE164('0038733222214'), '38733222214');
  assert.equal(toE164('12'), '');
});

test('ispravan upit šalje potvrdu klijentu i obavijest firmi', async () => {
  waCalls.length = 0;
  const res = await post(valid);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true, whatsappSent: true });
  await new Promise(r => setTimeout(r, 20)); // obavijest firmi se šalje u pozadini

  const [client, company] = waCalls;
  assert.equal(client.url, 'https://graph.facebook.com/v21.0/123/messages');
  assert.equal(client.auth, 'Bearer test-token');
  assert.equal(client.body.to, '38761123456');
  assert.equal(client.body.template.name, 'upit_zaprimljen');
  assert.equal(client.body.template.components[0].parameters[0].text, 'Amar Hodžić');

  assert.equal(company.body.to, '38761000111');
  assert.equal(company.body.template.name, 'novi_upit');
  const texts = company.body.template.components[0].parameters.map(p => p.text);
  assert.equal(texts.length, 5);
  assert.ok(texts.every(t => !/[\n\t]/.test(t)), 'parametri šablona ne smiju imati nove redove');
});

test('neispravni podaci se odbijaju bez slanja poruke', async () => {
  waCalls.length = 0;
  for (const bad of [{ ...valid, email: 'nije-email' }, { ...valid, telefon: '12' }, { ...valid, poruka: 'kratko' }, { ...valid, saglasnost: undefined }]) {
    const res = await post(bad);
    assert.equal(res.status, 400);
  }
  assert.equal(waCalls.length, 0);
});

test('honeypot tiho ignoriše botove', async () => {
  waCalls.length = 0;
  const res = await post({ ...valid, website: 'spam.example' });
  assert.equal(res.status, 200);
  assert.equal(waCalls.length, 0);
});

test('stranica i config se serviraju, traversal je blokiran', async () => {
  const html = await fetch(base + '/');
  assert.equal(html.status, 200);
  assert.match(await html.text(), /GLOCK/);
  assert.deepEqual(await (await fetch(base + '/api/config')).json(), { whatsapp: '38761000111' });
  const trav = await fetch(base + '/..%2Fserver.js');
  assert.notEqual(trav.status, 200);
});

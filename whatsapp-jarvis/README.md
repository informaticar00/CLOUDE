# Jarvis za WhatsApp

Osobni AI asistent (Claude) s kojim se dopisuješ u WhatsAppu kao s običnim kontaktom.
Koristi **službeni WhatsApp Cloud API** tvrtke Meta, pa ti broj neće biti blokiran.

## Kako radi

```
Ti (WhatsApp)  ->  Meta WhatsApp Cloud API  ->  ovaj server (webhook)  ->  Claude API
               <-                            <-   odgovor               <-
```

- Odgovara samo brojevima iz `ALLOWED_NUMBERS`. Poruke od svih ostalih ignorira, pa ti nitko drugi ne troši kredit.
- Pamti zadnjih 30 poruka razgovora. Pošalji `reset` za novi razgovor.
- Za sada razumije samo tekst, ne glasovne poruke ni slike.

## Što ti treba

1. **Anthropic API ključ** s [console.anthropic.com](https://console.anthropic.com). Plaća se prema potrošnji; običan chat stoji nekoliko centi dnevno.
2. **Meta developer račun** na [developers.facebook.com](https://developers.facebook.com). Besplatan je.
3. **Broj za asistenta.** Asistent ne može koristiti broj koji je već aktivan u tvojoj WhatsApp aplikaciji. Za početak Meta daje besplatni **testni broj**, a kasnije možeš dodati vlastiti drugi broj (npr. jeftinu drugu SIM karticu).
4. **Hosting** s javnim HTTPS linkom, npr. [Render](https://render.com) ili [Railway](https://railway.app).

## Postavljanje korak po korak

### 1. Meta aplikacija
1. Na developers.facebook.com: **My Apps → Create App → Other → Business**.
2. Dodaj proizvod **WhatsApp** i otvori **WhatsApp → API Setup**.
3. Zapiši **Phone number ID** i privremeni **Access token** (vrijedi 24 h; trajni token je opisan dolje).
4. U polju **To** dodaj svoj osobni broj i potvrdi ga kodom koji stigne na WhatsApp.
5. **App settings → Basic** → zapiši **App Secret**.

### 2. Objavi server (primjer: Render)
1. Ovu mapu stavi na GitHub (već je u ovom repozitoriju).
2. Render → **New → Web Service** → odaberi repozitorij.
   - Root directory: `whatsapp-jarvis`
   - Build command: `npm install`
   - Start command: `npm start`
3. Pod **Environment** upiši sve varijable iz `.env.example`.
4. Kad se objavi, dobiješ link oblika `https://jarvis-xxxx.onrender.com`.

### 3. Spoji webhook
1. U Meti: **WhatsApp → Configuration → Webhook → Edit**.
   - Callback URL: `https://jarvis-xxxx.onrender.com/webhook`
   - Verify token: isti tekst kao `WHATSAPP_VERIFY_TOKEN`
2. **Verify and save**, zatim pod **Webhook fields** uključi **messages**.

### 4. Isprobaj
Pošalji poruku testnom broju iz Meta API Setupa (spremi ga u kontakte kao "Jarvis").

## Trajni token
Privremeni token istekne za 24 sata. Za trajni:
**Business Settings → Users → System users → Add** (uloga Admin) → **Generate token** za svoju aplikaciju, s dozvolama `whatsapp_business_messaging` i `whatsapp_business_management`. Taj token upiši u `WHATSAPP_TOKEN`.

## Lokalno pokretanje
```bash
cd whatsapp-jarvis
npm install
cp .env.example .env    # popuni vrijednosti
node --env-file=.env server.mjs
```
Za test s mobitela treba ti javni link, npr. `npx localtunnel --port 3000`.

## Napomene
- Besplatni Render servis zaspi nakon 15 minuta neaktivnosti, pa prva poruka nakon pauze može kasniti oko 30 sekundi.
- Povijest razgovora sprema se u `history.json`. Na besplatnom hostingu briše se pri svakom ponovnom pokretanju.
- Model: `claude-opus-5-5` s niskim effortom za brze odgovore. Ako model odbije zahtjev, API ga sam ponovi na rezervnom modelu (server-side fallback).

# Glock Sigurnost: web stranica

Moderna jednostranična web stranica za Agenciju „GLOCK-SIGURNOST“ d.o.o. Sarajevo, s formom za upite i automatskom potvrdom na WhatsApp.

- `public/`: stranica (HTML, CSS, JS, bez frameworka)
- `server.js`: mali Node server bez vanjskih paketa. Servira stranicu, prima upite, sprema ih u `data/upiti.jsonl` i šalje WhatsApp poruke.

## Pokretanje

Potreban je Node.js 22 ili noviji.

```bash
cd glock-sigurnost
cp .env.example .env     # popunite podatke (vidi dolje)
npm start                # http://localhost:3000
npm test                 # testovi
```

Stranica radi i bez WhatsApp podataka. Upiti se tada samo spremaju u `data/upiti.jsonl`.

## Kako radi forma

1. Klijent upiše ime, broj telefona, email, uslugu i upit, te potvrdi saglasnost za kontakt.
2. Server provjeri podatke, zaštićen je od spam botova (honeypot polje i ograničenje broja upita po IP adresi) i spremi upit.
3. Klijent na WhatsApp dobije poruku da je upit zaprimljen i da će biti kontaktiran kad se upit obradi.
4. Ako je podešeno, i službeni broj firme dobije WhatsApp obavijest s podacima novog upita.

Brojevi se automatski pretvaraju u međunarodni format: `061 123 456` postaje `38761123456`.

## Podešavanje WhatsAppa (WhatsApp Business Cloud API)

Za automatske poruke potreban je **WhatsApp Business Cloud API** kompanije Meta. Običan WhatsApp ili WhatsApp Business aplikacija na telefonu ne može slati poruke automatski sa web stranice.

1. Na <https://business.facebook.com> napravite (ili otvorite) Meta Business nalog firme i verifikujte firmu.
2. Na <https://developers.facebook.com> napravite aplikaciju tipa **Business** i dodajte proizvod **WhatsApp**.
3. U **WhatsApp → API Setup** dodajte službeni broj firme. Taj broj ne smije istovremeno biti aktivan u običnoj WhatsApp aplikaciji. Kopirajte **Phone number ID**.
4. Napravite **trajni token**: Business Settings → System users → Add, dodijelite mu aplikaciju i WhatsApp nalog, pa Generate token s dozvolama `whatsapp_business_messaging` i `whatsapp_business_management`.
5. U **WhatsApp Manager → Message templates** napravite šablone ispod i sačekajte da ih Meta odobri. To obično traje od nekoliko minuta do nekoliko sati.
6. Upišite podatke u `.env`:

```env
WHATSAPP_TOKEN=trajni_token
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_TEMPLATE_LANG=bs
WHATSAPP_TEMPLATE_CLIENT=upit_zaprimljen
COMPANY_WHATSAPP=+387 6X XXX XXX
WHATSAPP_TEMPLATE_COMPANY=novi_upit
```

`COMPANY_WHATSAPP` uključuje i zeleno WhatsApp dugme na stranici.

### Šablon za klijenta: `upit_zaprimljen`

- Kategorija: **Utility**, jezik: **Bosnian** (`bs`)
- Tekst:

> Poštovani/a {{1}}, Vaš upit je uspješno zaprimljen u agenciji Glock Sigurnost. Kada upit bude obrađen, naš tim će Vas kontaktirati. Hvala na povjerenju!

### Šablon za firmu: `novi_upit` (opcionalno)

- Kategorija: **Utility**, jezik: **Bosnian** (`bs`)
- Tekst:

> Novi upit sa web stranice. Ime: {{1}}. Telefon: {{2}}. Email: {{3}}. Usluga: {{4}}. Upit: {{5}}

Ako šablon nazovete drugačije ili koristite drugi jezik, promijenite odgovarajuću vrijednost u `.env`.

Meta naplaćuje poslovne poruke po razgovoru. Cijene za BiH su na <https://developers.facebook.com/docs/whatsapp/pricing>.

## Objava na internetu

Server je obična Node aplikacija, pa radi na bilo kojem hostingu koji podržava Node.js 22: VPS, Render, Railway, Fly.io ili cPanel s Node.js podrškom.

- Start komanda: `npm start`
- Varijable iz `.env` upišite u postavke hostinga. Fajl `.env` ne stavljajte u git.
- Folder `data/` mora ostati sačuvan između restartova. Ako hosting to ne podržava, prebacite spremanje upita u bazu.
- Ispred servera koristite HTTPS. Većina hostinga ga uključuje automatski.

## Prije objave provjerite

- Kontakt podatke na stranici uzeo sam iz javnih poslovnih imenika (CompanyWall, eKapija, Poslovanje.ba). Provjerite ih prije objave: adresu, telefon `033 222 214`, faks `033 222 213` i email `info@glock-sigurnost.ba`.
- Tvrdnje u sekciji „O nama“ (osnovano 1995., licenca MUP-a KS, posebno odobrenje za zaštitu pravnih lica od federalnog značaja) preuzete su iz javnih izvora. Potvrdite da su tačne i aktuelne.
- Ako firma ima logo, zamijenite SVG štit u zaglavlju i podnožju.

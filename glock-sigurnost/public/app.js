// Glock Sigurnost: navigacija, animacije i forma za upit.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

$('#year').textContent = new Date().getFullYear();

// Navigacija: pozadina pri skrolu, mobilni meni, aktivni link
const nav = $('.nav');
const toggle = $('.nav__toggle');
const links = $('#nav-links');
const onScroll = () => nav.classList.toggle('is-scrolled', scrollY > 20);
addEventListener('scroll', onScroll, { passive: true });
onScroll();

const closeMenu = () => {
  toggle.setAttribute('aria-expanded', 'false');
  links.classList.remove('is-open');
  nav.classList.remove('menu-open');
};
toggle.addEventListener('click', () => {
  const open = toggle.getAttribute('aria-expanded') !== 'true';
  toggle.setAttribute('aria-expanded', String(open));
  links.classList.toggle('is-open', open);
  nav.classList.toggle('menu-open', open);
});
$$('a', links).forEach(a => a.addEventListener('click', closeMenu));
addEventListener('keydown', e => e.key === 'Escape' && closeMenu());

const sectionObserver = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (!e.isIntersecting) return;
    $$('a', links).forEach(a => a.classList.toggle('is-active', a.getAttribute('href') === `#${e.target.id}`));
  });
}, { rootMargin: '-45% 0px -50% 0px' });
$$('main section[id]').forEach(s => sectionObserver.observe(s));

// Pojavljivanje elemenata pri skrolu, sa blagim kašnjenjem unutar grupe
const revealObserver = new IntersectionObserver((entries, obs) => {
  entries.forEach(e => {
    if (!e.isIntersecting) return;
    e.target.classList.add('is-visible');
    e.target.querySelectorAll?.('[data-count]:not([data-plain])').forEach(countUp);
    if (e.target.matches('[data-count]:not([data-plain])')) countUp(e.target);
    obs.unobserve(e.target);
  });
}, { threshold: 0.15 });
$$('.reveal').forEach(el => {
  const siblings = $$(':scope > .reveal', el.parentElement);
  el.style.setProperty('--delay', `${Math.min(siblings.indexOf(el), 5) * 0.08}s`);
  revealObserver.observe(el);
});
const steps = $('.steps');
new IntersectionObserver(([e], obs) => {
  if (e.isIntersecting) { steps.classList.add('is-visible'); obs.disconnect(); }
}, { threshold: 0.3 }).observe(steps);

function countUp(el) {
  const target = Number(el.dataset.count);
  if (reduceMotion || !target) return;
  const start = performance.now();
  const dur = 1400;
  const tick = now => {
    const p = Math.min((now - start) / dur, 1);
    el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// Svjetlo koje prati miš na karticama usluga
$$('.card').forEach(card => card.addEventListener('pointermove', e => {
  const r = card.getBoundingClientRect();
  card.style.setProperty('--mx', `${e.clientX - r.left}px`);
  card.style.setProperty('--my', `${e.clientY - r.top}px`);
}));

// Službeni WhatsApp broj dolazi sa servera (varijabla COMPANY_WHATSAPP)
fetch('/api/config')
  .then(r => (r.ok ? r.json() : null))
  .then(cfg => {
    if (!cfg?.whatsapp) return;
    const url = `https://wa.me/${cfg.whatsapp}?text=${encodeURIComponent('Pozdrav, zanima me ponuda za zaštitu.')}`;
    $$('.wa-float, .wa-link').forEach(a => { a.href = url; });
    $('.wa-float').hidden = false;
    $('.contact__wa').hidden = false;
  })
  .catch(() => {});

// Forma za upit
const form = $('#upit-form');
const status = $('.form__status', form);
const rules = {
  ime: v => v.trim().length >= 2 || 'Unesite ime i prezime ili naziv firme.',
  telefon: v => /^\+?[\d\s/().-]{6,20}$/.test(v.trim()) && v.replace(/\D/g, '').length >= 8 || 'Unesite ispravan broj telefona, npr. 061 123 456.',
  email: v => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim()) || 'Unesite ispravnu email adresu.',
  poruka: v => v.trim().length >= 10 || 'Opišite upit u barem nekoliko riječi.',
};

function validateField(input) {
  const rule = rules[input.name];
  if (!rule) return true;
  const result = rule(input.value);
  const field = input.closest('.field');
  const msg = result === true ? '' : result;
  field.classList.toggle('has-error', !!msg);
  $('.field__err', field).textContent = msg;
  input.setAttribute('aria-invalid', String(!!msg));
  return !msg;
}
Object.keys(rules).forEach(name => {
  const input = form.elements[name];
  input.addEventListener('blur', () => validateField(input));
  input.addEventListener('input', () => input.closest('.field').classList.contains('has-error') && validateField(input));
});

form.addEventListener('submit', async e => {
  e.preventDefault();
  status.textContent = '';
  status.className = 'form__status';

  const fieldsOk = Object.keys(rules).map(n => validateField(form.elements[n])).every(Boolean);
  const consent = form.elements.saglasnost.checked;
  $('#saglasnost-err').textContent = consent ? '' : 'Potrebna je Vaša saglasnost da bismo Vas mogli kontaktirati.';
  if (!fieldsOk || !consent) {
    form.querySelector('[aria-invalid="true"], [name="saglasnost"]:not(:checked)')?.focus();
    return;
  }

  form.classList.add('is-loading');
  const data = Object.fromEntries(new FormData(form));
  try {
    const res = await fetch('/api/upit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || 'Slanje nije uspjelo.');
    status.classList.add('is-ok');
    const kanali = [body.whatsappSent && 'WhatsApp', body.emailSent && 'email'].filter(Boolean).join(' i na ');
    status.textContent = kanali
      ? `Hvala! Vaš upit je zaprimljen, a potvrdu smo Vam poslali na ${kanali}. Kontaktiraćemo Vas čim upit obradimo.`
      : 'Hvala! Vaš upit je zaprimljen. Kontaktiraćemo Vas čim upit obradimo.';
    form.reset();
  } catch (err) {
    status.classList.add('is-err');
    status.textContent = `${err.message} Pokušajte ponovo ili nas pozovite na 033 222 214.`;
  } finally {
    form.classList.remove('is-loading');
  }
});

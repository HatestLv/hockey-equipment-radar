/* =====================================================================
   HOCKEY EQUIPMENT RADAR — lapas loģika

   Dati:
     config.json        — veikali, modeļi, izmēri (VIENĪGAIS iestatījumu avots)
     scraped_data.json  — skrāpera rezultāti (cenas, izmēri, pieejamība)
     version.json       — lapas versija (to automātiski maina GitHub Actions)

   Struktūra:
     1. Stāvoklis un palīgfunkcijas
     2. Profils
     3. Bildes
     4. Piedāvājumu novērtēšana (viena funkcija kartītēm, tabulai un sākumlapai)
     5. Skati (sākums, slidas/nūjas, profils, u.c.)
     6. Notikumi
     7. Datu ielāde
   ===================================================================== */
'use strict';

/* ---------------------------------------------------------------------
   1. STĀVOKLIS UN PALĪGFUNKCIJAS
   --------------------------------------------------------------------- */
let CFG = null;            // config.json saturs
let OFFERS = [];           // scraped_data.json piedāvājumi
const DATA = { updatedAt: null, retailerStatus: {}, loaded: false, configError: false };

const S = {
  tab: 'home',
  view: 'cards',
  stockOnly: false,
  sort: 'default',
  searchQuery: '',
  sliderIndex: 0,
  profileDraft: null       // profila lapas nesaglabātās izmaiņas
};

const TEXT = {
  tabHome: 'Sākums',
  tabSkates: 'Slidas LV',
  tabSticks: 'Nūjas LV',
  tabProtective: 'Aizsargi (Drīzumā)',
  tabUsed: 'Lietots inventārs',
  tabIntl: 'Ārzemju deals',
  searchPh: 'Meklēt modeli, sēriju...',
  openStore: 'Atvērt veikalu →',
  checkStore: 'Pārbaudīt {store} lapā →'
};
const t = (k, params = {}) => Object.entries(params).reduce((s, [p, v]) => s.replace(`{${p}}`, v), TEXT[k] || k);

const FLAG_LV = `<svg width="18" height="12" viewBox="0 0 20 14"><rect width="20" height="14" fill="#981e32"/><rect y="5.6" width="20" height="2.8" fill="#fff"/></svg>`;
const ROLE_NAMES = { forward: 'uzbrucējam', defense: 'aizsargam', allround: 'universālam spēlētājam' };
const CATEGORY_LABELS = { Senior: 'Senior (SR)', Intermediate: 'Intermediate (INT)', Junior: 'Junior (JR)', Youth: 'Youth (Bērnu · YTH)' };

/** Drošs teksts HTML iekšā (dati nāk no veikalu lapām). */
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
/** Tikai http(s) saites. */
const safeUrl = u => (typeof u === 'string' && /^https?:\/\//i.test(u)) ? u : '#';
const eur = n => (n == null || !(n > 0)) ? '—' : '€' + Number(n).toFixed(2);
const row = (label, value) => `<div class="row"><span>${label}</span><span>${value}</span></div>`;
const pad = n => ('0' + n).slice(-2);
const fmtDate = d => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
const fmtDay = s => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || ''); return m ? `${m[3]}.${m[2]}.${m[1]}` : (s || '—'); };

/** '6.0' -> '6', 'YTH 11.5' -> 'Yth 11.5' — lai salīdzinātu izmērus no dažādiem veikaliem. */
function normSize(s) {
  if (s == null) return '';
  let v = String(s).trim().replace(',', '.');
  const yth = /^y(?:th|t|outh)?\s*/i.test(v);
  v = v.replace(/^y(?:th|t|outh)?\s*/i, '');
  const n = parseFloat(v);
  if (!isNaN(n)) v = String(n);
  return yth ? 'Yth ' + v : v;
}

const categories = () => CFG ? CFG.categories : ['Senior', 'Intermediate', 'Junior', 'Youth'];
const retailerKeys = () => Object.keys(CFG.retailers);
const sizeTable = (type, cat) => (CFG.sizeTables[type] && CFG.sizeTables[type][cat]) || [];
const modelsFor = (type, cat) => CFG.models.filter(m => m.type === type && m.categories.includes(cat));
const modelName = (m, cat) => `${m.name} ${cat}`;
const categoryUrl = (rKey, type, cat) => {
  const r = CFG.retailers[rKey];
  return (r.categoryUrls[type] && r.categoryUrls[type][cat]) || r.url;
};
const isTracked = (rKey, type, cat) => {
  const r = CFG.retailers[rKey];
  return !!(r.categoryUrls[type] && r.categoryUrls[type][cat]);
};

const VERSION = { version: null, released: null, notes: '' };

/* ---------------------------------------------------------------------
   2. PROFILS
   --------------------------------------------------------------------- */
const DEFAULT_PROFILE = {
  activeTab: 'skates',
  role: 'forward',
  skateBrand: 'Bauer',
  skateCat: 'Senior',
  size: '7.5',
  fit: 'FIT 2',
  skateFreq: '2-3',
  minSkate: 300,
  maxSkate: 650,
  stickBrand: 'Bauer',
  stickCat: 'Senior',
  stickStyle: 'forward',
  hand: 'Left',
  curve: 'P92',
  flex: '77',
  minStick: 100,
  maxStick: 350
};

function loadProfile() {
  try {
    const raw = localStorage.getItem('hsr_user_profile');
    if (raw) {
      const p = JSON.parse(raw);
      delete p.category;            // vecs, vairs neizmantots lauks
      if (p.size === 'pref') p.size = '7.5';
      return { ...DEFAULT_PROFILE, ...p };
    }
  } catch (e) { /* bojāti dati — izmanto noklusējumu */ }
  return { ...DEFAULT_PROFILE };
}

function saveProfile() {
  try { localStorage.setItem('hsr_user_profile', JSON.stringify(PROFILE)); } catch (e) {}
}

let PROFILE = loadProfile();

/** Pārbauda, vai profila izmērs/flex der izvēlētajai grupai (piem. pēc config izmaiņām). */
function sanitizeProfile(p) {
  if (!CFG) return p;
  if (!categories().includes(p.skateCat)) p.skateCat = 'Senior';
  if (!categories().includes(p.stickCat)) p.stickCat = 'Senior';
  if (p.size !== 'all' && !sizeTable('skate', p.skateCat).some(o => o.val === p.size)) p.size = 'all';
  if (p.flex !== 'all' && !sizeTable('stick', p.stickCat).some(o => o.val === p.flex)) p.flex = 'all';
  return p;
}

/**
 * Maina vecuma grupu. Katrai grupai atceras pēdējo izmēru un budžetu,
 * lai, pārslēdzoties SR -> YTH -> SR, tavs Senior izmērs nepazustu.
 */
function applyCategory(p, type, cat) {
  const isSkate = type === 'skate';
  const curCat = isSkate ? p.skateCat : p.stickCat;
  if (curCat === cat) return p;
  const keys = isSkate ? ['size', 'minSkate', 'maxSkate'] : ['flex', 'minStick', 'maxStick'];

  p.catMemory = JSON.parse(JSON.stringify(p.catMemory || {}));
  p.catMemory[type] = p.catMemory[type] || {};
  p.catMemory[type][curCat] = { [keys[0]]: p[keys[0]], [keys[1]]: p[keys[1]], [keys[2]]: p[keys[2]] };

  if (isSkate) p.skateCat = cat; else p.stickCat = cat;
  const saved = p.catMemory[type][cat];
  const budget = (CFG.defaultBudget && CFG.defaultBudget[type] && CFG.defaultBudget[type][cat]) || [0, 9999];
  p[keys[0]] = saved ? saved[keys[0]] : 'all';
  p[keys[1]] = saved ? saved[keys[1]] : budget[0];
  p[keys[2]] = saved ? saved[keys[2]] : budget[1];
  return sanitizeProfile(p);
}

/* ---------------------------------------------------------------------
   3. BILDES
   Katrai grupai var būt savas bildes:
     img/skates/<modelis>/<grupa>/1.png   (piem. .../bauer-supreme-m40/youth/1.png)
   Ja tādas nav, izmanto vispārējo:
     img/skates/<modelis>/1.png
   --------------------------------------------------------------------- */
function imageCandidates(m, cat) {
  const count = m.imgCount || 3;
  const list = [];
  for (let i = 1; i <= count; i++) {
    list.push([
      `${m.imgDir}/${cat.toLowerCase()}/${i}.png`,
      `${m.imgDir}/${i}.png`,
      `img/${m.id}.png`
    ]);
  }
  return list;
}

/** <img> ar automātisku pāreju uz nākamo variantu, ja fails neeksistē. */
function imgTag(candidates, alt, extra = '') {
  const [first, ...rest] = candidates;
  return `<img src="${esc(first)}" data-fb="${esc(rest.join('|'))}" alt="${esc(alt)}" onerror="imgFallback(this)" ${extra}>`;
}

function imgFallback(el) {
  const rest = (el.dataset.fb || '').split('|').filter(Boolean);
  if (!rest.length) { el.onerror = null; el.classList.add('img-missing'); return; }
  el.dataset.fb = rest.slice(1).join('|');
  el.src = rest[0];
}
window.imgFallback = imgFallback;

function setImg(el, candidatesStr) {
  const list = candidatesStr.split('|');
  el.classList.remove('img-missing');
  el.onerror = () => imgFallback(el);
  el.dataset.fb = list.slice(1).join('|');
  el.src = list[0];
}

/* ---------------------------------------------------------------------
   4. PIEDĀVĀJUMU NOVĒRTĒŠANA
   Viena funkcija nosaka katra modeļa stāvokli katrā veikalā.
   To izmanto kartītes, salīdzinājuma tabula un sākumlapa — tāpēc tās
   vienmēr rāda vienu un to pašu.
   --------------------------------------------------------------------- */
const findOffer = (modelId, rKey, cat) =>
  OFFERS.find(o => o.model === modelId && o.retailer === rKey && (o.category || 'Senior') === cat);

const offerTotal = o => (o && o.price > 0) ? o.price + (o.shipping || 0) : null;

function fitMatches(offerFits, wanted) {
  if (wanted === 'all') return true;
  if (!offerFits || !offerFits.length) return null;          // nav zināms
  const aliases = ((CFG.fitAliases || {})[wanted] || [wanted]).map(a => a.toUpperCase());
  return offerFits.some(f => aliases.includes(String(f).toUpperCase()));
}

/**
 * Atgriež { o, state, total, ... }
 * state:
 *   'not_tracked'  — šim veikalam/grupai dati netiek vākti
 *   'no_data'      — nav datu (skrāperis vēl nav darbojies vai kļūda)
 *   'not_found'    — veikalā šis modelis šajā grupā nav atrasts
 *   'out_of_stock' — atrasts, bet nav noliktavā
 *   'no_size'      — noliktavā, bet nav tava izmēra / roka / flex
 *   'over_budget'  — der, bet ārpus tava budžeta
 *   'match'        — der pilnībā
 */
function evaluate(m, rKey, cat) {
  const p = PROFILE;
  const o = findOffer(m.id, rKey, cat);
  const res = { o, state: 'no_data', total: offerTotal(o), sizeOk: null, fitOk: null, budgetOk: null, inStock: false };

  if (!isTracked(rKey, m.type, cat) || (o && o.status === 'NOT_TRACKED')) { res.state = 'not_tracked'; return res; }
  if (!o || o.status === 'ERROR' || (o.stale && !(o.price > 0))) { res.stale = !!(o && o.stale); return res; }
  if (!(o.price > 0)) { res.state = 'not_found'; return res; }
  if (!o.stock) { res.state = 'out_of_stock'; return res; }
  res.inStock = true;

  const min = m.type === 'skate' ? p.minSkate : p.minStick;
  const max = m.type === 'skate' ? p.maxSkate : p.maxStick;
  res.budgetOk = res.total >= (+min || 0) && res.total <= (+max || Infinity);

  if (m.type === 'skate') {
    const sizes = (o.sizes || []).map(normSize);
    res.sizeOk = p.size === 'all' ? true : (sizes.length ? sizes.includes(normSize(p.size)) : null);
    res.fitOk = fitMatches(o.fits, p.fit);
  } else {
    const chk = (list, val) => val === 'all' ? true : ((list && list.length) ? list.map(String).includes(String(val)) : null);
    const parts = [chk(o.hands, p.hand), chk(o.flexes, p.flex), chk(o.curves, p.curve)];
    res.sizeOk = parts.includes(false) ? false : (parts.includes(null) ? null : true);
    res.fitOk = true;
  }

  if (res.sizeOk === false || res.fitOk === false) res.state = 'no_size';
  else if (!res.budgetOk) res.state = 'over_budget';
  else res.state = 'match';
  return res;
}

/** Kartītes nozīmīte; ja neder tikai platums, saka to. */
function stateInfo(ev, m) {
  if (ev.state === 'no_size' && m.type === 'skate' && ev.sizeOk !== false && ev.fitOk === false) {
    return { badge: '<span class="badge b-demo">Nav tava platuma</span>', cls: 'card-partial' };
  }
  return STATE_INFO[ev.state];
}

const STATE_INFO = {
  match:        { badge: '<span class="badge b-ok">Der tev</span>', cls: '' },
  no_size:      { badge: '<span class="badge b-demo">Nav tava izmēra</span>', cls: 'card-partial' },
  over_budget:  { badge: '<span class="badge b-demo">Ārpus budžeta</span>', cls: 'card-partial' },
  out_of_stock: { badge: '<span class="badge b-no">Nav noliktavā</span>', cls: 'card-zero' },
  not_found:    { badge: '<span class="badge b-no">Nav atrasts</span>', cls: 'card-zero' },
  not_tracked:  { badge: '<span class="badge b-no">Drīzumā</span>', cls: 'card-zero' },
  no_data:      { badge: '<span class="badge b-no">Nav datu</span>', cls: 'card-zero' }
};

function stateNote(ev, m, rKey) {
  const p = PROFILE;
  const store = CFG.retailers[rKey].name;
  switch (ev.state) {
    case 'match':
      return ev.sizeOk === null
        ? `<div class="state-note warn">Ir noliktavā, bet ${store} neuzrāda izmērus — pārbaudi veikala lapā.</div>`
        : `<div class="state-note ok">Pieejams tavā izmērā un budžetā.</div>`;
    case 'no_size':
      if (m.type === 'skate') {
        return ev.fitOk === false
          ? `<div class="state-note warn">Tavs platums (${esc(p.fit)}) šajā veikalā nav pieejams.</div>`
          : `<div class="state-note warn">Tavs izmērs (${esc(p.size)}) šajā veikalā nav pieejams.</div>`;
      }
      return `<div class="state-note warn">Nav pieejams ar tavu satvērienu / flex / liekumu.</div>`;
    case 'over_budget': {
      const min = m.type === 'skate' ? p.minSkate : p.minStick;
      const max = m.type === 'skate' ? p.maxSkate : p.maxStick;
      return `<div class="state-note warn">Cena ārpus tava budžeta (€${min}–${max}).</div>`;
    }
    case 'out_of_stock': return `<div class="state-note muted">Veikalā atrasts, bet šobrīd nav noliktavā.</div>`;
    case 'not_found':    return `<div class="state-note muted">Šis modelis šajā vecuma grupā ${store} netika atrasts.</div>`;
    case 'not_tracked':  return `<div class="state-note muted">${store} cenas šai sadaļai vēl netiek vāktas.</div>`;
    default:             return `<div class="state-note muted">Dati vēl nav saņemti.</div>`;
  }
}

function sizesHtml(o, m) {
  if (!o) return '—';
  if (m.type === 'skate') {
    const sizes = o.sizes || [];
    if (!sizes.length) return '<span style="color:var(--muted)">Jāpārbauda veikalā</span>';
    const mine = normSize(PROFILE.size);
    const chips = sizes.map(s => `<span class="chip ${normSize(s) === mine ? 'mine' : ''}">${esc(s)}</span>`);
    if (PROFILE.size !== 'all' && !sizes.map(normSize).includes(mine)) {
      chips.push(`<span class="chip missing" title="Tavs izmērs">${esc(PROFILE.size)} ✕</span>`);
    }
    return `<span class="size-chips">${chips.join('')}</span>`;
  }
  const hands = (o.hands || []).join('/') || '—';
  return esc(hands);
}

function fitsHtml(o, m) {
  if (!o) return '—';
  if (m.type === 'skate') return (o.fits && o.fits.length) ? esc(o.fits.join(', ')) : '<span style="color:var(--muted)">Nav norādīts</span>';
  const flex = (o.flexes || []).join('/') || '—';
  const curves = (o.curves || []).join('/') || '—';
  return esc(`${flex} · ${curves}`);
}

/* ---------------------------------------------------------------------
   5. SKATI
   --------------------------------------------------------------------- */
function storeHeader(rKey, type = 'skate', cat = PROFILE.skateCat) {
  const r = CFG.retailers[rKey];
  return `<a class="store-header" href="${esc(safeUrl(categoryUrl(rKey, type, cat)))}" target="_blank" rel="noopener" title="${esc(r.name)} (${esc(cat)})">
    <div class="store-logo-box">
      <img class="logo-dark" src="${esc(r.logoDark)}" alt="${esc(r.name)}" onerror="this.onerror=null;this.src='img/${rKey}.png'">
      <img class="logo-light" src="${esc(r.logoLight)}" alt="${esc(r.name)}" onerror="this.onerror=null;this.src='img/${rKey}.png'">
    </div>
  </a>`;
}

function meter(m) {
  const key = m.type === 'stick' ? (PROFILE.stickStyle || PROFILE.role) : PROFILE.role;
  const v = m.match && (m.match[key] != null ? m.match[key] : m.match[PROFILE.role]);
  if (v == null) return '';
  return `<div class="meterbox">
    <div class="mlabel">
      <span>Atbilstība ${ROLE_NAMES[key] || ROLE_NAMES.forward} <span class="badge b-spec">${esc(m.profileBadge)}</span></span>
      <b>${v}%</b>
    </div>
    <div class="meter"><i style="left:${v}%"></i></div>
  </div>`;
}

function renderCard(m, rKey, cat) {
  const r = CFG.retailers[rKey];
  const ev = evaluate(m, rKey, cat);
  const o = ev.o;
  const info = stateInfo(ev, m);
  const hasPrice = o && o.price > 0;

  const imgs = imageCandidates(m, cat);
  const imgId = `cimg-${m.id}-${rKey}-${cat}`;
  const name = `${m.brand} ${modelName(m, cat)}`;
  const dots = imgs.length > 1 ? `<div class="card-img-dots">${imgs.map((c, i) =>
    `<span class="card-img-dot ${i === 0 ? 'active' : ''}" data-img-switch="${imgId}" data-img-src="${esc(c.join('|'))}"></span>`).join('')}</div>` : '';

  const priceHtml = hasPrice ? `<span class="price">${eur(o.price)}</span>` : `<span class="price is-zero">—</span>`;
  const stockHtml = ev.inStock
    ? `<span style="color:var(--green);font-weight:700">Noliktavā</span>`
    : (hasPrice ? `<span style="color:var(--amber)">Nav noliktavā</span>` : `<span style="color:var(--muted)">—</span>`);
  const checked = o ? `${fmtDay(o.checked)}${o.stale ? ' <span class="stale-tag" title="Pēdējā skenēšanā veikals neatbildēja">(veci dati)</span>' : ''}` : '—';

  const productUrl = o && o.url && hasPrice ? o.url : categoryUrl(rKey, m.type, cat);
  const btn = ev.inStock
    ? `<a class="btn" href="${esc(safeUrl(productUrl))}" target="_blank" rel="noopener">${t('openStore')}</a>`
    : `<a class="btn btn-zero" href="${esc(safeUrl(productUrl))}" target="_blank" rel="noopener">${t('checkStore', { store: esc(r.name) })}</a>`;

  return `
    <article class="card ${info.cls}">
      <div class="imgbox" data-open-lightbox="${esc(m.id)}" data-cat="${esc(cat)}" title="Noklikšķini, lai palielinātu">
        ${imgTag(imgs[0], name, `id="${esc(imgId)}"`)}
        ${dots}
      </div>
      <div class="body">
        <h3>${esc(name)}</h3>
        <p class="shop">${esc(r.name)} &nbsp; ${info.badge}</p>
        ${stateNote(ev, m, rKey)}
        <div class="card-specs-table">
          ${row('Cena', priceHtml)}
          ${row('Piegāde', hasPrice ? (o.shipping > 0 ? eur(o.shipping) : 'Bezmaksas') : '—')}
          ${row('Kopā', hasPrice ? `<b>${eur(ev.total)}</b>` : '—')}
          ${row(m.type === 'skate' ? 'Pieejamie izmēri' : 'Satvēriens', ev.inStock ? sizesHtml(o, m) : '—')}
          ${row(m.type === 'skate' ? 'Bauer FIT' : 'Flex · Liekums', ev.inStock ? fitsHtml(o, m) : '—')}
          ${row('Pieejamība', stockHtml)}
          ${row('Pēdējā pārbaude', checked)}
        </div>
        ${meter(m)}
        <p class="note">${esc(m.note)}</p>
      </div>
      ${btn}
    </article>`;
}

/** Stāvokļi, kuriem rāda kompakto kartīti (nav ko salīdzināt). */
const COMPACT_STATES = ['not_found', 'no_data', 'not_tracked'];

function renderCompactCard(m, rKey, cat, ev) {
  const r = CFG.retailers[rKey];
  const info = STATE_INFO[ev.state];
  const msg = {
    not_found: 'Šajā vecuma grupā nav atrasts',
    no_data: ev.stale ? 'Veikals pēdējā skenēšanā neatbildēja' : 'Dati vēl nav saņemti',
    not_tracked: 'Cenas vēl netiek vāktas'
  }[ev.state] || '';
  const url = categoryUrl(rKey, m.type, cat);
  return `<div class="card-compact">
    <p class="cc-title">${esc(m.brand)} ${esc(modelName(m, cat))}</p>
    <div class="cc-row"><span>${msg}</span>${info.badge}</div>
    <a href="${esc(safeUrl(url))}" target="_blank" rel="noopener">${t('checkStore', { store: esc(r.name) })}</a>
  </div>`;
}

/** Datora skats: režģis, kur katrs modelis ir viena rinda pāri visiem veikaliem. */
function renderStoresGrid(models, type, cat) {
  const rKeys = retailerKeys();
  const head = rKeys.map(k => storeHeader(k, type, cat)).join('');
  let rows = '';
  for (const m of models) {
    const evs = rKeys.map(k => evaluate(m, k, cat));
    if (S.stockOnly && !evs.some(e => e.inStock)) continue;          // nevienā veikalā nav — rindu nerāda
    rows += evs.map((ev, i) => {
      if (S.stockOnly && !ev.inStock) return '<div class="card-placeholder"></div>';
      return COMPACT_STATES.includes(ev.state) ? renderCompactCard(m, rKeys[i], cat, ev) : renderCard(m, rKeys[i], cat);
    }).join('');
  }
  if (!rows) rows = `<div class="store-empty" style="grid-column:1 / -1">${models.length ? 'Nav pieejamu modeļu ar šiem filtriem.' : 'Nav atrasts neviens modelis.'}</div>`;
  return `<div class="stores-grid">${head}${rows}</div>`;
}

/** Telefona skats: viens modelis, zem tā visi veikali. */
function renderMobileList(models, type, cat) {
  const rKeys = retailerKeys();
  const cards = models.map(m => {
    const evs = rKeys.map(k => ({ k, ev: evaluate(m, k, cat) }));
    if (S.stockOnly && !evs.some(x => x.ev.inStock)) return '';
    const matchTotals = evs.filter(x => x.ev.state === 'match').map(x => x.ev.total);
    const best = matchTotals.length ? Math.min(...matchTotals) : null;
    const imgs = imageCandidates(m, cat);
    const stores = evs.filter(x => !S.stockOnly || x.ev.inStock).map(({ k, ev }) => {
      const r = CFG.retailers[k];
      const o = ev.o;
      const hasPrice = o && o.price > 0;
      const isBest = best !== null && ev.state === 'match' && ev.total === best;
      const url = hasPrice && o.url ? o.url : categoryUrl(k, m.type, cat);
      const meta = ev.inStock
        ? `${stateInfo(ev, m).badge} ${m.type === 'skate' ? sizesHtml(o, m) : `<span>${fitsHtml(o, m)}</span>`}`
        : STATE_INFO[ev.state].badge;
      return `<div class="m-store ${isBest ? 'is-best' : ''}">
        <span class="m-store-name">${esc(r.name)}${isBest ? ' <span class="badge b-ok">★ Labākā</span>' : ''}</span>
        <span class="m-store-price ${hasPrice ? '' : 'is-zero'}">${hasPrice ? eur(ev.total) : '—'}</span>
        <div class="m-store-meta">${meta}</div>
        <a class="m-link" href="${esc(safeUrl(url))}" target="_blank" rel="noopener">${ev.inStock ? t('openStore') : t('checkStore', { store: esc(r.name) })}</a>
      </div>`;
    }).join('');
    return `<article class="m-card">
      <div class="m-head">
        <div class="m-thumb" data-open-lightbox="${esc(m.id)}" data-cat="${esc(cat)}">${imgTag(imgs[0], m.name)}</div>
        <div><h3>${esc(m.brand)} ${esc(modelName(m, cat))}</h3><div class="m-sub">${esc(m.series)} · ${esc(m.profileBadge)}</div></div>
      </div>
      ${stores}
    </article>`;
  }).join('');
  return `<div class="mobile-list">${cards || '<div class="store-empty">Nav pieejamu modeļu ar šiem filtriem.</div>'}</div>`;
}

const MOBILE_MQ = window.matchMedia('(max-width: 960px)');
MOBILE_MQ.addEventListener('change', () => { if (S.tab === 'skates' || S.tab === 'sticks') render(); });

/** Modeļi izvēlētajai grupai ar meklēšanu un kārtošanu. */
function visibleModels(type, cat) {
  let list = modelsFor(type, cat);
  const q = S.searchQuery.trim().toLowerCase();
  if (q) list = list.filter(m => `${m.brand} ${modelName(m, cat)} ${m.series}`.toLowerCase().includes(q));

  if (S.sort === 'price') {
    const best = m => {
      const totals = retailerKeys().map(k => evaluate(m, k, cat)).filter(e => e.inStock).map(e => e.total);
      return totals.length ? Math.min(...totals) : Infinity;
    };
    list = [...list].sort((a, b) => best(a) - best(b));
  } else if (S.sort !== 'default') {
    list = [...list].sort((a, b) => (b.id === S.sort) - (a.id === S.sort));
  }
  return list;
}

function renderTableView(models, type, cat) {
  const rs = retailerKeys();
  const head = rs.map(k => `<th>${esc(CFG.retailers[k].name)}</th>`).join('');
  const body = models.map(m => {
    const evs = rs.map(k => evaluate(m, k, cat));
    const matchTotals = evs.filter(e => e.state === 'match').map(e => e.total);
    const best = matchTotals.length ? Math.min(...matchTotals) : null;

    const cells = evs.map(ev => {
      if (S.stockOnly && !ev.inStock) return `<td><span class="badge b-no">—</span></td>`;
      if (!ev.inStock) {
        const label = { out_of_stock: 'Nav noliktavā', not_found: 'Nav atrasts', not_tracked: 'Drīzumā', no_data: 'Nav datu' }[ev.state];
        const price = ev.o && ev.o.price > 0 ? `<b style="color:var(--muted)">${eur(ev.total)}</b><br>` : '';
        return `<td>${price}<span class="badge b-no">${label}</span></td>`;
      }
      const isBest = best !== null && ev.state === 'match' && ev.total === best;
      const style = isBest ? 'background:rgba(52,211,153,0.1); outline:2px solid var(--green); outline-offset:-2px; border-radius:6px;' : '';
      const bestLabel = isBest ? `<div style="display:inline-block; background:var(--green); color:#000; font-size:9px; font-weight:900; padding:2px 6px; border-radius:4px; margin-bottom:6px; text-transform:uppercase;">★ Labākā cena</div><br>` : '';
      const note = {
        match: ev.sizeOk === null ? '<span class="cell-state warn">Izmēri jāpārbauda</span>' : '<span class="cell-state" style="color:var(--green)">Der tev</span>',
        no_size: `<span class="cell-state warn">${m.type === 'skate' ? 'Nav tava izmēra' : 'Neder profilam'}</span>`,
        over_budget: '<span class="cell-state warn">Ārpus budžeta</span>'
      }[ev.state];
      const specs = m.type === 'skate'
        ? `${(ev.o.sizes || []).join(', ') || '—'} · ${(ev.o.fits || []).join(', ') || '—'}`
        : `${(ev.o.hands || []).join('/') || '—'} · Flex ${(ev.o.flexes || []).join('/') || '—'}`;
      return `<td style="${style}">${bestLabel}<b style="font-size:16px;${isBest ? 'color:var(--green);' : ''}">${eur(ev.total)}</b>${note}<small style="color:var(--muted)">${esc(specs)}</small></td>`;
    }).join('');
    return `<tr><td><b style="font-size:14px">${esc(m.brand)} ${esc(modelName(m, cat))}</b></td>${cells}</tr>`;
  }).join('');
  return `<div class="tw"><table><tr><th>Modelis</th>${head}</tr>${body}</table></div>`;
}

function filtersBar(type, cat) {
  const models = modelsFor(type, cat);
  const short = CFG.categoryShort[cat] || cat;
  const p = PROFILE;
  const sizeTxt = p.size === 'all' ? 'visi izm.' : `Izm. ${p.size}`;
  const flexTxt = p.flex === 'all' ? 'visi flex' : `Flex ${p.flex}`;
  const pill = type === 'skate'
    ? `Profils: ${short} · ${sizeTxt} · ${p.fit === 'all' ? 'visi platumi' : p.fit} · €${p.minSkate}–${p.maxSkate}`
    : `Profils: ${short} · ${p.hand} · ${flexTxt} · ${p.curve === 'all' ? 'visi liekumi' : p.curve} · €${p.minStick}–${p.maxStick}`;

  let sortLabel = 'Pēc noklusējuma';
  if (S.sort === 'price') sortLabel = 'Lētākais vispirms';
  const sm = models.find(m => m.id === S.sort);
  if (sm) sortLabel = modelName(sm, cat);

  return `<div class="filters-bar">
    <button type="button" class="profile-pill-link" data-open="profile">
      <span class="profile-pill-dot"></span>
      <span><b>${esc(pill)}</b></span>
      <span class="profile-pill-tag">MAINĪT ⚙️</span>
    </button>
    <div class="divider"></div>
    <div style="display:flex; align-items:center; gap:8px;">
      <span style="font-size:13px; color:var(--muted);">Kārtot:</span>
      <div class="ui-dropdown" data-dropdown-id="f-sort" style="width:auto; min-width:170px;">
        <button type="button" class="ui-dropdown-btn">
          <span class="ui-dropdown-label">${esc(sortLabel)}</span>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="#a9b0be" stroke-width="2"><path d="M1 1l4 4 4-4"/></svg>
        </button>
        <div class="ui-dropdown-menu">
          <button type="button" class="ui-dropdown-opt ${S.sort === 'default' ? 'active' : ''}" data-val="default">Pēc noklusējuma</button>
          <button type="button" class="ui-dropdown-opt ${S.sort === 'price' ? 'active' : ''}" data-val="price">Lētākais vispirms</button>
          ${models.map(m => `<button type="button" class="ui-dropdown-opt ${S.sort === m.id ? 'active' : ''}" data-val="${esc(m.id)}">${esc(modelName(m, cat))} vispirms</button>`).join('')}
        </div>
      </div>
    </div>
    <label class="custom-chk-label">
      <input type="checkbox" id="f-stock"${S.stockOnly ? ' checked' : ''}>
      <span class="custom-chk-box"></span>
      Tikai noliktavā
    </label>
    <div class="views">
      <button data-v="cards" class="${S.view === 'cards' ? 'on' : ''}">Kartes</button>
      <button data-v="table" class="${S.view === 'table' ? 'on' : ''}">Salīdzinājums</button>
    </div>
  </div>`;
}

/** Brīdinājumi par veikaliem, kuru dati netiek nolasīti. */
function dataNotice(type, cat) {
  if (!DATA.loaded) return `<div class="notice-bar">Dati tiek ielādēti...</div>`;
  const rs = retailerKeys();
  const untracked = rs.filter(k => !isTracked(k, type, cat));
  if (untracked.length === rs.length) {
    return `<div class="notice-bar"><b>Drīzumā.</b> ${type === 'stick' ? 'Nūju' : 'Šīs sadaļas'} cenas veikalos vēl netiek automātiski vāktas. Zemāk redzami modeļi un saites uz veikaliem.</div>`;
  }
  if (!OFFERS.some(o => o.type === type && o.status !== 'NOT_TRACKED')) {
    return `<div class="notice-bar"><b>Dati vēl nav savākti.</b> ${type === 'stick' ? 'Nūju' : 'Šīs sadaļas'} cenas parādīsies pēc nākamās automātiskās skenēšanas.</div>`;
  }
  const bad = rs.filter(k => !untracked.includes(k) && ['error', 'empty', 'partial'].includes(DATA.retailerStatus[k]));
  if (!bad.length) return '';
  const names = bad.map(k => CFG.retailers[k].name + (DATA.retailerStatus[k] === 'partial' ? ' (daļēji)' : '')).join(', ');
  return `<div class="notice-bar"><b>Uzmanību:</b> ${esc(names)} dati pēdējā skenēšanā netika pilnībā nolasīti. Šo veikalu kartītēs var būt veci dati vai "Nav atrasts" — pārbaudi veikala lapā.</div>`;
}

function viewCategory(type) {
  const isSkate = type === 'skate';
  const cat = isSkate ? PROFILE.skateCat : PROFILE.stickCat;
  const models = visibleModels(type, cat);
  const rKeys = retailerKeys();

  // Kopsavilkums — tikai šīs grupas modeļi
  const evs = modelsFor(type, cat).flatMap(m => rKeys.map(k => evaluate(m, k, cat)));
  const matches = evs.filter(e => e.state === 'match').map(e => e.total);
  const inStock = evs.filter(e => e.inStock).map(e => e.total);
  const verified = evs.filter(e => e.inStock && e.o.status === 'VERIFIED').length;
  const tracked = evs.filter(e => e.state !== 'not_tracked').length;

  const p = PROFILE;
  const sub = isSkate
    ? `Hokeja Pasaule, Hokejam.lv, Sportega. Profils: <b>${ROLE_NAMES[p.role]}</b>, vecuma grupa <b>${cat}</b>, izmērs <b>${p.size === 'all' ? 'visi' : esc(p.size)}</b>, platums <b>${p.fit === 'all' ? 'visi' : esc(p.fit)}</b>.`
    : `Hokeja Pasaule, Hokejam.lv, Sportega. Profils: <b>${esc(p.hand)}</b>, Flex <b>${p.flex === 'all' ? 'visi' : esc(p.flex)}</b>, liekums <b>${p.curve === 'all' ? 'visi' : esc(p.curve)}</b>, vecuma grupa <b>${cat}</b>.`;

  return `
    <div class="section-top-row">
      <h1>${isSkate ? t('tabSkates') : t('tabSticks')}</h1>
      <div style="text-align:right; font-size:12px; color:var(--muted); padding-bottom:4px;">
        Preču datu atjauninājums:<br>
        <b style="color:var(--text); font-size:14px; font-family:monospace;">${DATA.updatedAt ? fmtDate(DATA.updatedAt) : (DATA.loaded ? 'nav datu' : 'Tiek sinhronizēts...')}</b>
      </div>
    </div>
    <p class="sub">${sub}</p>
    <div class="sum">
      <div><small>Labākā cena tavam profilam</small><b>${matches.length ? eur(Math.min(...matches)) : '—'}</b></div>
      <div><small>Zemākā cena (jebkurš izmērs)</small><b>${inStock.length ? eur(Math.min(...inStock)) : '—'}</b></div>
      <div><small>Pārbaudīti piedāvājumi</small><b>${verified} / ${tracked}</b></div>
      <div><small>Datu avots</small><b><span class="badge ${DATA.updatedAt ? 'b-ok' : 'b-no'}">${DATA.updatedAt ? 'GITHUB ACTIONS (LIVE)' : 'GAIDA DATUS'}</span></b></div>
    </div>
    ${dataNotice(type, cat)}
    ${filtersBar(type, cat)}
    ${S.view === 'table' ? renderTableView(models, type, cat) : (MOBILE_MQ.matches ? renderMobileList(models, type, cat) : renderStoresGrid(models, type, cat))}
  `;
}

/** Labākais veikals konkrētam modelim: vispirms 'match', tad lētākais noliktavā. */
function bestRetailerFor(m, cat) {
  const order = { match: 0, over_budget: 1, no_size: 2, out_of_stock: 3, not_found: 4, no_data: 5, not_tracked: 6 };
  const evs = retailerKeys().map(k => ({ k, ev: evaluate(m, k, cat) }));
  evs.sort((a, b) => (order[a.ev.state] - order[b.ev.state]) || ((a.ev.total || Infinity) - (b.ev.total || Infinity)));
  return evs[0].k;
}

/** Ieteicamais modelis: vispirms tie, kas tev der / ir noliktavā, tad pēc lomas atbilstības. */
function recommendedModel(type, cat, roleKey) {
  const list = modelsFor(type, cat);
  if (!list.length) return null;
  const rank = m => {
    const states = retailerKeys().map(k => evaluate(m, k, cat).state);
    return states.includes('match') ? 0 : (states.some(s => s === 'no_size' || s === 'over_budget') ? 1 : 2);
  };
  return [...list].sort((a, b) => (rank(a) - rank(b)) || (((b.match || {})[roleKey] || 0) - ((a.match || {})[roleKey] || 0)))[0];
}

function viewHome() {
  const isForward = PROFILE.role === 'forward';
  const recSkate = recommendedModel('skate', PROFILE.skateCat, PROFILE.role);
  const recStick = recommendedModel('stick', PROFILE.stickCat, PROFILE.stickStyle || PROFILE.role);

  return `
    <div class="hero-slider-wrap">
      <div class="hero-slide active" style="background-image:linear-gradient(90deg, rgba(14,15,19,0.92) 40%, rgba(14,15,19,0.4)), url('img/banners/banner_1.jpg');">
        <div class="hero-content">
          <span class="hero-tag">Jaunums veikalos</span>
          <h2 class="hero-title">Bauer S26 PULSE2 WHITE</h2>
          <p class="hero-desc">Jauda, precizitāte un ātrums katrā metienā! Izvēlies savu jauno nūju un dodies uz ledus ar pārliecību – iegādājies jau šodien par labākajām cenām reģionā.</p>
          <a href="#" data-t="sticks" class="hero-btn">Skatīt nūju radaru →</a>
        </div>
      </div>
      <div class="hero-slide" style="background-image:linear-gradient(90deg, rgba(14,15,19,0.92) 40%, rgba(14,15,19,0.4)), url('img/banners/banner_2.jpg');">
        <div class="hero-content">
          <span class="hero-tag">Cenu analīze</span>
          <h2 class="hero-title">Atrodi labāko inventāra cenu</h2>
          <p class="hero-desc">4 reizes dienā pārbaudām Hokeja Pasaule, Hokejam.lv un Sportega cenas, izmērus un noliktavas atlikumus.</p>
          <a href="#" data-t="skates" class="hero-btn">Salīdzināt slidas →</a>
        </div>
      </div>
      <div class="slider-dots">
        <span class="slider-dot active" data-slide="0"></span>
        <span class="slider-dot" data-slide="1"></span>
      </div>
    </div>

    <div class="home-recom">
      <div class="home-recom-title">
        <h3 style="margin:0 0 6px; font-size:22px; font-weight:800; letter-spacing:-0.01em;">Pielāgots tavam stilam: <span style="color:var(--accent); text-transform:uppercase;">${isForward ? 'Uzbrucējs' : 'Aizsargs'}</span> · ${esc(CFG.categoryShort[PROFILE.skateCat])}</h3>
        <p style="margin:0; font-size:14px; color:var(--muted); line-height:1.4;">Balstoties uz tavu spēlētāja profilu, vecuma grupu un izmēru, iesakām šos modeļus labākajā pieejamajā veikalā.</p>
      </div>
      <div class="rail-wrap">
        ${recSkate ? renderCard(recSkate, bestRetailerFor(recSkate, PROFILE.skateCat), PROFILE.skateCat) : ''}
        ${recStick ? renderCard(recStick, bestRetailerFor(recStick, PROFILE.stickCat), PROFILE.stickCat) : ''}
        <article class="card card-zero">
          <div class="imgbox" style="cursor:default;">
            <img src="img/icons/shield.png" alt="Aizsargu modulis" style="max-height:80px; max-width:80px; object-fit:contain; filter:drop-shadow(0 4px 12px rgba(0,0,0,0.45));" onerror="if(this.src.indexOf('img/shield.png')===-1){this.src='img/shield.png';}else{this.style.display='none';this.nextElementSibling.style.display='block';}">
            <div style="display:none; font-size:48px; opacity:0.85;">🛡️</div>
          </div>
          <div class="body">
            <h3>Hockey Equipment Radar PRO</h3>
            <p class="shop">Pilns ekipējuma komplekts &nbsp; <span class="badge b-demo">Drīzumā</span></p>
            <div class="card-specs-table">
              ${row('Kategorijas', 'Plecsargi · Elkoņsargi · Kājsargi · Bikses · Cimdi · Ķiveres')}
              ${row('Aizsardzība', 'Amatieru – Elites līmenis')}
              ${row('Pieejamība', '<span style="color:var(--amber)">Tiek izstrādāts</span>')}
              ${row('Statuss', 'Plānots 2026/2027')}
            </div>
            <p class="note">Tiek izstrādāts viedais plecsargu, elkoņsargu, kājsargu, bikšu, cimdu un ķiveres salīdzināšanas modulis ar precīziem izmēru kalkulatoriem un aizsardzības klasēm.</p>
          </div>
          <a class="btn btn-zero" href="#" data-t="protective">Uzzināt vairāk →</a>
        </article>
      </div>
    </div>

    <div style="margin-top:36px; padding:10px 0;">
      <h2 style="margin:0 0 20px; font-size:20px; font-weight:900; text-align:center; color:var(--text); letter-spacing:.02em;">Salīdzināšanā iesaistītie veikali</h2>
      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:18px; align-items:center;">
        ${retailerKeys().map(k => storeHeader(k)).join('')}
      </div>
    </div>`;
}

function viewProtective() {
  return `
    <div class="uc-wrap">
      <div class="uc-img-box">
        <img src="img/under-construction.png" alt="Aizsargu modulis izstrādē" class="uc-img" onerror="this.onerror=function(){this.style.display='none';}; this.src='img/under-construction.jpg';">
        <div class="uc-img-shadow"></div>
      </div>
      <div>
        <span class="hero-tag" style="margin-bottom:12px;">Drīzumā</span>
        <h1 style="font-size:26px; margin-bottom:10px;">Hockey Equipment Radar PRO</h1>
        <p style="color:var(--muted); max-width:560px; margin:0 auto 24px; font-size:14px; line-height:1.6;">
          Tiek izstrādāts viedais plecsargu, elkoņsargu, kājsargu, bikšu, cimdu un ķiveres salīdzināšanas modulis ar precīziem izmēru kalkulatoriem un aizsardzības klasēm.
        </p>
        <button data-t="home" class="btn-save-profile" style="padding:10px 22px; font-size:14px;">Atgriezties uz sākumu</button>
      </div>
    </div>`;
}

function viewUsed() {
  return `
  <div class="section-top-row"><h1>Lietots inventārs</h1></div>
  <p class="sub">Sludinājumu agregācija šobrīd nav automātiska. Apskati piedāvājumus tiešajos avotos:</p>
  <div class="src">${(CFG.usedSources || []).map(s => `<div class="card"><b>${esc(s.name)}</b><span class="badge b-no">Manuāls avots</span><a class="btn" href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener">Atvērt ${esc(s.name)} →</a></div>`).join('')}</div>`;
}

function viewIntl() {
  return `
  <div class="section-top-row"><h1>Ārzemju deals</h1></div>
  <p class="sub">Eiropas Savienības interneta veikali ar piegādi uz Latviju.</p>
  <div class="empty">Veikalu saraksts tiek sagatavots. Tiks iekļauti pārbaudīti veikali ar skaidriem piegādes un atgriešanas nosacījumiem uz Latviju.</div>`;
}

/* ----- Profila lapa ----- */
function dropdown(id, options, current, labelFn) {
  const cur = options.find(o => o.val === current) || options[0];
  return `<div class="ui-dropdown" data-dropdown-id="${id}" id="dd-${id}">
    <button type="button" class="ui-dropdown-btn">
      <span class="ui-dropdown-label">${esc(labelFn ? labelFn(cur) : cur.label)}</span>
      <svg width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="#a9b0be" stroke-width="2"><path d="M1 1l4 4 4-4"/></svg>
    </button>
    <div class="ui-dropdown-menu">
      ${options.map(o => `<button type="button" class="ui-dropdown-opt ${o.val === cur.val ? 'active' : ''}" data-val="${esc(o.val)}" ${o.disabled ? 'style="opacity:0.4; cursor:not-allowed;" data-disabled="1"' : ''}>${esc(o.label)}</button>`).join('')}
    </div>
  </div>`;
}

const field = (label, html) => `<div class="form-group"><label>${label}</label>${html}</div>`;
const numField = (id, label, val) => `<div class="form-group"><label for="${id}">${label}</label><input type="number" id="${id}" class="form-input-box" min="0" value="${esc(val)}"></div>`;

const sizeOptions = cat => [...sizeTable('skate', cat), { val: 'all', label: `Visi ${cat} izmēri` }];
const flexOptions = cat => [...sizeTable('stick', cat), { val: 'all', label: `Visi ${cat} Flex` }];

const OPTS = {
  brand: [{ val: 'Bauer', label: 'Bauer' }, { val: 'CCM', label: 'CCM (Drīzumā)', disabled: true }],
  cat: () => categories().map(c => ({ val: c, label: CATEGORY_LABELS[c] || c })),
  fit: [
    { val: 'FIT 1', label: 'FIT 1 — Šaura pēda / zems pacēlums' },
    { val: 'FIT 2', label: 'FIT 2 — Standarta platums & pacēlums (D / Regular)' },
    { val: 'FIT 3', label: 'FIT 3 — Plata pēda / augsts pacēlums (EE)' },
    { val: 'all', label: 'Visi platumi' }
  ],
  role: [
    { val: 'forward', label: 'Uzbrucējs (akcents uz manevrētspēju)' },
    { val: 'defense', label: 'Aizsargs (akcents uz stabilitāti)' }
  ],
  freq: [
    { val: '1-2', label: '1–2x nedēļā (Iesācējs / Amatieris)' },
    { val: '2-3', label: '2–3x nedēļā (Regulāri treniņi)' },
    { val: '3-4', label: '3–4x nedēļā (Pusprofesionālis)' },
    { val: '5+', label: '5+ reizes nedēļā (Augsta slodze / Pro)' }
  ],
  stickStyle: [
    { val: 'forward', label: 'Uzbrucējs — Ātri plaukstas metieni & Dribls (Low-Kick)' },
    { val: 'defense', label: 'Aizsargs — Jaudīgi šķēlieni & One-timer (Mid/High-Kick)' },
    { val: 'allround', label: 'Universāls — Visi metienu veidi (Hybrid-Kick)' }
  ],
  hand: [{ val: 'Left', label: 'Kreisā roka lejā (Left)' }, { val: 'Right', label: 'Labā roka lejā (Right)' }],
  curve: [{ val: 'P92', label: 'P92' }, { val: 'P28', label: 'P28' }, { val: 'all', label: 'Visi liekumi' }]
};

/** Profila dropdown id -> PROFILE lauks */
const PROFILE_FIELDS = {
  'p-skate-brand': 'skateBrand', 'p-skate-cat': 'skateCat', 'p-size': 'size', 'p-fit': 'fit',
  'p-role': 'role', 'p-skate-freq': 'skateFreq', 'p-stick-brand': 'stickBrand', 'p-stick-cat': 'stickCat',
  'p-stick-style': 'stickStyle', 'p-hand': 'hand', 'p-curve': 'curve', 'p-flex': 'flex'
};

function viewProfile() {
  if (!S.profileDraft) S.profileDraft = { ...PROFILE };
  const d = S.profileDraft;
  const tab = d.activeTab || 'skates';

  return `
  <div class="profile-container">
    <div class="section-top-row"><h1>Mans Spēlētāja Profils</h1></div>
    <p class="sub">Pielāgo savus izmērus slidām un nūjām. Radars automātiski atlasīs un sarindos piedāvājumus pēc šiem datiem.</p>

    <div class="profile-tabs-bar">
      <div class="profile-tabs">
        <button class="profile-tab-btn ${tab === 'skates' ? 'active' : ''}" data-ptab="skates">Slidu profils</button>
        <button class="profile-tab-btn ${tab === 'sticks' ? 'active' : ''}" data-ptab="sticks">Nūju profils</button>
      </div>
      <button type="button" class="btn-chart-modal" id="btn-open-chart" data-chart="${tab}">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        <span>${tab === 'skates' ? 'Slidu izmēru tabula' : 'Nūju izmēru tabula'}</span>
      </button>
    </div>

    <div class="profile-card-single">
      <div class="profile-unified-grid" style="${tab === 'skates' ? '' : 'display:none'}">
        ${field('Zīmols', dropdown('p-skate-brand', OPTS.brand, d.skateBrand))}
        ${field('Vecuma grupa', dropdown('p-skate-cat', OPTS.cat(), d.skateCat))}
        ${field('Vēlamais izmērs', dropdown('p-size', sizeOptions(d.skateCat), d.size))}
        ${field('Bauer FIT sistēma', dropdown('p-fit', OPTS.fit, d.fit))}
        ${field('Pozīcija laukumā', dropdown('p-role', OPTS.role, d.role))}
        ${field('Treniņu biežums', dropdown('p-skate-freq', OPTS.freq, d.skateFreq))}
        ${numField('p-minSkate', 'Minimālā cena (€)', d.minSkate)}
        ${numField('p-maxSkate', 'Maksimālā cena (€)', d.maxSkate)}
      </div>

      <div class="profile-unified-grid" style="${tab === 'sticks' ? '' : 'display:none'}">
        ${field('Zīmols', dropdown('p-stick-brand', OPTS.brand, d.stickBrand))}
        ${field('Vecuma grupa', dropdown('p-stick-cat', OPTS.cat(), d.stickCat))}
        ${field('Spēles stils & Pozīcija', dropdown('p-stick-style', OPTS.stickStyle, d.stickStyle))}
        ${field('Satvēriens', dropdown('p-hand', OPTS.hand, d.hand))}
        ${field('Lāpstiņas liekums', dropdown('p-curve', OPTS.curve, d.curve))}
        ${field('Cietība (Flex)', dropdown('p-flex', flexOptions(d.stickCat), d.flex))}
        ${numField('p-minStick', 'Minimālā cena (€)', d.minStick)}
        ${numField('p-maxStick', 'Maksimālā cena (€)', d.maxStick)}
      </div>

      <div class="profile-actions">
        <button type="button" id="btn-save-profile" class="btn-save-profile">Saglabāt profilu</button>
        <button type="button" id="btn-reset-profile" class="btn-reset-profile">Atiestatīt noklusējumu</button>
        <div id="save-toast" class="save-toast"></div>
      </div>
    </div>
  </div>`;
}

/* ----- Galvenā renderēšana ----- */
function updateHeaderNav() {
  const tabs = [['home', 'tabHome'], ['skates', 'tabSkates'], ['sticks', 'tabSticks'], ['protective', 'tabProtective'], ['used', 'tabUsed'], ['intl', 'tabIntl']];
  document.getElementById('nav').innerHTML = tabs.map(([k, label]) => `<button data-t="${k}" class="${S.tab === k ? 'on' : ''}">${t(label)}</button>`).join('');
}

function updateStatic() {
  document.getElementById('current-lang-flag').innerHTML = FLAG_LV;
  document.getElementById('current-lang-code').textContent = 'LV';
  document.getElementById('site-search').placeholder = t('searchPh');
  document.querySelectorAll('.lang-opt').forEach(b => b.classList.toggle('active', b.dataset.lang === 'lv'));
  if (VERSION.version) {
    const v = document.getElementById('ui-version');
    v.textContent = 'v' + VERSION.version;
    v.title = VERSION.notes || '';
    const d = new Date(VERSION.released);
    document.getElementById('ui-last-modified').textContent = isNaN(d.getTime()) ? '—' : fmtDate(d);
  }
}

function render() {
  updateHeaderNav();
  updateStatic();
  const app = document.getElementById('app');
  if (!CFG) {
    app.innerHTML = DATA.configError
      ? `<div class="empty" style="margin-top:40px">Neizdevās ielādēt <b>config.json</b>. Pārliecinies, ka fails ir augšupielādēts blakus index.html.</div>`
      : `<div class="empty" style="margin-top:40px">Ielādē...</div>`;
    return;
  }
  if (S.tab !== 'profile') S.profileDraft = null;
  const views = {
    home: viewHome,
    skates: () => viewCategory('skate'),
    sticks: () => viewCategory('stick'),
    protective: viewProtective,
    used: viewUsed,
    intl: viewIntl,
    profile: viewProfile
  };
  app.innerHTML = (views[S.tab] || viewHome)();
}

/* ----- Modālie logi ----- */
function openLightbox(modelId, cat) {
  const m = CFG.models.find(x => x.id === modelId);
  if (!m) return;
  const imgs = imageCandidates(m, cat);
  const main = document.getElementById('lightbox-main-img');
  setImg(main, imgs[0].join('|'));
  document.getElementById('lightbox-thumbs').innerHTML = imgs.map((c, i) => `
    <div class="lightbox-thumb ${i === 0 ? 'active' : ''}" data-lb-src="${esc(c.join('|'))}">
      ${imgTag(c, 'Bilde ' + (i + 1))}
    </div>`).join('');
  document.getElementById('modal-lightbox').classList.add('open');
}

function openChartModal(type) {
  const img = document.getElementById('modal-chart-img');
  const base = type === 'skates' ? 'skate-size-chart' : 'stick-size-chart';
  const sources = [`img/${base}.jpg`, `img/${base}.png`, `img/tables/${base}.jpg`, `img/tables/${base}.png`, `img/${base}.jpeg`];
  setImg(img, sources.join('|'));
  document.getElementById('modal-chart').classList.add('open');
}

/* ---------------------------------------------------------------------
   6. NOTIKUMI
   --------------------------------------------------------------------- */
function closeAllDropdowns() {
  document.querySelectorAll('.ui-dropdown-menu').forEach(m => m.classList.remove('open'));
  document.querySelectorAll('.ui-dropdown-btn').forEach(b => b.classList.remove('active'));
}

/** Nolasa profila skaitļu laukus melnrakstā (tie netiek glabāti, kamēr nenospiež Saglabāt). */
function readDraftNumbers() {
  const d = S.profileDraft;
  if (!d) return;
  ['minSkate', 'maxSkate', 'minStick', 'maxStick'].forEach(k => {
    const el = document.getElementById('p-' + k);
    if (el && el.value !== '') d[k] = +el.value;
  });
}

function onProfileDropdown(id, val) {
  const d = S.profileDraft;
  if (!d || !PROFILE_FIELDS[id]) return;
  readDraftNumbers();
  if (id === 'p-skate-cat') applyCategory(d, 'skate', val);
  else if (id === 'p-stick-cat') applyCategory(d, 'stick', val);
  else d[PROFILE_FIELDS[id]] = val;
  // grupa maina izmēru sarakstu un budžetu — pārzīmē profila formu
  if (id === 'p-skate-cat' || id === 'p-stick-cat') render();
}

document.addEventListener('click', e => {
  const el = e.target;

  if (el.closest('#theme-toggle')) {
    const next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('hsr_theme', next); } catch (err) {}
    return;    // logo maiņa notiek ar CSS — pārzīmēt lapu nevajag
  }

  if (el.closest('#lang-btn')) { document.getElementById('lang-menu').classList.toggle('open'); return; }
  const lo = el.closest('.lang-opt');
  if (lo) { document.getElementById('lang-menu').classList.remove('open'); return; }

  const chartBtn = el.closest('#btn-open-chart');
  if (chartBtn) { openChartModal(chartBtn.dataset.chart || 'skates'); return; }

  // Pielāgotie dropdown
  const dropBtn = el.closest('.ui-dropdown-btn');
  if (dropBtn) {
    const menu = dropBtn.closest('.ui-dropdown').querySelector('.ui-dropdown-menu');
    const wasOpen = menu.classList.contains('open');
    closeAllDropdowns();
    if (!wasOpen) { menu.classList.add('open'); dropBtn.classList.add('active'); }
    return;
  }
  const dropOpt = el.closest('.ui-dropdown-opt');
  if (dropOpt) {
    if (dropOpt.dataset.disabled) return;
    const parent = dropOpt.closest('.ui-dropdown');
    const id = parent.dataset.dropdownId;
    const val = dropOpt.dataset.val;
    parent.querySelectorAll('.ui-dropdown-opt').forEach(o => o.classList.remove('active'));
    dropOpt.classList.add('active');
    parent.querySelector('.ui-dropdown-label').textContent = dropOpt.textContent;
    const hidden = parent.querySelector('input[type="hidden"]');
    if (hidden) hidden.value = val;
    closeAllDropdowns();

    if (id === 'f-sort') { S.sort = val; render(); return; }
    onProfileDropdown(id, val);
    return;
  }
  if (!el.closest('.ui-dropdown')) closeAllDropdowns();

  if (el.closest('#menu-btn')) { document.getElementById('menu-dropdown').classList.toggle('open'); return; }
  if (!el.closest('.menu-box')) document.getElementById('menu-dropdown').classList.remove('open');
  if (!el.closest('.lang-box')) document.getElementById('lang-menu').classList.remove('open');

  const modBtn = el.closest('[data-modal]');
  if (modBtn) {
    e.preventDefault();
    document.getElementById('menu-dropdown').classList.remove('open');
    document.getElementById('modal-' + modBtn.dataset.modal)?.classList.add('open');
    return;
  }

  if (el.hasAttribute('data-close-modal') || el.classList.contains('modal-overlay') || (el.closest('#modal-chart') && !el.closest('#modal-chart-img'))) {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open'));
    return;
  }

  // Vecuma grupas ātrā pārslēgšana slidu/nūju lapā
  const catBtn = el.closest('[data-cat-switch]');
  if (catBtn) {
    applyCategory(PROFILE, catBtn.dataset.type, catBtn.dataset.catSwitch);
    saveProfile();
    if (S.sort !== 'default' && S.sort !== 'price') S.sort = 'default';
    render();
    return;
  }

  const imgDot = el.closest('[data-img-switch]');
  if (imgDot) {
    e.stopPropagation();
    const target = document.getElementById(imgDot.dataset.imgSwitch);
    if (target) {
      target.style.opacity = '0';
      setTimeout(() => { setImg(target, imgDot.dataset.imgSrc); setTimeout(() => { target.style.opacity = '1'; }, 50); }, 300);
    }
    imgDot.parentNode.querySelectorAll('.card-img-dot').forEach(d => d.classList.remove('active'));
    imgDot.classList.add('active');
    return;
  }

  const openLb = el.closest('[data-open-lightbox]');
  if (openLb) { openLightbox(openLb.dataset.openLightbox, openLb.dataset.cat || 'Senior'); return; }

  const lbThumb = el.closest('[data-lb-src]');
  if (lbThumb) {
    setImg(document.getElementById('lightbox-main-img'), lbThumb.dataset.lbSrc);
    lbThumb.parentNode.querySelectorAll('.lightbox-thumb').forEach(x => x.classList.remove('active'));
    lbThumb.classList.add('active');
    return;
  }

  const sDot = el.closest('[data-slide]');
  if (sDot) { showSlide(+sDot.dataset.slide); return; }

  const pTab = el.closest('[data-ptab]');
  if (pTab && S.profileDraft) {
    readDraftNumbers();
    S.profileDraft.activeTab = pTab.dataset.ptab;
    render();
    return;
  }

  const op = el.closest('[data-open]');
  if (op) {
    e.preventDefault();
    document.getElementById('menu-dropdown').classList.remove('open');
    S.tab = op.dataset.open;
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  const tBtn = el.closest('[data-t]');
  if (tBtn) {
    e.preventDefault();
    S.tab = tBtn.dataset.t;
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  const vBtn = el.closest('[data-v]');
  if (vBtn) { S.view = vBtn.dataset.v; render(); return; }

  if (el.id === 'btn-save-profile' && S.profileDraft) {
    readDraftNumbers();
    const d = S.profileDraft;
    if (d.minSkate > d.maxSkate) [d.minSkate, d.maxSkate] = [d.maxSkate, d.minSkate];
    if (d.minStick > d.maxStick) [d.minStick, d.maxStick] = [d.maxStick, d.minStick];
    PROFILE = sanitizeProfile({ ...d });
    saveProfile();
    const toast = document.getElementById('save-toast');
    if (toast) {
      toast.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--green);flex-shrink:0;"><polyline points="20 6 9 17 4 12"/></svg> <span>Profils veiksmīgi saglabāts!</span>`;
      toast.style.display = 'inline-flex';
      clearTimeout(toast._t);
      toast._t = setTimeout(() => { toast.style.display = 'none'; }, 3000);
    }
    return;
  }

  if (el.id === 'btn-reset-profile') {
    PROFILE = sanitizeProfile({ ...DEFAULT_PROFILE });
    try { localStorage.removeItem('hsr_user_profile'); } catch (err) {}
    S.profileDraft = null;
    render();
    return;
  }

  const g = el.closest('[data-go]');
  if (g) window.scrollTo({ top: g.dataset.go === 'bottom' ? document.body.scrollHeight : 0, behavior: 'smooth' });
});

document.addEventListener('change', e => {
  if (e.target.id === 'f-stock') { S.stockOnly = e.target.checked; render(); }
});

document.addEventListener('input', e => {
  if (e.target.id !== 'site-search') return;
  S.searchQuery = e.target.value;
  if (S.tab !== 'skates' && S.tab !== 'sticks') S.tab = 'skates';
  render();
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open'));
    closeAllDropdowns();
  }
});

document.addEventListener('submit', e => {
  if (e.target.id !== 'contact-quick-form') return;
  e.preventDefault();
  const subject = encodeURIComponent('[HER Ziņojums] ' + document.getElementById('msg-subject-val').value);
  const body = encodeURIComponent(document.getElementById('msg-body').value);
  window.location.href = `mailto:hockeyeqradar@gmail.com?subject=${subject}&body=${body}`;
});

function showSlide(idx) {
  const slides = document.querySelectorAll('.hero-slide');
  const dots = document.querySelectorAll('.slider-dots .slider-dot');
  if (!slides.length) return;
  S.sliderIndex = idx % slides.length;
  slides.forEach((s, i) => s.classList.toggle('active', i === S.sliderIndex));
  dots.forEach((d, i) => d.classList.toggle('active', i === S.sliderIndex));
}

setInterval(() => { if (S.tab === 'home') showSlide(S.sliderIndex + 1); }, 15000);

// Kartīšu bilžu automātiskā rotācija
setInterval(() => {
  document.querySelectorAll('.card').forEach(card => {
    const dots = card.querySelectorAll('.card-img-dot');
    if (dots.length < 2) return;
    const active = Array.from(dots).findIndex(d => d.classList.contains('active'));
    const next = dots[(active + 1) % dots.length];
    const target = document.getElementById(next.dataset.imgSwitch);
    if (!target) return;
    target.style.opacity = '0';
    setTimeout(() => { setImg(target, next.dataset.imgSrc); setTimeout(() => { target.style.opacity = '1'; }, 80); }, 400);
    dots.forEach(d => d.classList.toggle('active', d === next));
  });
}, 10000);

/* ---------------------------------------------------------------------
   7. DATU IELĀDE
   --------------------------------------------------------------------- */
async function loadJson(path) {
  const res = await fetch(path + '?t=' + Date.now(), { cache: 'no-store' });
  if (!res.ok) throw new Error(path + ' HTTP ' + res.status);
  return res.json();
}

async function loadVersion() {
  try {
    Object.assign(VERSION, await loadJson('version.json'));
    updateStatic();
  } catch (err) {
    document.getElementById('ui-last-modified').textContent = '—';
  }
}

async function init() {
  render();
  loadVersion();
  try {
    CFG = await loadJson('config.json');
  } catch (err) {
    console.error('config.json nav ielādējams:', err);
    DATA.configError = true;
    render();
    return;
  }
  PROFILE = sanitizeProfile(PROFILE);
  render();

  try {
    const data = await loadJson('scraped_data.json');
    OFFERS = Array.isArray(data.offers) ? data.offers : [];
    if (data.updatedAt) {
      // Vecie dati bija bez laika zonas, bet tika ģenerēti UTC (GitHub serverī)
      const iso = /[zZ]|[+-]\d{2}:?\d{2}$/.test(data.updatedAt) ? data.updatedAt : data.updatedAt + 'Z';
      const d = new Date(iso);
      if (!isNaN(d.getTime())) DATA.updatedAt = d;
    }
    DATA.retailerStatus = data.retailerStatus || {};
  } catch (err) {
    console.warn('scraped_data.json nav ielādējams:', err);
  }
  DATA.loaded = true;
  render();
}

init();

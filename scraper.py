"""
Hockey Equipment Radar — veikalu skrāperis.

Visi iestatījumi (veikali, saites, modeļi, izmēri) nāk no config.json.
Šajā failā ir TIKAI nolasīšanas loģika.

Palaišana:
    python scraper.py            # parasta skenēšana -> scraped_data.json
    python scraper.py --debug    # papildus saglabā lejupielādētās lapas mapē debug/
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "scraped_data.json")
DEBUG_DIR = os.path.join(BASE_DIR, "debug")
DEBUG = "--debug" in sys.argv

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "lv,en-US;q=0.9,en;q=0.8",
}
MAX_PAGES = 10         # cik kategorijas lapas (pagination) pārlūkot maksimums
REQUEST_PAUSE = 1.0    # pauze starp pieprasījumiem, lai nenoslogotu veikalus

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

# Diagnostika: katrs pieprasījums un tā rezultāts tiek ierakstīts scraped_data.json,
# lai problēmas varētu redzēt bez GitHub Actions logiem.
DIAG = []

CATEGORIES = CONFIG["categories"]
RETAILERS = CONFIG["retailers"]
MODELS = CONFIG["models"]
SIZE_TABLES = CONFIG["sizeTables"]
CATEGORY_WORDS = CONFIG["categoryWords"]
EXCLUDE_WORDS = CONFIG["excludeWords"]


# ---------------------------------------------------------------------------
# Palīgfunkcijas
# ---------------------------------------------------------------------------

def log(msg):
    print(msg, flush=True)


def has_word(text, word):
    """Vai vārds ir tekstā kā atsevišķs vārds (nevis daļa no cita vārda)."""
    return re.search(r"(?<![a-z0-9āčēģīķļņšūž])" + re.escape(word.lower()) + r"(?![a-z0-9āčēģīķļņšūž])", text.lower()) is not None


def parse_price(text):
    if not text:
        return 0.0
    text = text.replace("\xa0", " ").replace(" ", "")
    nums = re.findall(r"\d+(?:[.,]\d{1,2})?", text)
    if not nums:
        return 0.0
    try:
        return float(nums[0].replace(",", "."))
    except ValueError:
        return 0.0


def save_debug(name, html):
    if not DEBUG:
        return
    os.makedirs(DEBUG_DIR, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", name)[:120]
    with open(os.path.join(DEBUG_DIR, safe + ".html"), "w", encoding="utf-8") as f:
        f.write(html)


def fetch(session, url, debug_name):
    """Atgriež (soup, html) vai (None, None), ja lapa nav pieejama."""
    started = time.time()
    try:
        resp = session.get(url, timeout=15)
    except requests.RequestException as e:
        log(f"    ! Savienojuma kļūda: {url} -> {e}")
        DIAG.append({"url": url, "status": "error", "error": f"{type(e).__name__}: {str(e)[:160]}",
                     "seconds": round(time.time() - started, 1)})
        return None, None
    entry = {"url": url, "status": resp.status_code, "bytes": len(resp.content),
             "seconds": round(time.time() - started, 1)}
    if resp.url != url:
        entry["finalUrl"] = resp.url
    if resp.status_code != 200:
        log(f"    ! HTTP {resp.status_code}: {url}")
        entry["server"] = resp.headers.get("server", "")
        entry["snippet"] = re.sub(r"\s+", " ", resp.text[:300])
        DIAG.append(entry)
        return None, None
    DIAG.append(entry)
    save_debug(debug_name, resp.text)
    return BeautifulSoup(resp.text, "html.parser"), resp.text


def absolute(url, base):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    m = re.match(r"(https?://[^/]+)", base)
    return (m.group(1) if m else "") + ("" if url.startswith("/") else "/") + url


def json_ld_blocks(soup):
    """Visi <script type="application/ld+json"> bloki kā Python objekti (saplacināti)."""
    out = []
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                out.append(d)
                if "@graph" in d:
                    stack.append(d["@graph"])
                if "itemListElement" in d:
                    stack.append(d["itemListElement"])
                if "item" in d and isinstance(d["item"], (dict, list)):
                    stack.append(d["item"])
    return out


# ---------------------------------------------------------------------------
# Izmēru un platumu normalizācija
# ---------------------------------------------------------------------------

def eur_to_size(eur, category, item_type):
    for row in SIZE_TABLES.get(item_type, {}).get(category, []):
        if row.get("eur") and float(row["eur"]) == float(eur):
            return row["val"]
    return None


def _num(txt):
    """'6.0' -> '6', '6.5' -> '6.5'"""
    f = float(txt)
    return str(int(f)) if f == int(f) else str(f)


def normalize_size(raw, category, item_type="skate"):
    """'6.0' -> '6', 'Y11.5' -> 'Yth 11.5', 'EUR 42' -> '7' (Senior). Atgriež None, ja nav izmērs."""
    if not raw:
        return None
    low = raw.strip().replace(",", ".").lower()

    # Bērnu izmēri: "Yth 11.5", "Y11.5", "YT 12", "Youth 12"
    m = re.search(r"\by(?:th|t|outh)?\s*(\d{1,2}(?:\.[05])?)\b", low)
    if m:
        if category != "Youth":
            return None
        n = float(m.group(1))
        return f"Yth {_num(m.group(1))}" if 6 <= n <= 13.5 else None

    # EUR izmērs: "EUR 42", "42 EU", "42.5"
    m = re.search(r"(?<![\d.])(\d{2}(?:\.5)?)(?![\d])", low)
    if m and float(m.group(1)) >= 24:
        return eur_to_size(m.group(1), category, item_type)

    # Bauer izmērs: "6", "6.0", "6.5", "10.5"
    m = re.search(r"(?<![\d.])(\d{1,2}(?:\.[05])?)(?![\d])", low)
    if m:
        n = float(m.group(1))
        if category == "Youth":
            return f"Yth {_num(m.group(1))}" if 6 <= n <= 13.5 else None
        if 1 <= n <= 13:
            return _num(m.group(1))
    return None


def normalize_fit(raw):
    """Platums -> 'FIT 1' / 'FIT 2' / 'FIT 3' (vai 'D' / 'EE' vecākiem modeļiem).
    Hokejam.lv un Hokeja Pasaule: 'FIT 1', 'FIT2', 'Fit 3'.
    Sportega: 'Konusveida' (= FIT 1), 'Regulāri' (= FIT 2), 'Plašs' (= FIT 3)."""
    if not raw:
        return None
    t = raw.strip().upper().replace("_", " ")
    m = re.search(r"FIT\s*([123])", t)
    if m:
        return f"FIT {m.group(1)}"
    low = raw.strip().lower()
    if low.startswith(("konus", "tapered", "šaur", "saur")):
        return "FIT 1"
    if low.startswith(("regul", "standart")):
        return "FIT 2"
    if low.startswith(("plaš", "plas", "plat", "wide")):
        return "FIT 3"
    if re.fullmatch(r"(EE|W)", t):
        return "EE"
    if re.fullmatch(r"(D|R)", t):
        return "D"
    return None


def classify_group(label):
    """Pēc varianta grupas nosaukuma nosaka, vai tas ir izmērs, platums, roka, flex vai liekums.
    Piem. 'Slidu izmērs', 'Slidas platums', 'Nūjas puse', 'Cietība', 'Līkums'."""
    l = (label or "").lower()
    if any(w in l for w in ["platum", "width", "fit"]):
        return "fit"
    if any(w in l for w in ["roka", "satvēr", "hand", "tvēriens", "puse", "side"]):
        return "hand"
    if "flex" in l or "cietīb" in l or "cietib" in l:
        return "flex"
    if any(w in l for w in ["liekum", "līkum", "likum", "curve", "pattern", "lāpstiņ"]):
        return "curve"
    if any(w in l for w in ["izmēr", "izmer", "size"]):
        return "size"
    return None


UNAVAILABLE_WORDS = ["nav pieejams", "nav noliktavā", "izpārdots", "out of stock", "nav pieejama"]


def is_unavailable_text(t):
    t = (t or "").lower()
    return any(w in t for w in UNAVAILABLE_WORDS)


def normalize_hand(raw):
    t = (raw or "").lower().strip()
    if re.search(r"(left|kreis)", t) or re.fullmatch(r"l\b.*", t):
        return "Left"
    if re.search(r"(right|\blab)", t) or re.fullmatch(r"r\b.*", t):
        return "Right"
    return None


def normalize_curve(raw):
    m = re.search(r"\b(P\d{2}[A-Z]?)\b", (raw or "").upper())
    return m.group(1) if m else None


def normalize_flex(raw):
    m = re.search(r"\b(\d{2,3})\b", raw or "")
    if m and 10 <= int(m.group(1)) <= 112:
        return m.group(1)
    return None


class Variants:
    """Savāc produkta lapā atrastās opcijas."""

    def __init__(self, category, item_type):
        self.category = category
        self.item_type = item_type
        self.sizes, self.fits, self.hands, self.flexes, self.curves = [], [], [], [], []

    def add(self, kind, raw):
        if not raw or is_unavailable_text(raw):
            return
        if kind == "size":
            v = normalize_size(raw, self.category, self.item_type)
            if v and v not in self.sizes:
                self.sizes.append(v)
            # dažreiz platums ir izmēra tekstā, piem. "6.0 EE" vai "6 FIT 2"
            m = re.search(r"\b(FIT\s*[123]|EE|D)\b", raw.upper())
            if m:
                self.add("fit", m.group(1))
        elif kind == "fit":
            v = normalize_fit(raw)
            if v and v not in self.fits:
                self.fits.append(v)
        elif kind == "hand":
            v = normalize_hand(raw)
            if v and v not in self.hands:
                self.hands.append(v)
        elif kind == "flex":
            v = normalize_flex(raw)
            if v and v not in self.flexes:
                self.flexes.append(v)
        elif kind == "curve":
            v = normalize_curve(raw)
            if v and v not in self.curves:
                self.curves.append(v)

    def any(self):
        return bool(self.sizes or self.hands or self.flexes or self.curves)


# ---------------------------------------------------------------------------
# Kategoriju lapas: produktu saraksts
# ---------------------------------------------------------------------------

RETAILER_LIST_SELECTORS = {
    # (kartītes selektors, nosaukuma saite, cenas elements)
    "hj": (".product-miniature, .js-product-miniature", ".product-title a", ".current-price .price, .price"),
    "hp": (".product-item-info, .product-item", "a.product-item-link", None),
    "sp": (".c-product-card, .product-card, .product, article", "a[href]", ".c-price__current, .price, [class*=price]"),
}

NEXT_PAGE_SELECTORS = 'a[rel="next"], a.next, .pagination a.next, a.action.next, li.next a, .pages-item-next a'


def products_from_selectors(soup, r_key, base_url):
    card_sel, title_sel, price_sel = RETAILER_LIST_SELECTORS.get(r_key, (None, None, None))
    out = []
    if not card_sel:
        return out
    for item in soup.select(card_sel):
        a = item.select_one(title_sel)
        if not a:
            continue
        title = a.get_text(" ", strip=True) or a.get("title", "")
        if not title:
            continue
        price = 0.0
        # Magento (hp): precīzā cena atribūtā data-price-amount
        fp = item.select_one('[data-price-type="finalPrice"]')
        if fp and fp.get("data-price-amount"):
            price = parse_price(fp.get("data-price-amount"))
        elif price_sel:
            pe = item.select_one(price_sel)
            if pe:
                price = parse_price(pe.get_text())
        out.append({"title": title, "url": absolute(a.get("href", ""), base_url), "price": price})
    return out


def products_from_jsonld(soup, base_url):
    out = []
    for d in json_ld_blocks(soup):
        if d.get("@type") in ("Product", "ListItem") and d.get("name") and d.get("url"):
            price = 0.0
            offers = d.get("offers")
            if isinstance(offers, dict):
                price = parse_price(str(offers.get("price") or offers.get("lowPrice") or ""))
            out.append({"title": d["name"], "url": absolute(d["url"], base_url), "price": price})
    return out


def products_from_links(soup, base_url, keywords):
    """Rezerves variants: jebkura saite, kuras tekstā ir modeļa atslēgvārds."""
    out = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True) or a.get("title", "")
        if title and len(title) > 6 and any(has_word(title, k) for k in keywords):
            out.append({"title": title, "url": absolute(a["href"], base_url), "price": 0.0})
    return out


def crawl_category(session, r_key, cat_url, all_keywords, debug_name):
    """Atgriež (produkti, ok). ok=False nozīmē, ka lapu neizdevās ielādēt (dati jāpatur vecie)."""
    products, url, pages, ok = [], cat_url, 0, False
    seen = set()
    while url and pages < MAX_PAGES and url not in seen:
        seen.add(url)
        soup, _ = fetch(session, url, f"{debug_name}_p{pages + 1}")
        if soup is None:
            break
        ok = True
        pages += 1
        a = products_from_selectors(soup, r_key, url)
        b = products_from_jsonld(soup, url)
        c = products_from_links(soup, url, all_keywords)
        found = a + b + c
        log(f"    lapa {pages}: {len(a)} pēc selektoriem, {len(b)} JSON-LD, {len(c)} pēc saitēm")
        DIAG[-1].update({"found": {"selectors": len(a), "jsonld": len(b), "links": len(c)}})
        products.extend(found)
        nxt = soup.select_one(NEXT_PAGE_SELECTORS)
        url = absolute(nxt.get("href"), url) if nxt and nxt.get("href") else None
        if url:
            time.sleep(REQUEST_PAUSE)
    # dublikāti pēc URL
    uniq = {}
    for p in products:
        if not p["url"]:
            continue
        cur = uniq.get(p["url"])
        if cur is None or (p["price"] > 0 and cur["price"] == 0) or (len(p["title"]) > len(cur["title"]) and p["price"] >= cur["price"]):
            uniq[p["url"]] = {**p, "price": max(p["price"], cur["price"] if cur else 0)}
    return list(uniq.values()), ok


# ---------------------------------------------------------------------------
# Produkta atbilstība modelim un vecuma grupai
# ---------------------------------------------------------------------------

def title_category(title):
    """Kurām vecuma grupām atbilst nosaukums (pēc vārdiem config.json)."""
    return {cat for cat, words in CATEGORY_WORDS.items() if any(has_word(title, w) for w in words)}


def match_product(products, model, category, url_is_shared):
    candidates = []
    for p in products:
        title = p["title"]
        haystack = title + " " + p["url"].replace("-", " ").replace("/", " ")
        if not all(has_word(haystack, k) for k in model["keywords"]):
            continue
        if any(has_word(title, w) for w in EXCLUDE_WORDS.get(model["type"], [])):
            continue
        cats = title_category(haystack)
        if cats and category not in cats:
            continue              # nosaukums skaidri norāda citu grupu
        if not cats and url_is_shared:
            continue              # kopīgā lapā bez grupas norādes nevar zināt, kam tas paredzēts
        score = (2 if category in cats else 0) + (1 if p["price"] > 0 else 0)
        candidates.append((score, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Produkta lapa: cena, pieejamība, izmēri
# ---------------------------------------------------------------------------

def parse_prestashop(soup, v):
    """Hokejam.lv (PrestaShop): katra varianta grupa atsevišķi -> izmērs netiek jaukts ar 'FIT 2'."""
    groups = soup.select(".product-variants-item, .product-variants > div")
    for g in groups:
        label_el = g.select_one(".control-label, label, span.control-label")
        kind = classify_group(label_el.get_text(" ", strip=True) if label_el else "")
        if not kind:
            # mēģina pēc select name, piem. group[3] ar data-product-attribute
            sel = g.select_one("select")
            kind = classify_group(sel.get("aria-label", "") if sel else "")
        if not kind:
            continue
        for opt in g.select("option"):
            v.add(kind, opt.get_text(" ", strip=True))
        for inp in g.select('input[type="radio"]'):
            txt = inp.get("title") or ""
            if not txt:
                lab = inp.find_parent("label") or inp.find_next("span")
                txt = lab.get_text(" ", strip=True) if lab else ""
            v.add(kind, txt)


def parse_magento(soup, v):
    """Hokeja Pasaule (Magento 2): opcijas ir JSON iekš <script type="text/x-magento-init">."""
    for s in soup.select('script[type="text/x-magento-init"]'):
        raw = s.string or s.get_text() or ""
        if "attributes" not in raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                cfg = d.get("jsonConfig") or d.get("spConfig")
                if isinstance(cfg, dict) and isinstance(cfg.get("attributes"), dict):
                    for attr in cfg["attributes"].values():
                        kind = classify_group(f"{attr.get('code', '')} {attr.get('label', '')}")
                        if not kind:
                            continue
                        for opt in attr.get("options", []):
                            # Magento neiekļauj izpārdotos variantus 'products' sarakstā
                            if opt.get("products"):
                                v.add(kind, opt.get("label", ""))
                stack.extend(d.values())
            elif isinstance(d, list):
                stack.extend(d)
    # ja lapā tomēr ir HTML swatch elementi
    for sw in soup.select(".swatch-attribute"):
        kind = classify_group(" ".join(sw.get("class", [])) + " " + (sw.get("data-attribute-code") or ""))
        if not kind:
            continue
        for o in sw.select(".swatch-option"):
            if "disabled" not in o.get("class", []):
                v.add(kind, o.get("data-option-label") or o.get_text(strip=True))


def parse_generic(soup, v):
    """Jebkuram veikalam: <select> ar nosaukumu, kas izskatās pēc izmēra/platuma."""
    for sel in soup.select("select"):
        label = " ".join(filter(None, [sel.get("name"), sel.get("id"), sel.get("aria-label")]))
        lab_el = soup.select_one(f'label[for="{sel.get("id")}"]') if sel.get("id") else None
        if lab_el:
            label += " " + lab_el.get_text(" ", strip=True)
        kind = classify_group(label)
        if not kind and "param" in label.lower():
            kind = "size"
        if not kind:
            continue
        for opt in sel.select("option"):
            txt = opt.get_text(" ", strip=True)
            if not opt.get("value") or "izvēl" in txt.lower() or opt.has_attr("disabled"):
                continue
            v.add(kind, txt)


def product_info_from_jsonld(soup):
    """(cena, noliktavā?) no JSON-LD Product. noliktavā = None, ja nav zināms."""
    price, stock = 0.0, None
    for d in json_ld_blocks(soup):
        if d.get("@type") != "Product":
            continue
        offers = d.get("offers")
        offers = offers if isinstance(offers, list) else [offers] if offers else []
        for o in offers:
            if not isinstance(o, dict):
                continue
            p = parse_price(str(o.get("price") or o.get("lowPrice") or ""))
            if p and (price == 0 or p < price):
                price = p
            av = str(o.get("availability", "")).lower()
            if "instock" in av or "limitedavailability" in av:
                stock = True
            elif ("outofstock" in av or "soldout" in av) and stock is None:
                stock = False
    return price, stock


def get_product_details(session, url, r_key, model, category, debug_name):
    soup, _ = fetch(session, url, debug_name)
    if soup is None:
        return None
    v = Variants(category, model["type"])
    if r_key == "hj":
        parse_prestashop(soup, v)
    elif r_key == "hp":
        parse_magento(soup, v)
    if not v.any():
        parse_generic(soup, v)

    price, stock = product_info_from_jsonld(soup)
    # Lai varētu pielāgot nolasīšanu: kādi <select> un variantu bloki lapā vispār ir
    DIAG[-1].update({
        "variants": {"sizes": v.sizes, "fits": v.fits, "hands": v.hands, "flexes": v.flexes, "curves": v.curves},
        "selects": [
            {"name": sel.get("name"), "id": sel.get("id"), "class": " ".join(sel.get("class", [])),
             "options": [o.get_text(" ", strip=True)[:30] for o in sel.select("option")][:8]}
            for sel in soup.select("select")
        ][:6],
    })
    if not price:
        meta = soup.select_one('meta[property="product:price:amount"], meta[itemprop="price"]')
        if meta:
            price = parse_price(meta.get("content"))
    return {"variants": v, "price": price, "stock": stock}


# ---------------------------------------------------------------------------
# Galvenā plūsma
# ---------------------------------------------------------------------------

def load_previous():
    try:
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {(o["model"], o["retailer"], o.get("category", "Senior")): o for o in data.get("offers", [])}
    except (OSError, ValueError):
        return {}


def scrape_all():
    started = datetime.now(timezone.utc)
    log(f"[{started:%Y-%m-%d %H:%M:%S} UTC] Sākas skenēšana{' (DEBUG)' if DEBUG else ''}...")
    session = requests.Session()
    session.headers.update(HEADERS)
    today = started.strftime("%Y-%m-%d")
    previous = load_previous()

    # 1) Kategoriju lapas — katru unikālo URL lejupielādē tikai vienreiz
    catalogs = {}     # url -> (produkti, ok)
    stats = {}
    pages_ok, pages_failed = {}, {}
    for r_key, r in RETAILERS.items():
        for item_type, cat_urls in r["categoryUrls"].items():
            type_keywords = [k for m in MODELS if m["type"] == item_type for k in m["keywords"]]
            if not type_keywords:
                continue
            for cat in CATEGORIES:
                url = cat_urls.get(cat)
                if not url or url in catalogs:
                    continue
                log(f"Katalogs [{r_key.upper()} · {item_type} · {cat}] {url}")
                catalogs[url] = crawl_category(session, r_key, url, type_keywords, f"{r_key}_{item_type}_{cat}")
                stats[r_key] = stats.get(r_key, 0) + len(catalogs[url][0])
                bucket = pages_ok if catalogs[url][1] else pages_failed
                bucket[r_key] = bucket.get(r_key, 0) + 1
                time.sleep(REQUEST_PAUSE)

    # 2) Katram modelim katrā grupā katrā veikalā
    offers = []
    failed_retailers = set()
    for model in MODELS:
        item_type = model["type"]
        for cat in model["categories"]:
            for r_key, r in RETAILERS.items():
                cat_urls = r["categoryUrls"].get(item_type, {})
                cat_url = cat_urls.get(cat)
                key = (model["id"], r_key, cat)
                base = {
                    "type": item_type, "category": cat, "model": model["id"], "retailer": r_key,
                    "price": 0.0, "shipping": r.get("shipping", 0.0),
                    "sizes": [], "fits": [], "stock": False, "checked": today,
                    "url": cat_url or r["url"], "status": "NOT_FOUND", "stale": False,
                }
                if item_type == "stick":
                    base.update({"hands": [], "flexes": [], "curves": []})

                if not cat_url:
                    base["status"] = "NOT_TRACKED"
                    offers.append(base)
                    continue

                products, ok = catalogs.get(cat_url, ([], False))
                if not ok:
                    # Lapa nav ielādējusies — paturam iepriekšējos datus, nevis pārrakstām ar 0
                    failed_retailers.add(r_key)
                    old = previous.get(key)
                    if old:
                        old = {**old, "stale": True}
                        offers.append(old)
                        log(f" -> PATURĒTI VECIE DATI: [{cat}] {r_key.upper()} {model['id']}")
                    else:
                        base["status"] = "ERROR"
                        offers.append(base)
                    continue

                shared = sum(1 for c in CATEGORIES if cat_urls.get(c) == cat_url) > 1
                prod = match_product(products, model, cat, shared)
                if not prod:
                    log(f" -> nav atrasts: [{cat}] {r_key.upper()} {model['id']}")
                    offers.append(base)
                    continue

                log(f" -> ATRASTS: [{cat}] {r_key.upper()} {prod['title']}")
                time.sleep(REQUEST_PAUSE)
                details = get_product_details(session, prod["url"], r_key, model, cat,
                                              f"{r_key}_{model['id']}_{cat}_product")
                price = prod["price"]
                v, page_stock = None, None
                if details:
                    v = details["variants"]
                    price = price or details["price"]
                    page_stock = details["stock"]
                has_options = bool(v and v.any())
                # Noliktava: ja lapa to skaidri pasaka (JSON-LD) — ticam tai, citādi pēc variantiem/cenas
                stock = page_stock if page_stock is not None else (has_options or price > 0)

                base.update({
                    "title": prod["title"],
                    "url": prod["url"],
                    "price": round(price, 2),
                    "stock": bool(stock and price > 0),
                    "sizes": v.sizes if v else [],
                    "fits": v.fits if v else [],
                    "status": "VERIFIED" if (price > 0 and has_options) else ("FOUND" if price > 0 else "NOT_FOUND"),
                })
                if item_type == "stick" and v:
                    base.update({"hands": v.hands, "flexes": v.flexes, "curves": v.curves})
                offers.append(base)
                log(f"    cena {price} € · izmēri {base['sizes']} · platumi {base['fits']}")

    # 3) Drošības pārbaude: ja NEVIENS veikals neatbildēja, neko nepārrakstām
    if stats and all(n == 0 for n in stats.values()) and len(failed_retailers) == len(RETAILERS):
        log("KĻŪDA: neviens veikals neatbildēja. scraped_data.json NETIEK mainīts.")
        sys.exit(1)

    payload = {
        "updatedAt": started.isoformat(timespec="seconds"),
        # ok = viss nolasīts, partial = daļa lapu neatbildēja, error = neviena lapa, empty = lapas ielādējās, bet produkti netika atrasti
        "retailerStatus": {
            r_key: ("error" if pages_failed.get(r_key) and not pages_ok.get(r_key)
                    else "partial" if pages_failed.get(r_key)
                    else "empty" if stats.get(r_key, 0) == 0 else "ok")
            for r_key in RETAILERS
        },
        "offers": offers,
        "diagnostics": DIAG,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    log("")
    log("KOPSAVILKUMS:")
    for r_key in RETAILERS:
        found = sum(1 for o in offers if o["retailer"] == r_key and o["status"] in ("VERIFIED", "FOUND"))
        log(f"  {RETAILERS[r_key]['name']:<16} produkti katalogā: {stats.get(r_key, 0):>4} · atrasti modeļi: {found} · statuss: {payload['retailerStatus'][r_key]}")
    log(f"Gatavs! {len(offers)} ieraksti -> scraped_data.json")


if __name__ == "__main__":
    scrape_all()

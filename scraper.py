import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'lv,en-US;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
}

# Tabula Sportega EUR izmēru konvertēšanai uz Bauer Youth izmēriem
EUR_TO_YOUTH = {
    "24": "Yth 6",
    "25": "Yth 7",
    "26": "Yth 8",
    "27": "Yth 9",
    "28": "Yth 10",
    "29": "Yth 10.5",
    "30": "Yth 11",
    "30.5": "Yth 11.5",
    "31": "Yth 12",
    "32": "Yth 12.5",
    "32.5": "Yth 13",
    "33": "Yth 13.5"
}

# Veikalu bāzes meklēšanas URL un noklusētās sadaļas
RETAILER_CONFIG = {
    "hj": {
        "name": "Hokejam.lv",
        "search_url": "https://www.hokejam.lv/lv/meklesana?search={query}",
        "default_url": "https://www.hokejam.lv/",
        "youth_fallback": "https://www.hokejam.lv/lv/51-bernu-hokeja-slidas",
        "shipping": 0.0
    },
    "hp": {
        "name": "Hokeja Pasaule",
        "search_url": "https://hokejapasaule.lv/catalogsearch/result/?q={query}",
        "default_url": "https://hokejapasaule.lv/",
        "youth_fallback": "https://hokejapasaule.lv/lv_lv/slidas/hokeja-slidas/slidas-berniem",
        "shipping": 3.5
    },
    "sp": {
        "name": "Sportega",
        "search_url": "https://www.sportega.lv/search?q={query}",
        "default_url": "https://www.sportega.lv/",
        "youth_fallback": "https://www.sportega.lv/hokeja-ekipejums/berns-youth/c233",
        "shipping": 4.0
    }
}

# MODEĻU DEFINĪCIJAS:
# Te pietiek norādīt tikai modeļa kodu un atslēgvārdus!
MODELS = [
    {
        "id": "bauer-supreme-m40",
        "type": "skate",
        "brand": "Bauer",
        "keywords": ["Supreme", "M40"],
        "categories": ["Senior", "Youth"], # Eksistē abās grupās
        # Tiešās saites kalpo kā garantēts ātrais ceļš, ja veikala meklētājs ir lēns vai bloķēts:
        "direct_urls": {
            "Youth": {
                "hj": "https://www.hokejam.lv/lv/bernu-hokeja-slidas/5729-bauer-supreme-m40-s24-bernu-hokeja-slidas",
                "hp": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s24-m40-youth-hokeja-slidas",
                "sp": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-m40-youth-d-standarta-kaja-eur-26/d1438563"
            },
            "Senior": {
                "hj": "https://www.hokejam.lv/lv/pieauguso-hokeja-slidas/4507-bauer-supreme-m40-pieauguso-hokeja-slidas",
                "hp": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s24-m40-senior-hokeja-slidas",
                "sp": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-m40-senior/d1438036"
            }
        }
    },
    {
        "id": "bauer-vapor-fly40",
        "type": "skate",
        "brand": "Bauer",
        "keywords": ["Vapor", "FLY40"],
        "categories": ["Senior", "Youth"],
        "direct_urls": {
            "Youth": {
                "hp": "https://hokejapasaule.lv/lv_lv/bauer-vapor-s25-fly40-youth-hokeja-slidas",
                "sp": "https://www.sportega.lv/hokeja-slidas-bauer-vapor-fly40-youth-d-standarta-kaja-eur-26/d1503208"
            },
            "Senior": {
                "hp": "https://hokejapasaule.lv/lv_lv/bauer-vapor-s25-fly40-senior-hokeja-slidas",
                "sp": "https://www.sportega.lv/hokeja-slidas-bauer-vapor-fly40-senior/d1502757"
            }
        }
    },
    {
        "id": "bauer-supreme-f40",
        "type": "skate",
        "brand": "Bauer",
        "keywords": ["Supreme", "F40"],
        "categories": ["Senior"], # F40 bērniem netiek ražots, tāpēc Youth te NAV!
        "direct_urls": {
            "Senior": {
                "hj": "https://www.hokejam.lv/lv/pieauguso-hokeja-slidas/5455-bauer-supreme-f40-s26-pieauguso-hokeja-slidas",
                "hp": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s26-f40-senior-hokeja-slidas",
                "sp": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-f40-senior/d1583973"
            }
        }
    }
]

def check_category_match(title, category):
    """Pārbauda, vai atrastā preces virsraksts atbilst meklētajai vecuma grupai."""
    title_low = title.lower()
    if category == "Youth":
        return any(k in title_low for k in ["bērnu", "youth", "yth"])
    elif category == "Junior":
        return any(k in title_low for k in ["junioru", "junior", "jr"])
    elif category == "Intermediate":
        return any(k in title_low for k in ["intermediate", "int"])
    elif category == "Senior":
        # Ja nav bērnu un nav junioru, bet ir pieaugušo vai senior
        if any(k in title_low for k in ["bērnu", "youth", "junior", "junioru", "yth", "jr"]):
            return False
        return any(k in title_low for k in ["pieaugušo", "senior", "sr"]) or True
    return False

def discover_product_url(retailer_key, model, category, session):
    """Automātiski atrod preci veikala meklētājā pēc atslēgvārdiem."""
    cfg = RETAILER_CONFIG[retailer_key]
    query = "+".join(model["keywords"])
    if category == "Youth":
        query += "+bernu"
    elif category == "Senior":
        query += "+senior"

    search_url = cfg["search_url"].format(query=query)
    try:
        resp = session.get(search_url, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')

        if retailer_key == "hj":
            items = soup.select('.product-miniature, .js-product-miniature')
            for it in items:
                title_el = it.select_one('.product-title a')
                if title_el:
                    title = title_el.get_text().strip()
                    if all(k.lower() in title.lower() for k in model["keywords"]) and check_category_match(title, category):
                        return title_el['href']

        elif retailer_key == "hp":
            items = soup.select('.product-item-info')
            for it in items:
                title_el = it.select_one('a.product-item-link')
                if title_el:
                    title = title_el.get_text().strip()
                    if all(k.lower() in title.lower() for k in model["keywords"]) and check_category_match(title, category):
                        return title_el['href']

        elif retailer_key == "sp":
            items = soup.select('.c-product-card, article')
            for it in items:
                title_el = it.select_one('a[href*="/d"]')
                if title_el:
                    title = title_el.get_text().strip()
                    if all(k.lower() in title.lower() for k in model["keywords"]) and check_category_match(title, category):
                        link = title_el['href']
                        if not link.startswith('http'):
                            link = "https://www.sportega.lv" + link
                        return link
    except Exception as e:
        print(f"[{retailer_key.upper()}] Meklēšanas kļūda vaicājumam '{query}': {e}")

    return None

def extract_real_price(soup, retailer_key):
    """Nolasa reālo gala cenu ar visām atlaidēm."""
    try:
        if retailer_key == 'hj':
            curr = soup.select_one('.current-price [itemprop="price"], .current-price-value, .product-price')
            if curr:
                clean = re.sub(r'[^\d.,]', '', curr.get_text()).replace(',', '.')
                return float(clean)

        elif retailer_key == 'hp':
            spec = soup.select_one('.special-price .price, [data-price-type="finalPrice"] .price')
            if spec:
                clean = re.sub(r'[^\d.,]', '', spec.get_text()).replace(',', '.')
                return float(clean)
            final_p = soup.select_one('.price-final_price .price, .product-info-price .price')
            if final_p:
                clean = re.sub(r'[^\d.,]', '', final_p.get_text()).replace(',', '.')
                return float(clean)

        elif retailer_key == 'sp':
            p_elem = soup.select_one('.c-price__current, [data-price-amount], .price-wrapper .price')
            if p_elem:
                if p_elem.has_attr('data-price-amount'):
                    return float(p_elem['data-price-amount'])
                clean = re.sub(r'[^\d.,]', '', p_elem.get_text()).replace(',', '.')
                return float(clean)

        # Rezerves meta tags
        meta_p = soup.find('meta', attrs={'property': 'product:price:amount'}) or soup.find('meta', attrs={'itemprop': 'price'})
        if meta_p and meta_p.get('content'):
            return float(meta_p['content'].replace(',', '.'))
    except Exception:
        pass
    return 0.0

def extract_real_sizes(soup, retailer_key, category):
    """Nolasa tikai faktiski noliktavā esošos izmērus."""
    sizes = []
    try:
        if retailer_key == 'hj':
            options = soup.select('.form-control-select option, .input-container input[type="radio"]')
            for opt in options:
                txt = opt.get_text().strip() if opt.name == 'option' else opt.get('title', '')
                if not txt:
                    continue
                match_yth = re.search(r'Y\s*([\d.]+)', txt, re.IGNORECASE)
                if match_yth:
                    sizes.append(f"Yth {match_yth.group(1)}")
                elif category == 'Senior':
                    match_sr = re.search(r'\b([6-9]|1[0-3])(?:\.5)?\b', txt)
                    if match_sr:
                        sizes.append(match_sr.group(0))

        elif retailer_key == 'hp':
            swatches = soup.select('.swatch-attribute.size .swatch-option, .swatch-attribute.boot_size .swatch-option')
            for sw in swatches:
                # Ja ir klase 'disabled', izmērs nav noliktavā!
                if 'disabled' in sw.get('class', []):
                    continue
                txt = sw.get_text().strip()
                if txt:
                    if category == 'Youth':
                        sizes.append(f"Yth {txt}" if not txt.lower().startswith('yth') else txt)
                    else:
                        sizes.append(txt)

        elif retailer_key == 'sp':
            options = soup.select('select[name*="parameter"] option, .c-param-select option')
            for opt in options:
                txt = opt.get_text().strip()
                if 'izvēlieties' in txt.lower():
                    continue
                eur_match = re.search(r'EUR\s*([\d.]+)', txt, re.IGNORECASE)
                if eur_match:
                    eur_val = eur_match.group(1)
                    if category == 'Youth' and eur_val in EUR_TO_YOUTH:
                        sizes.append(EUR_TO_YOUTH[eur_val])
                    elif category != 'Youth':
                        sizes.append(eur_val)
    except Exception as e:
        print(f"Kļūda lasot izmērus: {e}")

    # Ja atsevišķa variāciju selektora nav, pārbauda virsrakstu (viena izmēra prece)
    if not sizes and category == 'Youth':
        title = soup.get_text()
        yth_matches = re.findall(r'Yth\s*([\d.]+)|EUR\s*(\d{2})', title, re.IGNORECASE)
        for y, eur in yth_matches:
            if y:
                sizes.append(f"Yth {y}")
            elif eur and eur in EUR_TO_YOUTH:
                sizes.append(EUR_TO_YOUTH[eur])

    return list(dict.fromkeys(sizes))

def scrape_url(url, retailer_key, category, session):
    """Atver atrasto konkrēto lapu un nolasa reālos datus."""
    try:
        resp = session.get(url, timeout=12)
        if resp.status_code != 200:
            return 0.0, False, [], url, "UNVERIFIED"

        soup = BeautifulSoup(resp.text, 'html.parser')
        price = extract_real_price(soup, retailer_key)

        # Groza pogas un noliktavas pārbaude
        btn = soup.select_one('#product-addtocart-button, .add-to-cart, button[data-button-action="add-to-cart"], .c-product-detail__btn-buy')
        is_in_stock = bool(btn and not btn.has_attr('disabled'))

        if not btn and price > 0:
            txt_low = resp.text.lower()
            if 'ir noliktavā' in txt_low or 'pieejams' in txt_low:
                is_in_stock = True

        sizes = extract_real_sizes(soup, retailer_key, category)
        status = "VERIFIED" if (price > 0 and is_in_stock) else "UNVERIFIED"
        return price, is_in_stock, sizes, url, status

    except Exception as e:
        print(f"Kļūda atverot {url}: {e}")
        return 0.0, False, [], url, "UNVERIFIED"

def scrape_all():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sākas hokeja inventāra skenēšana...")
    session = requests.Session()
    session.headers.update(HEADERS)
    today_str = datetime.now().strftime("%Y-%m-%d")

    all_offers = []

    for model in MODELS:
        for cat in model["categories"]:
            for r_key in ["hj", "hp", "sp"]:
                print(f"Pārbauda [{cat.upper()}] {r_key.upper()} -> {model['brand']} {model['id']}...")

                # 1. Pārbauda, vai ir iepriekš fiksēta tiešā saite
                target_url = model.get("direct_urls", {}).get(cat, {}).get(r_key)

                # 2. Ja tiešās saites nav, izmanto Viedo meklētāju
                if not target_url:
                    target_url = discover_product_url(r_key, model, cat, session)

                # 3. Ja prece veikalā nav atrasta vispār
                if not target_url:
                    fallback_link = RETAILER_CONFIG[r_key]["youth_fallback"] if cat == "Youth" else RETAILER_CONFIG[r_key]["default_url"]
                    print(f" -> Nav atrasts veikalā. Atzīmēts kā nepieejams.")
                    all_offers.append({
                        "type": model["type"],
                        "category": cat,
                        "model": model["id"],
                        "retailer": r_key,
                        "price": 0.0,
                        "shipping": RETAILER_CONFIG[r_key]["shipping"],
                        "sizes": [],
                        "fits": ["FIT 2", "Regular"],
                        "stock": False,
                        "checked": today_str,
                        "url": fallback_link,
                        "status": "UNVERIFIED"
                    })
                    continue

                # 4. Ja saite atrasta, nolasa cenu un izmērus
                price, stock, sizes, final_url, status = scrape_url(target_url, r_key, cat, session)
                time.sleep(1)

                print(f" -> Rezultāts: Cena = €{price}, Noliktavā = {stock}, Izmēri = {sizes}, Statuss = {status}")

                all_offers.append({
                    "type": model["type"],
                    "category": cat,
                    "model": model["id"],
                    "retailer": r_key,
                    "price": price,
                    "shipping": RETAILER_CONFIG[r_key]["shipping"],
                    "sizes": sizes,
                    "fits": ["FIT 2", "Regular"],
                    "stock": stock,
                    "checked": today_str,
                    "url": final_url,
                    "status": status
                })

    payload = {
        "updatedAt": datetime.now().isoformat(),
        "offers": all_offers
    }

    with open('scraped_data.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Skenēšana pabeigta! scraped_data.json saglabāts ar {len(all_offers)} piedāvājumiem.")

if __name__ == '__main__':
    scrape_all()

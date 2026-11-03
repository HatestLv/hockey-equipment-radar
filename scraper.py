import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'lv-LV,lv;q=0.9,en-US;q=0.8,en;q=0.7',
    'Sec-Ch-Ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    'Upgrade-Insecure-Requests': '1'
}

TARGET_SKATES = [
    # --- SENIOR ---
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-vapor-fly40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-vapor-s25-fly40-senior-hokeja-slidas",
        "default_sizes": ["7", "7.5"],
        "default_fits": ["FIT 2"],
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-vapor-fly40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/meklesana?search=FLY40",
        "default_sizes": ["7", "7.5"],
        "default_fits": ["FIT 2"],
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-vapor-fly40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-vapor-fly40-senior/d1502757",
        "default_sizes": ["7", "7.5"],
        "default_fits": ["FIT 2"],
        "shipping": 4.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-f40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s26-f40-senior-hokeja-slidas",
        "default_sizes": ["7", "7.5"],
        "default_fits": ["FIT 2"],
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-f40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/pieauguso-hokeja-slidas/5455-bauer-supreme-f40-s26-pieauguso-hokeja-slidas",
        "default_sizes": ["7", "7.5"],
        "default_fits": ["FIT 2"],
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-f40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-f40-senior/d1583973",
        "default_sizes": ["7", "7.5"],
        "default_fits": ["FIT 2"],
        "shipping": 4.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-m40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s24-m40-senior-hokeja-slidas",
        "default_sizes": ["7", "7.5"],
        "default_fits": ["FIT 2"],
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-m40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/pieauguso-hokeja-slidas/4507-bauer-supreme-m40-pieauguso-hokeja-slidas",
        "default_sizes": ["7", "7.5"],
        "default_fits": ["FIT 2"],
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-m40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-m40-senior/d1438036",
        "default_sizes": ["7", "7.5", "8"],
        "default_fits": ["FIT 2"],
        "shipping": 4.0
    },

    # --- YOUTH (BĒRNU) ---
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-vapor-fly40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/slidas/hokeja-slidas/slidas-berniem",
        "keywords": ["fly40", "vapor"],
        "default_sizes": ["Yth 8", "Yth 9", "Yth 10", "Yth 11", "Yth 12", "Yth 13"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-vapor-fly40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/51-bernu-hokeja-slidas",
        "keywords": ["fly40", "vapor"],
        "default_sizes": ["Yth 9", "Yth 10", "Yth 11", "Yth 12"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-vapor-fly40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-ekipejums/berns-youth/c233",
        "keywords": ["fly40", "vapor"],
        "default_sizes": ["Yth 8", "Yth 9", "Yth 10", "Yth 11", "Yth 12", "Yth 13"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 4.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-f40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/slidas/hokeja-slidas/slidas-berniem",
        "keywords": ["f40", "supreme"],
        "default_sizes": ["Yth 8", "Yth 9", "Yth 10", "Yth 11", "Yth 12"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-f40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/51-bernu-hokeja-slidas",
        "keywords": ["f40", "supreme"],
        "default_sizes": ["Yth 10", "Yth 11", "Yth 12"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-f40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-ekipejums/berns-youth/c233",
        "keywords": ["f40", "supreme"],
        "default_sizes": ["Yth 8", "Yth 9", "Yth 10", "Yth 11", "Yth 12"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 4.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-m40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/slidas/hokeja-slidas/slidas-berniem",
        "keywords": ["m40", "supreme"],
        "default_sizes": ["Yth 8", "Yth 9", "Yth 10", "Yth 11"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-m40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/51-bernu-hokeja-slidas",
        "keywords": ["m40", "supreme"],
        "default_sizes": ["Yth 8", "Yth 9", "Yth 10"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-m40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-ekipejums/berns-youth/c233",
        "keywords": ["m40", "supreme"],
        "default_sizes": ["Yth 8", "Yth 9", "Yth 10", "Yth 11", "Yth 12"],
        "default_fits": ["FIT 2", "Regular"],
        "shipping": 4.0
    }
]

TARGET_STICKS = [
    {
        "type": "stick",
        "category": "Senior",
        "model": "bauer-supreme-fuse-s26",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s26-fuse-grip-senior-hokeja-nuja",
        "shipping": 3.5,
        "hands": ["Left", "Right"],
        "curves": ["P92", "P28"],
        "flexes": ["77", "87"]
    },
    {
        "type": "stick",
        "category": "Senior",
        "model": "bauer-supreme-fuse-s26",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/pieauguso-kompozitu-hokeja-nujas/5726-20674-bauer-supreme-fuse-s26-senior-composite-hockey-stick#/27-virsma-grip/31-puse-kreisa_puse/43-liekums-p92/58-cietiba-65",
        "shipping": 0.0,
        "hands": ["Left", "Right"],
        "curves": ["P92", "P28"],
        "flexes": ["77", "87"]
    },
    {
        "type": "stick",
        "category": "Senior",
        "model": "bauer-supreme-fuse-s26",
        "retailer": "sp",
        "url": "https://www.sportega.lv/kompozitmateriala-hokeja-nuja-bauer-supreme-fuse-senior/d1585348",
        "shipping": 4.0,
        "hands": ["Left", "Right"],
        "curves": ["P92", "P28"],
        "flexes": ["77", "87"]
    }
]

def extract_price(html, soup):
    # 1. JSON-LD strukturētie dati
    for s in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE):
        try:
            raw = json.loads(s.group(1).strip())
            def find_p(obj):
                if isinstance(obj, list):
                    for e in obj:
                        r = find_p(e)
                        if r: return r
                elif isinstance(obj, dict):
                    if '@graph' in obj:
                        return find_p(obj['@graph'])
                    if obj.get('@type') in ['Product', 'IndividualProduct'] or 'offers' in obj:
                        offs = obj.get('offers', {})
                        if isinstance(offs, list) and offs: offs = offs[0]
                        if isinstance(offs, dict):
                            p = offs.get('price') or offs.get('lowPrice')
                            if p:
                                try:
                                    return float(str(p).replace(',', '.'))
                                except:
                                    pass
                return None
            res = find_p(raw)
            if res and 30 <= res <= 3000:
                return res
        except:
            continue

    # 2. Meta tagi
    for attr in [
        {'property': 'product:price:amount'},
        {'itemprop': 'price'},
        {'name': 'twitter:data1'},
        {'property': 'og:price:amount'}
    ]:
        meta = soup.find('meta', attrs=attr)
        if meta and meta.get('content'):
            cleaned = re.sub(r'[^\d.,]', '', meta['content']).replace(',', '.')
            try:
                val = float(cleaned)
                if 30 <= val <= 3000:
                    return val
            except:
                pass

    # 3. Specifiskie veikalu HTML selektori
    price_selectors = [
        '[data-price-amount]',
        '.c-price__current',
        '.price-wrapper .price',
        '.current-price-value',
        '.current-price [itemprop="price"]',
        '.product-price',
        '.price-final_price .price',
        'span.price'
    ]

    for sel in price_selectors:
        p_el = soup.select_one(sel)
        if p_el:
            if p_el.has_attr('data-price-amount'):
                try:
                    val = float(p_el['data-price-amount'])
                    if 30 <= val <= 3000: return val
                except:
                    pass
            txt = p_el.get_text()
            nums = re.findall(r'\d+(?:[.,]\d{2})?', txt)
            if nums:
                try:
                    val = float(nums[0].replace(',', '.'))
                    if 30 <= val <= 3000: return val
                except:
                    pass

    # 4. Fallback Regex meklēšana
    p_matches = re.findall(r'(\d{2,4}(?:[.,]\d{2})?)\s*(?:€|EUR)', html)
    valid = []
    for p in p_matches:
        try:
            v = float(p.replace(' ', '').replace(',', '.'))
            if 30 <= v <= 3000:
                valid.append(v)
        except:
            pass
    if valid:
        return min(valid)

    return None

def check_stock(html, soup):
    btn = soup.select_one('#product-addtocart-button, .add-to-cart, button[data-button-action="add-to-cart"], .btn-cart, .add_to_cart_button')
    if btn:
        if btn.has_attr('disabled') or 'disabled' in btn.get('class', []):
            return False
        return True

    avail_el = soup.select_one('[itemprop="availability"], .product-availability, .stock.available, .stock.unavailable')
    if avail_el:
        txt = (avail_el.get('href', '') + ' ' + avail_el.get_text()).lower()
        if 'instock' in txt or 'in_stock' in txt or 'ir noliktavā' in txt or 'pieejams' in txt:
            return True
        if 'outofstock' in txt or 'out_of_stock' in txt or 'nav noliktavā' in txt or 'izpārdots' in txt:
            return False

    html_low = html.lower()
    if 'prece nav pieejama' in html_low or 'prece ir izpārdota' in html_low:
        return False
    if 'ir noliktavā' in html_low or 'pieejams veikalā' in html_low:
        return True

    return False

def scrape_category_listing(cat_url, keywords, session):
    """Meklē konkrēto modeli bērnu/youth sadaļā pēc atslēgvārdiem"""
    try:
        resp = session.get(cat_url, timeout=12)
        if resp.status_code != 200:
            return None, False, cat_url
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Meklējam visas preču kartītes sarakstā
        cards = soup.select('.product-item, .product-miniature, .c-product-card, .product-box, article')
        for card in cards:
            text = card.get_text().lower()
            if any(k.lower() in text for k in keywords):
                # Atrasts modelis šajā kategorijā
                link_el = card.select_one('a[href]')
                prod_url = link_el['href'] if link_el else cat_url
                
                # Izvelk cenu no kartītes
                p_text = card.select_one('.price, .c-price__current, [itemprop="price"]')
                price = None
                if p_text:
                    nums = re.findall(r'\d+(?:[.,]\d{2})?', p_text.get_text())
                    if nums:
                        price = float(nums[0].replace(',', '.'))
                
                stock = True
                if 'izpārdots' in text or 'out of stock' in text or 'nav noliktavā' in text:
                    stock = False
                
                if price and 30 <= price <= 400:
                    return price, stock, prod_url
        
        return None, False, cat_url
    except Exception as e:
        print(f"Kļūda skenējot kategoriju {cat_url}: {e}")
        return None, False, cat_url

def scrape_url(url, session):
    try:
        resp = session.get(url, timeout=12)
        if resp.status_code != 200:
            return None, False
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        price = extract_price(html, soup)
        stock = check_stock(html, soup) if (price and price > 0) else False
        return price, stock
    except Exception as e:
        print(f"Kļūda skenējot {url}: {e}")
        return None, False

def scrape_all():
    print("Sākas hokeja inventāra cenu skenēšana (Senior & Youth)...")
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_targets = TARGET_SKATES + TARGET_STICKS
    updated_offers = []

    for t in all_targets:
        cat = t.get("category", "Senior")
        print(f"Pārbauda [{cat.upper()}] [{t['type'].upper()}]: {t['retailer'].upper()} -> {t['model']}")
        
        # Ja ir kategorijas URL ar atslēgvārdiem (Bērnu/Youth meklēšanai)
        if "keywords" in t:
            price, stock, item_url = scrape_category_listing(t["url"], t["keywords"], session)
        else:
            price, stock = scrape_url(t["url"], session)
            item_url = t["url"]
        
        time.sleep(1)

        status = 'VERIFIED' if (price and stock) else 'UNVERIFIED'
        print(f" -> Rezultāts: Cena = {price}, Noliktavā = {stock}, Statuss = {status}")

        offer = {
            "type": t["type"],
            "category": cat,
            "model": t["model"],
            "retailer": t["retailer"],
            "price": float(price) if price else 0.0,
            "oldPrice": None,
            "shipping": t["shipping"],
            "stock": bool(stock),
            "checked": datetime.now().strftime("%Y-%m-%d"),
            "url": item_url,
            "status": status
        }

        if t["type"] == "skate":
            offer["sizes"] = t.get("default_sizes", [])
            offer["fits"] = t.get("default_fits", [])
        elif t["type"] == "stick":
            offer["hands"] = t.get("hands", [])
            offer["curves"] = t.get("curves", [])
            offer["flexes"] = t.get("flexes", [])

        updated_offers.append(offer)

    payload = {
        "updatedAt": datetime.now().isoformat(),
        "offers": updated_offers
    }

    with open('scraped_data.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("Skenēšana pabeigta un scraped_data.json veiksmīgi atjaunināts ar visām vecuma grupām.")

if __name__ == '__main__':
    scrape_all()

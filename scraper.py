import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'lv,en-US;q=0.9,en;q=0.8'
}

EUR_TO_YOUTH = {
    "24": "Yth 6", "25": "Yth 7", "26": "Yth 8", "27": "Yth 9",
    "28": "Yth 10", "29": "Yth 10.5", "30": "Yth 11", "30.5": "Yth 11.5",
    "31": "Yth 12", "32": "Yth 12.5", "32.5": "Yth 13", "33": "Yth 13.5"
}

# Veikalu bāzes kategoriju saites katrai vecuma grupai
CATEGORY_URLS = {
    "Youth": {
        "hj": "https://www.hokejam.lv/lv/51-bernu-hokeja-slidas",
        "hp": "https://hokejapasaule.lv/lv_lv/slidas/hokeja-slidas/slidas-berniem",
        "sp": "https://www.sportega.lv/hokeja-ekipejums/berns-youth/c233"
    },
    "Junior": {
        "hj": "https://www.hokejam.lv/lv/50-junioru-hokeja-slidas",
        "hp": "https://hokejapasaule.lv/lv_lv/slidas/hokeja-slidas/slidas-junioriem",
        "sp": "https://www.sportega.lv/hokeja-ekipejums/juniors/c2559"
    },
    "Intermediate": {
        "hj": "https://www.hokejam.lv/lv/241-pusaudzu-hokeja-slidas",
        "hp": "https://hokejapasaule.lv/lv_lv/slidas/hokeja-slidas/slidas-jauniesiem",
        "sp": "https://www.sportega.lv/hokeja-ekipejums/jauniesi/c2558"
    },
    "Senior": {
        "hj": "https://www.hokejam.lv/lv/48-pieauguso-hokeja-slidas",
        "hp": "https://hokejapasaule.lv/lv_lv/slidas/hokeja-slidas/slidas-pieaugusajiem",
        "sp": "https://www.sportega.lv/hokeja-slidas/c354"
    }
}

SHIPPING_RATES = {"hj": 0.0, "hp": 3.5, "sp": 4.0}

# Modeļu saraksts
MODELS = [
    {
        "id": "bauer-supreme-m40",
        "type": "skate",
        "brand": "Bauer",
        "keywords": ["m40"],
        "categories": ["Senior", "Intermediate", "Junior", "Youth"],
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
        "keywords": ["fly40"],
        "categories": ["Senior", "Intermediate", "Junior", "Youth"],
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
        "keywords": ["f40"],
        "categories": ["Senior", "Intermediate", "Junior"],
        "direct_urls": {
            "Senior": {
                "hj": "https://www.hokejam.lv/lv/pieauguso-hokeja-slidas/5455-bauer-supreme-f40-s26-pieauguso-hokeja-slidas",
                "hp": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s26-f40-senior-hokeja-slidas",
                "sp": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-f40-senior/d1583973"
            }
        }
    },
    {
        "id": "bauer-supreme-fuse-s26",
        "type": "stick",
        "brand": "Bauer",
        "keywords": ["fuse"],
        "categories": ["Senior"],
        "direct_urls": {
            "Senior": {
                "hp": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s26-fuse-grip-senior-hokeja-nuja",
                "hj": "https://www.hokejam.lv/lv/pieauguso-kompozitu-hokeja-nujas/5726-20674-bauer-supreme-fuse-s26-senior-composite-hockey-stick#/27-virsma-grip/31-puse-kreisa_puse/43-liekums-p92/58-cietiba-65",
                "sp": "https://www.sportega.lv/kompozitmateriala-hokeja-nuja-bauer-supreme-fuse-senior/d1585348"
            }
        }
    }
]

def crawl_category(retailer_key, cat_url, session):
    """Nolasa produktus no kategorijas lapas, ja tiešais links nav fiksēts."""
    products = []
    try:
        resp = session.get(cat_url, timeout=12)
        if resp.status_code != 200:
            return products
        soup = BeautifulSoup(resp.text, 'html.parser')

        if retailer_key == "hj":
            for item in soup.select('.product-miniature, .js-product-miniature'):
                title_el = item.select_one('.product-title a')
                price_el = item.select_one('.price, .current-price')
                if title_el:
                    link = title_el.get('href', '')
                    title = title_el.get_text().strip()
                    price = 0.0
                    if price_el:
                        nums = re.findall(r'\d+(?:[.,]\d+)?', price_el.get_text().replace(' ', ''))
                        if nums: price = float(nums[0].replace(',', '.'))
                    products.append({"title": title, "url": link, "price": price})

        elif retailer_key == "hp":
            for item in soup.select('.product-item-info'):
                title_el = item.select_one('a.product-item-link')
                price_el = item.select_one('.price-wrapper .price, .special-price .price')
                if title_el:
                    link = title_el.get('href', '')
                    title = title_el.get_text().strip()
                    price = 0.0
                    if price_el:
                        nums = re.findall(r'\d+(?:[.,]\d+)?', price_el.get_text().replace(' ', ''))
                        if nums: price = float(nums[0].replace(',', '.'))
                    products.append({"title": title, "url": link, "price": price})

        elif retailer_key == "sp":
            for item in soup.select('.c-product-card, article'):
                title_el = item.select_one('a[href*="/d"]')
                price_el = item.select_one('.c-price__current, .price')
                if title_el:
                    link = title_el.get('href', '')
                    if not link.startswith('http'):
                        link = "https://www.sportega.lv" + link
                    title = title_el.get_text().strip()
                    price = 0.0
                    if price_el:
                        nums = re.findall(r'\d+(?:[.,]\d+)?', price_el.get_text().replace(' ', ''))
                        if nums: price = float(nums[0].replace(',', '.'))
                    products.append({"title": title, "url": link, "price": price})
    except Exception as e:
        print(f"Kļūda skenējot {retailer_key} kategoriju {cat_url}: {e}")

    return products

def get_product_details(product_url, retailer_key, category, session):
    """Atver atrasto konkrēto lapu un nolasa reālo cenu un noliktavā esošos izmērus."""
    sizes = []
    price = 0.0
    is_in_stock = False

    try:
        resp = session.get(product_url, timeout=12)
        if resp.status_code != 200:
            return 0.0, False, sizes
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 1. CENAS NOTEIKŠANA
        if retailer_key == 'hj':
            curr = soup.select_one('.current-price [itemprop="price"], .current-price-value, .product-price')
            if curr:
                nums = re.findall(r'\d+(?:[.,]\d+)?', curr.get_text().replace(' ', ''))
                if nums: price = float(nums[0].replace(',', '.'))
        elif retailer_key == 'hp':
            spec = soup.select_one('.special-price .price, [data-price-type="finalPrice"] .price, .product-info-price .price')
            if spec:
                nums = re.findall(r'\d+(?:[.,]\d+)?', spec.get_text().replace(' ', ''))
                if nums: price = float(nums[0].replace(',', '.'))
        elif retailer_key == 'sp':
            p_elem = soup.select_one('.c-price__current, [data-price-amount], .price-wrapper .price')
            if p_elem:
                if p_elem.has_attr('data-price-amount'):
                    price = float(p_elem['data-price-amount'])
                else:
                    nums = re.findall(r'\d+(?:[.,]\d+)?', p_elem.get_text().replace(' ', ''))
                    if nums: price = float(nums[0].replace(',', '.'))

        if price == 0.0:
            meta_p = soup.find('meta', attrs={'property': 'product:price:amount'}) or soup.find('meta', attrs={'itemprop': 'price'})
            if meta_p and meta_p.get('content'):
                try: price = float(meta_p['content'].replace(',', '.'))
                except: pass

        # 2. PIEEJAMĪBAS PĀRBAUDE
        btn = soup.select_one('#product-addtocart-button, .add-to-cart, button[data-button-action="add-to-cart"], .c-product-detail__btn-buy')
        is_in_stock = bool(btn and not btn.has_attr('disabled'))
        if not btn and price > 0:
            txt_low = resp.text.lower()
            if 'ir noliktavā' in txt_low or 'pieejams' in txt_low:
                is_in_stock = True

        # 3. IZMĒRU NOLASĪŠANA
        if retailer_key == "hj":
            for opt in soup.select('.form-control-select option, .input-container input[type="radio"]'):
                txt = opt.get_text().strip() if opt.name == 'option' else opt.get('title', '')
                if not txt: continue
                m_yth = re.search(r'Y\s*([\d.]+)', txt, re.IGNORECASE)
                if m_yth: sizes.append(f"Yth {m_yth.group(1)}")
                else:
                    m = re.search(r'\b([1-9]|1[0-3])(?:\.5)?\b', txt)
                    if m: sizes.append(m.group(0))

        elif retailer_key == "hp":
            for sw in soup.select('.swatch-attribute.size .swatch-option, .swatch-attribute.boot_size .swatch-option'):
                if 'disabled' in sw.get('class', []): continue
                txt = sw.get_text().strip()
                if txt:
                    if category == 'Youth' and not txt.lower().startswith('yth'):
                        sizes.append(f"Yth {txt}")
                    else:
                        sizes.append(txt)

        elif retailer_key == "sp":
            for opt in soup.select('select[name*="parameter"] option, .c-param-select option'):
                txt = opt.get_text().strip()
                if 'izvēlieties' in txt.lower(): continue
                eur_m = re.search(r'EUR\s*([\d.]+)', txt, re.IGNORECASE)
                if eur_m:
                    eur_val = eur_m.group(1)
                    if category == 'Youth' and eur_val in EUR_TO_YOUTH:
                        sizes.append(EUR_TO_YOUTH[eur_val])
                    else:
                        sizes.append(eur_val)

        if not sizes and category == 'Youth':
            t = soup.get_text()
            for y, eur in re.findall(r'Yth\s*([\d.]+)|EUR\s*(\d{2})', t, re.IGNORECASE):
                if y: sizes.append(f"Yth {y}")
                elif eur in EUR_TO_YOUTH: sizes.append(EUR_TO_YOUTH[eur])

    except Exception as e:
        print(f"Kļūda lasot datus no {product_url}: {e}")

    return price, is_in_stock, list(dict.fromkeys(sizes))

def scrape_all():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sākas hokeja inventāra skenēšana...")
    session = requests.Session()
    session.headers.update(HEADERS)
    today_str = datetime.now().strftime("%Y-%m-%d")

    all_offers = []

    # 1. Ielādē veikalu kategoriju katalogus
    store_catalogs = {}
    for cat in ["Senior", "Intermediate", "Junior", "Youth"]:
        store_catalogs[cat] = {}
        for r_key in ["hj", "hp", "sp"]:
            cat_url = CATEGORY_URLS[cat][r_key]
            store_catalogs[cat][r_key] = crawl_category(r_key, cat_url, session)
            time.sleep(0.5)

    # 2. Apstrādā katru modeli
    for model in MODELS:
        for cat in model["categories"]:
            for r_key in ["hj", "hp", "sp"]:
                print(f"Pārbauda [{cat.upper()}] {r_key.upper()} -> {model['id']}...")

                # Pārbauda tiešo saiti
                target_url = model.get("direct_urls", {}).get(cat, {}).get(r_key)

                # Ja tiešās saites nav, meklē kategorijas katalogā
                if not target_url:
                    prods = store_catalogs[cat].get(r_key, [])
                    for p in prods:
                        if all(k.lower() in p["title"].lower() for k in model["keywords"]):
                            target_url = p["url"]
                            break

                # Ja prece veikalā ir atrasta
                if target_url:
                    price, stock, sizes = get_product_details(target_url, r_key, cat, session)
                    status = "VERIFIED" if (price > 0 and stock) else "UNVERIFIED"
                    final_url = target_url
                else:
                    price, stock, sizes = 0.0, False, []
                    status = "UNVERIFIED"
                    final_url = CATEGORY_URLS[cat][r_key]

                print(f" -> Cena = €{price}, Noliktavā = {stock}, Izmēri = {sizes}, Statuss = {status}")

                all_offers.append({
                    "type": model["type"],
                    "category": cat,
                    "model": model["id"],
                    "retailer": r_key,
                    "price": price,
                    "shipping": SHIPPING_RATES[r_key],
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

    print(f"Skenēšana pabeigta! scraped_data.json atjaunināts ar {len(all_offers)} ierakstiem.")

if __name__ == '__main__':
    scrape_all()

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'lv-LV,lv;q=0.9,en-US;q=0.8,en;q=0.7'
}

# Tabula Sportega EUR izmēru pārvēršanai par Bauer Youth izmēriem
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

TARGET_SKATES = [
    # --- YOUTH MODEĻI ---
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-m40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/bernu-hokeja-slidas/5729-bauer-supreme-m40-s24-bernu-hokeja-slidas",
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-m40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s24-m40-youth-hokeja-slidas",
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-m40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-m40-youth-d-standarta-kaja-eur-26/d1438563",
        "shipping": 4.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-vapor-fly40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/51-bernu-hokeja-slidas",
        "search_term": "Vapor FLY40",
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-vapor-fly40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-vapor-s25-fly40-youth-hokeja-slidas",
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-vapor-fly40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-vapor-fly40-youth-d-standarta-kaja-eur-26/d1503208",
        "shipping": 4.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-f40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/51-bernu-hokeja-slidas",
        "search_term": "Supreme F40",
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-f40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s26-fuse-youth-hokeja-slidas",
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Youth",
        "model": "bauer-supreme-f40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-fuse-youth-d-standarta-kaja-eur-31/d1584484",
        "shipping": 4.0
    },

    # --- SENIOR MODEĻI ---
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-vapor-fly40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-vapor-s25-fly40-senior-hokeja-slidas",
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-vapor-fly40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/meklesana?search=FLY40",
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-vapor-fly40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-vapor-fly40-senior/d1502757",
        "shipping": 4.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-f40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s26-f40-senior-hokeja-slidas",
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-f40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/pieauguso-hokeja-slidas/5455-bauer-supreme-f40-s26-pieauguso-hokeja-slidas",
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-f40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-f40-senior/d1583973",
        "shipping": 4.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-m40",
        "retailer": "hp",
        "url": "https://hokejapasaule.lv/lv_lv/bauer-supreme-s24-m40-senior-hokeja-slidas",
        "shipping": 3.5
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-m40",
        "retailer": "hj",
        "url": "https://www.hokejam.lv/lv/pieauguso-hokeja-slidas/4507-bauer-supreme-m40-pieauguso-hokeja-slidas",
        "shipping": 0.0
    },
    {
        "type": "skate",
        "category": "Senior",
        "model": "bauer-supreme-m40",
        "retailer": "sp",
        "url": "https://www.sportega.lv/hokeja-slidas-bauer-supreme-m40-senior/d1438036",
        "shipping": 4.0
    }
]

def extract_real_price(soup, retailer):
    """Izvelk reālo gala cenu ar visām atlaidēm."""
    try:
        if retailer == 'hj':
            # PrestaShop: meklējam konkrēto akcijas vai tekošo cenu
            curr_price = soup.select_one('.current-price [itemprop="price"], .current-price-value, .product-price')
            if curr_price:
                clean = re.sub(r'[^\d.,]', '', curr_price.get_text()).replace(',', '.')
                val = float(clean)
                if 20 <= val <= 2000:
                    return val

        elif retailer == 'hp':
            # Magento: prioritāte ir special-price (ja ir atlaide)
            spec_price = soup.select_one('.special-price .price, [data-price-type="finalPrice"] .price')
            if spec_price:
                clean = re.sub(r'[^\d.,]', '', spec_price.get_text()).replace(',', '.')
                val = float(clean)
                if 20 <= val <= 2000:
                    return val
            final_p = soup.select_one('.price-final_price .price, .product-info-price .price')
            if final_p:
                clean = re.sub(r'[^\d.,]', '', final_p.get_text()).replace(',', '.')
                val = float(clean)
                if 20 <= val <= 2000:
                    return val

        elif retailer == 'sp':
            # Sportega: galvenā cenas birka
            p_elem = soup.select_one('.c-price__current, [data-price-amount], .price-wrapper .price')
            if p_elem:
                if p_elem.has_attr('data-price-amount'):
                    return float(p_elem['data-price-amount'])
                clean = re.sub(r'[^\d.,]', '', p_elem.get_text()).replace(',', '.')
                val = float(clean)
                if 20 <= val <= 2000:
                    return val

        # Universāls rezerves meklētājs
        meta_p = soup.find('meta', attrs={'property': 'product:price:amount'}) or soup.find('meta', attrs={'itemprop': 'price'})
        if meta_p and meta_p.get('content'):
            val = float(meta_p['content'].replace(',', '.'))
            if 20 <= val <= 2000:
                return val
    except Exception:
        pass
    return None

def extract_real_sizes(soup, retailer, category):
    """Nolasa reālos, pieejamos izmērus no lapas variācijām."""
    available_sizes = []
    try:
        if retailer == 'hj':
            # Hokejam.lv: parasti dropdown vai saraksts ar 'Y 11.5', 'Y 12.5' vai '7.5'
            options = soup.select('.form-control-select option, .input-container input[type="radio"]')
            for opt in options:
                txt = opt.get_text().strip() if opt.name == 'option' else opt.get('title', '')
                if not txt:
                    continue
                # Pārbauda un konvertē "Y 11.5" -> "Yth 11.5"
                match_yth = re.search(r'Y\s*([\d.]+)', txt, re.IGNORECASE)
                if match_yth:
                    available_sizes.append(f"Yth {match_yth.group(1)}")
                elif category == 'Senior':
                    match_sr = re.search(r'\b([6-9]|1[0-3])(?:\.5)?\b', txt)
                    if match_sr:
                        available_sizes.append(match_sr.group(0))

        elif retailer == 'hp':
            # Hokeja Pasaule: swatches vai atribūti
            swatches = soup.select('.swatch-attribute.size .swatch-option, .swatch-attribute.boot_size .swatch-option')
            for sw in swatches:
                # Ja ir klase 'disabled', izmērs nav pieejams
                if 'disabled' in sw.get('class', []):
                    continue
                txt = sw.get_text().strip()
                if txt:
                    if category == 'Youth':
                        available_sizes.append(f"Yth {txt}")
                    else:
                        available_sizes.append(txt)

        elif retailer == 'sp':
            # Sportega: dropdown ar EUR izmēriem (piem. EUR 26 -> Yth 8)
            options = soup.select('select[name*="parameter"] option, .c-param-select option')
            for opt in options:
                txt = opt.get_text().strip()
                if 'izvēlieties' in txt.lower():
                    continue
                eur_match = re.search(r'EUR\s*([\d.]+)', txt, re.IGNORECASE)
                if eur_match:
                    eur_val = eur_match.group(1)
                    if category == 'Youth' and eur_val in EUR_TO_YOUTH:
                        available_sizes.append(EUR_TO_YOUTH[eur_val])
                    elif category != 'Youth':
                        available_sizes.append(eur_val)
    except Exception as e:
        print(f"Kļūda lasot izmērus: {e}")

    # Ja neatrada atsevišķus variantus, bet prece ir viena konkrēta izmēra prece
    if not available_sizes:
        title = soup.get_text()
        if category == 'Youth':
            yth_in_title = re.findall(r'Yth\s*([\d.]+)|EUR\s*(\d{2})', title, re.IGNORECASE)
            for y, eur in yth_in_title:
                if y:
                    available_sizes.append(f"Yth {y}")
                elif eur and eur in EUR_TO_YOUTH:
                    available_sizes.append(EUR_TO_YOUTH[eur])

    # Noņemam dublikātus, saglabājot secību
    return list(dict.fromkeys(available_sizes))

def scrape_item(target, session):
    url = target['url']
    # Ja preces linkā ir vispārējā kategorija (prece vēl nav atrasta)
    if 'search_term' in target:
        return 0.0, False, [], url, 'UNVERIFIED'

    try:
        resp = session.get(url, timeout=12)
        if resp.status_code != 200:
            return 0.0, False, [], url, 'UNVERIFIED'

        soup = BeautifulSoup(resp.text, 'html.parser')
        price = extract_real_price(soup, target['retailer'])

        # Pieejamības pārbaude
        btn = soup.select_one('#product-addtocart-button, .add-to-cart, button[data-button-action="add-to-cart"], .c-product-detail__btn-buy')
        is_in_stock = bool(btn and not btn.has_attr('disabled'))
        
        # Ja poga nav atrasta, bet ir cena
        if not btn and price:
            txt_low = resp.text.lower()
            if 'ir noliktavā' in txt_low or 'pieejams' in txt_low:
                is_in_stock = True

        sizes = extract_real_sizes(soup, target['retailer'], target['category'])
        if not sizes and is_in_stock:
            # Ja izmēru selektors nav atsevišķs, atstājam pamata
            sizes = target.get('default_sizes', ['Standard'])

        status = 'VERIFIED' if (price and is_in_stock) else 'UNVERIFIED'
        return (price or 0.0), is_in_stock, sizes, url, status

    except Exception as e:
        print(f"Kļūda skenējot {url}: {e}")
        return 0.0, False, [], url, 'UNVERIFIED'

def scrape_all():
    print("Sākas precīza hokeja inventāra cenu un izmēru skenēšana...")
    session = requests.Session()
    session.headers.update(HEADERS)
    today_date = datetime.now().strftime("%Y-%m-%d")

    updated_offers = []
    for t in TARGET_SKATES:
        cat = t.get('category', 'Senior')
        print(f"Pārbauda [{cat.upper()}] {t['retailer'].upper()} -> {t['model']}")
        price, stock, sizes, final_url, status = scrape_item(t, session)
        time.sleep(1)

        print(f" -> Rezultāts: Cena = €{price}, Noliktavā = {stock}, Izmēri = {sizes}, Statuss = {status}")

        updated_offers.append({
            "type": t["type"],
            "category": cat,
            "model": t["model"],
            "retailer": t["retailer"],
            "price": price,
            "shipping": t["shipping"],
            "sizes": sizes,
            "fits": ["FIT 2", "Regular"],
            "stock": stock,
            "checked": today_date,
            "url": final_url,
            "status": status
        })

    payload = {
        "updatedAt": datetime.now().isoformat(),
        "offers": updated_offers
    }

    with open('scraped_data.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("scraped_data.json veiksmīgi atjaunināts ar reālajām cenām un izmēriem.")

if __name__ == '__main__':
    scrape_all()

"""
OpenStreetMap Overpass API ile il bazında gerçek işletme sayımı.
TAMAMEN ÜCRETSİZ: API anahtarı, kredi kartı veya faturalandırma hesabı gerekmez.

Not: OpenStreetMap verisi gönüllü katkısına dayanır. Google Places'a göre özellikle
küçük illerde eksik sayımlar olabilir (bazı işletmeler haritaya hiç eklenmemiş olabilir).
Büyük şehirlerde (İstanbul, Ankara, İzmir vb.) veri kalitesi genelde daha iyidir.
Bunu gerçek ama muhtemelen "alt sınır" (eksik sayabilen) bir tahmin olarak düşün.

Kurulum:
    pip install requests

Çalıştırma:
    python3 osm_places_scraper.py            # tam koşu (81 il x kategoriler)
    python3 osm_places_scraper.py --test      # sadece 3 il ile test (İstanbul, Ankara, Bayburt)

Çıktı:
    places_summary.csv   -> il, kategori, gerçek (OSM) işletme sayısı
"""

import csv
import sys
import time
import requests
from il_data import IL_DATA

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "fwturkiye-places-scraper/1.0 (contact: tuncanil92@gmail.com)"}

# İl adı -> resmi plaka kodu (Overpass'ta ISO3166-2:TR alan eşlemesi için kullanılıyor)
PLATE_CODE = {
    "Adana": 1, "Adıyaman": 2, "Afyonkarahisar": 3, "Ağrı": 4, "Amasya": 5,
    "Ankara": 6, "Antalya": 7, "Artvin": 8, "Aydın": 9, "Balıkesir": 10,
    "Bilecik": 11, "Bingöl": 12, "Bitlis": 13, "Bolu": 14, "Burdur": 15,
    "Bursa": 16, "Çanakkale": 17, "Çankırı": 18, "Çorum": 19, "Denizli": 20,
    "Diyarbakır": 21, "Edirne": 22, "Elazığ": 23, "Erzincan": 24, "Erzurum": 25,
    "Eskişehir": 26, "Gaziantep": 27, "Giresun": 28, "Gümüşhane": 29, "Hakkâri": 30,
    "Hatay": 31, "Isparta": 32, "Mersin": 33, "İstanbul": 34, "İzmir": 35,
    "Kars": 36, "Kastamonu": 37, "Kayseri": 38, "Kırklareli": 39, "Kırşehir": 40,
    "Kocaeli": 41, "Konya": 42, "Kütahya": 43, "Malatya": 44, "Manisa": 45,
    "Kahramanmaraş": 46, "Mardin": 47, "Muğla": 48, "Muş": 49, "Nevşehir": 50,
    "Niğde": 51, "Ordu": 52, "Rize": 53, "Sakarya": 54, "Samsun": 55,
    "Siirt": 56, "Sinop": 57, "Sivas": 58, "Tekirdağ": 59, "Tokat": 60,
    "Trabzon": 61, "Tunceli": 62, "Şanlıurfa": 63, "Uşak": 64, "Van": 65,
    "Yozgat": 66, "Zonguldak": 67, "Aksaray": 68, "Bayburt": 69, "Karaman": 70,
    "Kırıkkale": 71, "Batman": 72, "Şırnak": 73, "Bartın": 74, "Ardahan": 75,
    "Iğdır": 76, "Yalova": 77, "Karabük": 78, "Kilis": 79, "Osmaniye": 80,
    "Düzce": 81,
}

CATEGORY_FILTERS = {
    "fitness": [
        'nwr["leisure"="fitness_centre"](area.a);',
        'nwr["leisure"="sports_centre"]["sport"="fitness"](area.a);',
        'nwr["shop"="fitness"](area.a);',
    ],
    "pilates_pt": [
        'nwr["leisure"="fitness_centre"]["sport"~"pilates|exercise"](area.a);',
        'node["name"~"pilates",i](area.a);',
        'node["name"~"reformer",i](area.a);',
        'node["name"~"personal training",i](area.a);',
    ],
    "fizyoterapi": [
        'nwr["healthcare"="physiotherapist"](area.a);',
        'node["name"~"fizyoterapi",i](area.a);',
        'node["name"~"fizik tedavi",i](area.a);',
    ],
}

OVERPASS_TIMEOUT_S = 120
HTTP_TIMEOUT_S = 150
MAX_RETRIES = 5
RETRY_WAIT_S = 20
REQUEST_GAP_S = 1.5


def query_count(kod, filters):
    area_sel = f'area["ISO3166-2"="TR-{kod:02d}"]["boundary"="administrative"]->.a;'
    body = (
        f"[out:json][timeout:{OVERPASS_TIMEOUT_S}];\n"
        + area_sel + "\n(\n" + "\n".join(filters) + "\n);\nout count;"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(OVERPASS_URL, data={"data": body}, headers=HEADERS, timeout=HTTP_TIMEOUT_S)
        except requests.RequestException as e:
            print(f"  [HATA] istek başarısız ({attempt}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_WAIT_S)
            continue

        if resp.status_code == 200:
            data = resp.json()
            elements = data.get("elements", [])
            if elements and "tags" in elements[0]:
                return int(elements[0]["tags"].get("total", 0))
            return 0

        if resp.status_code in (429, 504):
            print(f"  [BEKLE] {resp.status_code} alındı, {RETRY_WAIT_S}s bekleyip tekrar denenecek ({attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_WAIT_S)
            continue

        print(f"  [HATA] {resp.status_code}: {resp.text[:300]}")
        return 0

    print("  [HATA] tüm denemeler başarısız oldu, 0 olarak kaydedildi")
    return 0


def save_csv(rows):
    with open("places_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["il", "kategori", "sayi"])
        writer.writeheader()
        writer.writerows(rows)


def run(il_list):
    rows = []
    for il in il_list:
        kod = PLATE_CODE[il]
        print(f"\n=== {il} (TR-{kod:02d}) ===")
        for kategori, filters in CATEGORY_FILTERS.items():
            count = query_count(kod, filters)
            print(f"  -> {kategori}: {count}")
            rows.append({"il": il, "kategori": kategori, "sayi": count})
            time.sleep(REQUEST_GAP_S)
        save_csv(rows)

    print("\nBitti. Özet: places_summary.csv")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run(["İstanbul", "Ankara", "Bayburt"])
    else:
        run(list(IL_DATA.keys()))

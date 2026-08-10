"""
Google Places API (New) ile il bazında gerçek işletme sayımı.

ÖNEMLİ: Bu script'i BENİM ortamımda çalıştıramıyorum çünkü sandbox'ımın genel
internet erişimi yok (googleapis.com'a bağlanamıyorum). Bu yüzden bu dosyayı
KENDİ bilgisayarında çalıştırman gerekiyor.

Kurulum:
    pip install requests

Çalıştırma:
    python3 google_places_scraper.py            # tam koşu (81 il x kategoriler)
    python3 google_places_scraper.py --test      # sadece 3 il ile test (İstanbul, Ankara, Bayburt)

Çıktı:
    places_raw/{kategori}_{il}.json   -> her il+kategori için ham sonuçlar
    places_summary.csv                -> il, kategori, gerçek işletme sayısı

Maliyet uyarısı: Google Places API Text Search (New) her istek için ücretlendirir
(Google Cloud hesabında aylık ücretsiz kredi var ama sınırlı). 81 il x ~4 sorgu x
en fazla 3 sayfa ile tahminen birkaç yüz istek olur. Önce --test ile deneyip
Google Cloud Console > Billing üzerinden maliyeti kontrol etmeni öneririm.

Sonucu bana geri verdiğinde (places_summary.csv dosyasını paylaş), haritaları
tahmini oranlar yerine bu gerçek sayılarla yeniden oluştururum.
"""

import json
import os
import sys
import time
import requests
from il_data import IL_DATA

# --- API anahtarı: koda gömülü DEĞİL, ortam değişkeninden / GitHub Secret'tan okunuyor ---
API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    sys.exit("HATA: GOOGLE_PLACES_API_KEY ortam değişkeni tanımlı değil.")

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.location,nextPageToken"

# Her ana kategori için bir veya birden fazla arama terimi (sonuçlar id'ye göre
# birleştirilip tekilleştirilir, aynı yer birden fazla terimle eşleşse bile 1 kez sayılır)
CATEGORIES = {
    "fitness": ["fitness salonu", "spor salonu", "gym"],
    "pilates_pt": ["pilates stüdyosu", "reformer pilates", "personal training stüdyosu"],
    "fizyoterapi": ["fizyoterapi kliniği", "fizik tedavi merkezi"],
}

RADIUS_M = 40000.0       # il merkezinden arama yarıçapı (metre) - büyük iller için yetersiz kalabilir
MAX_PAGES = 3             # sorgu başına en fazla sayfa (sayfa başına ~20 sonuç -> üst sınır ~60)
PAGE_WAIT_S = 2.0         # Google, nextPageToken'ın aktif olması için birkaç saniye bekleme öneriyor
REQUEST_GAP_S = 0.3       # istekler arası kısa bekleme (rate-limit'e takılmamak için)

OUT_DIR = "places_raw"


def search_text(query, lat, lon, page_token=None):
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "textQuery": query,
        "languageCode": "tr",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": RADIUS_M,
            }
        },
    }
    if page_token:
        body["pageToken"] = page_token

    resp = requests.post(ENDPOINT, headers=headers, json=body, timeout=20)
    if resp.status_code != 200:
        print(f"  [HATA] {resp.status_code}: {resp.text[:300]}")
        return [], None
    data = resp.json()
    return data.get("places", []), data.get("nextPageToken")


def collect_for_query(query, il, lat, lon):
    results = []
    seen_ids = set()
    page_token = None
    for page in range(MAX_PAGES):
        places, page_token = search_text(f"{query} {il}", lat, lon, page_token)
        for p in places:
            pid = p.get("id")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                results.append(p)
        time.sleep(REQUEST_GAP_S)
        if not page_token:
            break
        time.sleep(PAGE_WAIT_S)
    return results


def run(il_list):
    os.makedirs(OUT_DIR, exist_ok=True)
    summary_rows = []

    for il in il_list:
        pop, lat, lon, macfit = IL_DATA[il]
        print(f"\n=== {il} ===")
        for cat, queries in CATEGORIES.items():
            merged = {}
            for q in queries:
                print(f"  sorgu: '{q} {il}'")
                found = collect_for_query(q, il, lat, lon)
                for p in found:
                    merged[p.get("id")] = p
            count = len(merged)
            print(f"  -> {cat}: {count} benzersiz işletme")
            summary_rows.append({"il": il, "kategori": cat, "sayi": count})
            with open(os.path.join(OUT_DIR, f"{cat}_{il}.json"), "w", encoding="utf-8") as f:
                json.dump(list(merged.values()), f, ensure_ascii=False, indent=2)

    with open("places_summary.csv", "w", encoding="utf-8") as f:
        f.write("il,kategori,sayi\n")
        for row in summary_rows:
            f.write(f"{row['il']},{row['kategori']},{row['sayi']}\n")

    print("\nBitti. Özet: places_summary.csv")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run(["İstanbul", "Ankara", "Bayburt"])
    else:
        run(list(IL_DATA.keys()))

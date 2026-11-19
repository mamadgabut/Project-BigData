import json
import logging
import hashlib
import re
from pathlib import Path
import sys

# Tambahkan path folder script agar import db_connection selalu berjalan
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from db_connection import get_existing_urls_from_db

logger = logging.getLogger(__name__)

RAW_FILE = SCRIPT_DIR / "result.json"
VALIDATED_FILE = SCRIPT_DIR / "validated_articles.json"

def extract_urlhash(url: str) -> str:
    """Menghasilkan hash MD5 dari URL unik."""
    return hashlib.md5(url.strip().encode("utf-8")).hexdigest()

def extract_id_url(url: str) -> str:
    """
    Mengekstrak ID angka artikel dari URL VOI.
    Contoh: https://voi.id/berita/603139/judul -> '603139'
    """
    match = re.search(r'/(\d+)/', url)
    if match:
        return match.group(1)
    return None

def validate_raw_data():
    """
    Fungsi Validasi Data Mentah:
    1. Mengecek kelengkapan data (menolak data jika URL / Title / Content bernilai None atau kosong).
    2. Mengekstrak metadata teknis: urlhash & id_url.
    3. Mencegah redundansi: menyaring duplikasi antar batch dan terhadap database bronze.
    """
    if not RAW_FILE.exists():
        logger.warning("File raw %s tidak ditemukan. Tidak ada data untuk divalidasi.", RAW_FILE)
        return []

    with open(RAW_FILE, "r", encoding="utf-8") as f:
        try:
            raw_articles = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Format JSON pada file raw rusak: %s", e)
            return []

    logger.info("Memulai validasi %d artikel mentah...", len(raw_articles))

    # Ambil URL yang sudah tersimpan di database bronze untuk mencegah redundansi
    existing_urls = get_existing_urls_from_db()

    seen_urls_in_batch = set()
    validated_articles = []
    
    skipped_null = 0
    skipped_duplicate_batch = 0
    skipped_duplicate_db = 0

    for article in raw_articles:
        url = article.get("url")

        # 1. VALIDASI NULL / NONE (Atribut Wajib)
        if not url or not isinstance(url, str) or not url.strip():
            logger.warning("Data dilewati: URL kosong / None.")
            skipped_null += 1
            continue

        url = url.strip()
        title = article.get("title")
        content = article.get("content")

        if not title or not content:
            logger.warning("Data dilewati: Title atau Content kosong pada URL %s", url)
            skipped_null += 1
            continue

        # 2. VALIDASI REDUNDANSI (Batch & Database)
        if url in seen_urls_in_batch:
            skipped_duplicate_batch += 1
            continue
        seen_urls_in_batch.add(url)

        if url in existing_urls:
            skipped_duplicate_db += 1
            continue

        # 3. EKSTRAKSI METADATA TEKNIS (urlhash & id_url)
        urlhash = extract_urlhash(url)
        id_url = extract_id_url(url)

        # Standarisasi data validated untuk layer Bronze
        validated_item = {
            "urlhash": urlhash,
            "url": url,
            "id_url": id_url,
            "title": title.strip() if isinstance(title, str) else title,
            "kategori": article.get("kategori"),
            "published_time": article.get("published_time"),
            "content": content.strip() if isinstance(content, str) else content,
            "tim_redaksi": article.get("tim_redaksi") or [],
            "tags": article.get("tags") or []
        }

        validated_articles.append(validated_item)

    # Simpan hasil validasi
    with open(VALIDATED_FILE, "w", encoding="utf-8") as f:
        json.dump(validated_articles, f, indent=4, ensure_ascii=False)

    print("=== HASIL VALIDASI DATA MENTAH ===")
    print(f"Total data mentah dibaca : {len(raw_articles)}")
    print(f"Dilewati (NULL/Kosong)   : {skipped_null}")
    print(f"Dilewati (Duplikat Batch): {skipped_duplicate_batch}")
    print(f"Dilewati (Ada di DB)     : {skipped_duplicate_db}")
    print(f"Lolos Validasi           : {len(validated_articles)}")
    print(f"Disimpan di              : {VALIDATED_FILE}")

    return validated_articles

if __name__ == "__main__":
    validate_raw_data()

# 1. add unicodedata, re, psycopg
import re
import unicodedata
import logging
import json
from datetime import datetime
from pathlib import Path
import sys
from psycopg2.extras import Json

# Tambahkan path folder script ke sys.path untuk impor db_connection
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from db_connection import get_connection

logger = logging.getLogger(__name__)

# Pola kalimat promosi / noise khas VOI yang perlu dibersihkan dari konten
EXCLUSION_PHRASES = [
    r"BACA JUGA:.*?(?=(\.|$))",
    r"Baca terus\s*VOI\.id.*?(?=(\.|$))",
    r"Add VOI as a Preferred Source.*",
    r"Follow VOI news updates across Google\..*",
    r"Tag:.*"
]

BULAN_INDO = {
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2,
    "maret": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "agustus": 8, "agt": 8, "agu": 8,
    "september": 9, "sep": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12
}


def clean_text(text: str) -> str:
    """Membersihkan whitespace liar, zero-width chars, dan normalisasi unicode."""
    if not text or not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u200b", "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_content(content: str) -> str:
    """Membersihkan isi konten artikel dari kalimat promosi, rekomendasi, dan tag footer."""
    if not content:
        return ""
    
    text = clean_text(content)
    for pattern in EXCLUSION_PHRASES:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    return re.sub(r"\s+", " ", text).strip()


# 3. create clean tag function
def clean_tags(tags_data) -> list:
    """
    Membersihkan tags:
    SEBELUM : [{"href": "...", "text": "ijazah"}, {"href": "...", "text": "dpr"}]
    SESUDAH : ["ijazah", "dpr"]  (hanya text, href dibuang)
    """
    if not tags_data or not isinstance(tags_data, list):
        return []

    cleaned_tags = []
    seen = set()

    for item in tags_data:
        tag_text = ""
        if isinstance(item, dict):
            tag_text = item.get("text") or item.get("nama") or ""
        elif isinstance(item, str):
            tag_text = item

        tag_clean = clean_text(tag_text).lower()
        if tag_clean and tag_clean not in seen:
            seen.add(tag_clean)
            cleaned_tags.append(tag_clean)

    return cleaned_tags


def clean_tim_redaksi(redaksi_data) -> tuple:
    """
    Membersihkan tim redaksi:
    SEBELUM : [{"href": "...", "text": "Tim VOI", "bagian": "Reporter"}, ...]
    SESUDAH : [{"text": "Tim VOI", "bagian": "Reporter"}, ...]  (hanya text & bagian, href dibuang)
    
    Return: (author, editor, cleaned_redaksi_list)
    """
    if not redaksi_data or not isinstance(redaksi_data, list):
        return None, None, []

    author = None
    editor = None
    cleaned_list = []
    seen = set()

    for item in redaksi_data:
        if not isinstance(item, dict):
            continue

        nama = clean_text(item.get("text") or item.get("nama") or "")
        bagian = clean_text(item.get("bagian") or "Redaksi")

        if not nama:
            continue

        identity = (nama.lower(), bagian.lower())
        if identity in seen:
            continue
        seen.add(identity)

        # Identifikasi author (reporter) dan editor utama untuk kolom silver
        if "reporter" in bagian.lower() and not author:
            author = nama
        elif "editor" in bagian.lower() and not editor:
            editor = nama

        cleaned_list.append({
            "text": nama,
            "bagian": bagian
        })

    if not author and cleaned_list:
        author = cleaned_list[0]["text"]

    return author, editor, cleaned_list


def parse_published_date(date_str: str) -> datetime:
    """Mengonversi string tanggal mentah VOI menjadi datetime terstandar."""
    if not date_str:
        return datetime.now()

    cleaned_str = clean_text(date_str).replace("|", "").strip().lower()
    match = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4}),?\s+(\d{1,2})[:.](\d{2})", cleaned_str)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        month = BULAN_INDO.get(month_name, 1)
        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            pass

    return datetime.now()


# 4. create ingestion function
def ingest_to_silver(cursor, records):
    """
    Menyimpan data hasil transformasi ke tabel silver.articles.
    Menggunakan ON CONFLICT (url) DO NOTHING untuk memastikan sifat idempoten.
    """
    insert_query = """
        INSERT INTO silver.articles (
            bronze_id,
            url,
            id_url,
            title,
            kategori,
            published_date,
            content,
            author,
            editor,
            tim_redaksi,
            tags,
            word_count,
            char_count
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING;
    """

    inserted = 0
    for record in records:
        cursor.execute(
            insert_query,
            (
                record["bronze_id"],
                record["url"],
                record["id_url"],
                record["title"],
                record["kategori"],
                record["published_date"],
                record["content"],
                record["author"],
                record["editor"],
                Json(record["tim_redaksi"]),  # [{"text": "...", "bagian": "..."}]
                Json(record["tags"]),         # ["tag1", "tag2"]
                record["word_count"],
                record["char_count"]
            )
        )
        if cursor.rowcount == 1:
            inserted += 1

    return inserted


# 5. select data from bronze, then insert to silver
def select_from_bronze(cursor):
    """Mengambil artikel dari bronze.articles yang belum pernah diproses ke silver.articles."""
    select_query = """
        SELECT 
            b.id,
            b.url,
            b.id_url,
            b.title,
            b.kategori,
            b.published_time,
            b.content,
            b.tim_redaksi,
            b.tags
        FROM bronze.articles b
        LEFT JOIN silver.articles s ON b.url = s.url
        WHERE s.url IS NULL;
    """
    cursor.execute(select_query)
    return cursor.fetchall()


def _save_silver_json(transformed_records):
    """
    Menyimpan hasil transformasi ke file silver_articles.json untuk keperluan
    perbandingan / inspeksi manual (selalu dijalankan, baik DB aktif maupun tidak).
    """
    output_file = SCRIPT_DIR / "silver_articles.json"
    # Buat salinan yang serializable (datetime -> string)
    serializable = []
    for rec in transformed_records:
        item = dict(rec)
        if hasattr(item.get("published_date"), "isoformat"):
            item["published_date"] = item["published_date"].strftime("%Y-%m-%d %H:%M:%S")
        serializable.append(item)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=4, ensure_ascii=False)
    print(f"[OUTPUT] silver_articles.json disimpan -> {output_file}")


# 2. create main function
def main():
    """
    Fungsi Utama Pipeline Bronze -> Silver:
    1. Mengambil data dari bronze (Database atau fallback file JSON validated)
    2. Melakukan transformasi:
       - Memisahkan & membersihkan tags -> list string ["tag1", "tag2"] (tanpa href)
       - Memisahkan & membersihkan tim redaksi -> [{"text": "...", "bagian": "..."}] (tanpa href)
       - Ekstrak author dan editor
       - Membersihkan teks konten & normalisasi tanggal
    3. Ingest data yang sudah bersih ke silver.articles di PostgreSQL
    """
    print("=== MEMULAI PREPROCESSING BRONZE -> SILVER ===")

    connection = get_connection()
    if not connection:
        print("[WARNING] Koneksi database PostgreSQL tidak tersedia.")
        print("[FALLBACK] Melakukan transformasi lokal dari validated_articles.json...")
        _run_local_fallback()
        return

    try:
        with connection.cursor() as cursor:
            # 5. Select data from bronze
            rows = select_from_bronze(cursor)

            if not rows:
                print("Tidak ada data baru di Bronze yang perlu diproses ke Silver.")
                return

            print(f"Ditemukan {len(rows)} data Bronze baru. Memulai pembersihan...")

            transformed_records = []
            for row in rows:
                (b_id, url, id_url, raw_title, raw_kategori,
                 raw_pub_time, raw_content, raw_redaksi, raw_tags) = row

                # Preprocessing
                clean_t = clean_text(raw_title)
                clean_k = clean_text(raw_kategori)
                clean_c = clean_content(raw_content)
                pub_date = parse_published_date(raw_pub_time)

                # 3. Clean tags (hanya text, href dibuang)
                tags_clean = clean_tags(raw_tags)

                # Clean tim redaksi (hanya text & bagian, href dibuang) + ekstrak author/editor
                author, editor, redaksi_clean = clean_tim_redaksi(raw_redaksi)

                word_count = len(clean_c.split())
                char_count = len(clean_c)

                transformed_records.append({
                    "bronze_id": b_id,
                    "url": url,
                    "id_url": id_url,
                    "title": clean_t,
                    "kategori": clean_k,
                    "published_date": pub_date,
                    "content": clean_c,
                    "author": author,
                    "editor": editor,
                    "tim_redaksi": redaksi_clean,
                    "tags": tags_clean,
                    "word_count": word_count,
                    "char_count": char_count
                })

            # Selalu simpan ke silver_articles.json untuk perbandingan / inspeksi
            _save_silver_json(transformed_records)

            # 4. Ingestion ke Silver DB
            inserted_count = ingest_to_silver(cursor, transformed_records)
            connection.commit()

            print("=== PREPROCESSING & INGESTION TO SILVER BERHASIL ===")
            print(f"Total artikel diproses                      : {len(transformed_records)}")
            print(f"Total berhasil di-insert ke silver.articles : {inserted_count}")

    except Exception as err:
        connection.rollback()
        logger.error("Terjadi kesalahan saat preprocessing ke Silver: %s", err)
        raise
    finally:
        connection.close()


def _run_local_fallback():
    """Fungsi pembantu jika database belum aktif, menyimpan hasil transform ke silver_articles.json."""
    json_path = SCRIPT_DIR / "validated_articles.json"
    if not json_path.exists():
        json_path = SCRIPT_DIR / "result.json"

    if not json_path.exists():
        print(f"File data mentah {json_path} tidak ditemukan.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    transformed = []
    for idx, item in enumerate(articles, start=1):
        clean_c = clean_content(item.get("content"))
        author, editor, redaksi_clean = clean_tim_redaksi(item.get("tim_redaksi"))
        tags_clean = clean_tags(item.get("tags"))

        transformed.append({
            "bronze_id": idx,
            "url": item.get("url"),
            "id_url": item.get("id_url"),
            "title": clean_text(item.get("title")),
            "kategori": clean_text(item.get("kategori")),
            "published_date": str(parse_published_date(item.get("published_time"))),
            "content": clean_c,
            "author": author,
            "editor": editor,
            "tim_redaksi": redaksi_clean,
            "tags": tags_clean,
            "word_count": len(clean_c.split()),
            "char_count": len(clean_c)
        })

    output_file = SCRIPT_DIR / "silver_articles.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(transformed, f, indent=4, ensure_ascii=False)

    print(f"Berhasil mentransformasi {len(transformed)} artikel ke format Silver!")
    print(f"Hasil disimpan di: {output_file}")


run_preprocessing = main

if __name__ == "__main__":
    main()

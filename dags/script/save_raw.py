import json
import logging
from pathlib import Path
import sys
from psycopg2.extras import Json

# Tambahkan path folder script agar import db_connection selalu berjalan
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from db_connection import get_connection

logger = logging.getLogger(__name__)

VALIDATED_FILE = SCRIPT_DIR / "validated_articles.json"

def save_to_bronze():
    """
    Menyimpan data artikel yang telah divalidasi ke dalam tabel bronze.articles di database PostgreSQL.
    Menggunakan ON CONFLICT (url) DO NOTHING untuk memastikan sifat idempoten.
    """
    if not VALIDATED_FILE.exists():
        logger.warning("File validated %s tidak ditemukan. Tidak ada data yang diinsert.", VALIDATED_FILE)
        return

    with open(VALIDATED_FILE, "r", encoding="utf-8") as f:
        try:
            articles = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Gagal membaca JSON dari %s: %s", VALIDATED_FILE, e)
            return

    if not articles:
        print("Tidak ada artikel baru yang perlu disimpan ke database bronze.")
        return

    connection = get_connection()
    if not connection:
        # DB tidak tersedia, tapi validated_articles.json sudah ada - tidak perlu raise error
        print("[WARNING] Database tidak tersedia. Data tetap tersimpan di validated_articles.json untuk referensi.")
        print(f"File JSON: {VALIDATED_FILE}")
        return

    inserted_count = 0
    skipped_count = 0

    try:
        with connection.cursor() as cursor:
            insert_query = """
                INSERT INTO bronze.articles (
                    urlhash,
                    url,
                    id_url,
                    title,
                    kategori,
                    published_time,
                    content,
                    tim_redaksi,
                    tags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            """

            for article in articles:
                cursor.execute(
                    insert_query,
                    (
                        article.get("urlhash"),
                        article.get("url"),
                        article.get("id_url"),
                        article.get("title"),
                        article.get("kategori"),
                        article.get("published_time"),
                        article.get("content"),
                        Json(article.get("tim_redaksi", [])),
                        Json(article.get("tags", []))
                    )
                )

                if cursor.rowcount == 1:
                    inserted_count += 1
                else:
                    skipped_count += 1

        connection.commit()
        print("=== HASIL PENYIMPANAN KE BRONZE ===")
        print(f"Total data diproses   : {len(articles)}")
        print(f"Berhasil di-insert    : {inserted_count}")
        print(f"Dilewati (Duplikat DB): {skipped_count}")

    except Exception as e:
        connection.rollback()
        logger.error("Terjadi error saat insert ke bronze.articles: %s", e)
        raise
    finally:
        connection.close()

if __name__ == "__main__":
    save_to_bronze()

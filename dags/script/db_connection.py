import os
import logging
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Cari root folder project untuk load file .env
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

def get_connection():
    """
    Membuat koneksi ke database PostgreSQL Lakehouse (project_bigdata_db).
    Mendukung eksekusi dari dalam Docker (host: postgres-lakehouse, port: 5432)
    maupun dari terminal host Windows (host: localhost, port: 5434 / 5432).
    """
    primary_host = os.getenv("DB_HOST", "localhost")
    primary_port = os.getenv("DB_PORT", "5434")
    dbname = os.getenv("DB_NAME", "project_bigdata_db")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgrespassword")

    # Daftar kombinasi (host, port) yang dicoba berurutan
    attempts = [
        (primary_host, primary_port),
        ("localhost", "5434"),
        ("localhost", "5432"),
        ("postgres-lakehouse", "5432")
    ]

    seen = set()
    for host, port in attempts:
        pair = (host, str(port))
        if pair in seen:
            continue
        seen.add(pair)

        try:
            connection = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=3
            )
            return connection
        except psycopg2.Error:
            continue

    logger.warning("Gagal koneksi ke PostgreSQL (%s:%s/%s). Pastikan container menyala.", primary_host, primary_port, dbname)
    return None

def get_existing_urls_from_db():
    """
    Mengambil daftar URL unik yang sudah tersimpan di tabel bronze.articles untuk mencegah duplikasi.
    """
    connection = get_connection()
    if not connection:
        logger.info("Database belum aktif. Melewati pengecekan DB dan mengembalikan set kosong.")
        return set()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT url FROM bronze.articles;")
            rows = cursor.fetchall()
            existing_urls = {row[0] for row in rows if row[0]}
            logger.info("Ditemukan %d URL yang sudah ada di database.", len(existing_urls))
            return existing_urls
    except psycopg2.Error as err:
        logger.warning("Tabel bronze.articles belum tersedia atau error: %s", err)
        connection.rollback()
        return set()
    finally:
        connection.close()

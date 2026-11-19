import sys
from pathlib import Path
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Menambahkan folder script ke sys.path agar Airflow dapat mengimpor fungsi task
SCRIPT_DIR = Path(__file__).resolve().parent / "script"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

# Impor fungsi-fungsi dari script modular
from main import run_scraper
from validate_raw import validate_raw_data
from save_raw import save_to_bronze

default_args = {
    "owner": "bigdata_team",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="dag_voi_bronze_pipeline",
    default_args=default_args,
    description="Pipeline Ingestion Berita VOI ke Layer Bronze (Scraper -> Validate -> Save Raw)",
    schedule="*/5 * * * *",  # Berjalan otomatis setiap 5 menit
    catchup=False,
    tags=["bronze", "voi", "scraping", "bigdata"],
) as dag:

    # Task 1: Scraper
    task_scraper = PythonOperator(
        task_id="scrape_voi_task",
        python_callable=run_scraper,
    )

    # Task 2: Validasi (Cek NULL/None, Duplikasi, dan Ekstraksi urlhash + id_url)
    task_validator = PythonOperator(
        task_id="validate_raw_task",
        python_callable=validate_raw_data,
    )

    # Task 3: Simpan ke PostgreSQL Bronze Layer
    task_save_bronze = PythonOperator(
        task_id="save_to_bronze_task",
        python_callable=save_to_bronze,
    )

    # Definisi Urutan Eksekusi Pipeline (DAG 1)
    task_scraper >> task_validator >> task_save_bronze

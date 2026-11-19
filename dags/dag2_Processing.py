import sys
from pathlib import Path
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Menambahkan folder script ke sys.path agar Airflow dapat mengimpor fungsi task
SCRIPT_DIR = Path(__file__).resolve().parent / "script"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

# Impor fungsi preprocessing
from preprocessing import run_preprocessing

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
    dag_id="dag_voi_silver_pipeline",
    default_args=default_args,
    description="Pipeline Transformasi Berita VOI dari Bronze ke Silver (Clean, Parse, Normalize)",
    schedule="*/10 * * * *",  # Berjalan setiap 10 menit (setelah data bronze terkumpul)
    catchup=False,
    tags=["silver", "voi", "preprocessing", "bigdata"],
) as dag:

    # Task: Transformasi & Ingestion ke Silver Layer
    task_process_to_silver = PythonOperator(
        task_id="transform_to_silver_task",
        python_callable=run_preprocessing,
    )

    task_process_to_silver

import sys
from pathlib import Path
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

SCRIPT_DIR = Path(__file__).resolve().parent / "script"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from gold_warehouse import (
    validate_silver_source,
    ensure_gold_schema,
    load_dim_category,
    load_dim_date,
    load_dim_reporter,
    load_dim_editor,
    load_fact_article,
    validate_gold,
    create_analytics_views,
)

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
    dag_id="dag_voi_gold_warehouse",
    default_args=default_args,
    description="Pipeline Gold Warehouse VOI dari Silver ke Star Schema.",
    schedule="*/5 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["gold", "voi", "warehouse", "bigdata"],
) as dag:

    task_validate_silver = PythonOperator(
        task_id="validate_silver_source_task",
        python_callable=validate_silver_source,
    )

    task_ensure_schema = PythonOperator(
        task_id="ensure_gold_schema_task",
        python_callable=ensure_gold_schema,
    )

    task_load_category = PythonOperator(
        task_id="load_dim_category_task",
        python_callable=load_dim_category,
    )

    task_load_date = PythonOperator(
        task_id="load_dim_date_task",
        python_callable=load_dim_date,
    )

    task_load_reporter = PythonOperator(
        task_id="load_dim_reporter_task",
        python_callable=load_dim_reporter,
    )

    task_load_editor = PythonOperator(
        task_id="load_dim_editor_task",
        python_callable=load_dim_editor,
    )

    task_load_fact = PythonOperator(
        task_id="load_fact_article_task",
        python_callable=load_fact_article,
    )

    task_validate_gold = PythonOperator(
        task_id="validate_gold_task",
        python_callable=validate_gold,
    )

    task_create_views = PythonOperator(
        task_id="create_analytics_views_task",
        python_callable=create_analytics_views,
    )

    (
        task_validate_silver
        >> task_ensure_schema
        >> task_load_category
        >> task_load_date
        >> task_load_reporter
        >> task_load_editor
        >> task_load_fact
        >> task_validate_gold
        >> task_create_views
    )

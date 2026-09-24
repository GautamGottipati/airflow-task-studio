from datetime import datetime

from airflow.sdk import dag, task
from task_studio import editable


@dag(
    dag_id="task_studio_demo",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
)
def task_studio_demo():

    @task
    @editable
    def extract_customers(
        source: str = "postgres",
        batch_size: int = 8000,
        timeout: int = 300,
    ):
        print(f"Source: {source}")
        print(f"Batch size: {batch_size}")
        print(f"Timeout: {timeout}")

    @task
    @editable(
        fields={
            "target": {
                "choices": [
                    "snowflake",
                    "postgres",
                    "bigquery",
                ],
                "description": "Destination warehouse",
            },
            "batch_size": {
                "min": 100,
                "max": 50000,
                "description": "Rows processed per batch",
            },
        }
    )
    def load_customers(
        target: str = "snowflake",
        batch_size: int = 4000,
    ):
        print(f"Target: {target}")
        print(f"Batch size: {batch_size}")

    @task
    def internal_cleanup():
        print("cleanup")

    extract_customers() >> load_customers() >> internal_cleanup()


task_studio_demo()
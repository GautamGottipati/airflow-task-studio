import json
from datetime import datetime, timezone
from typing import Any

from airflow.sdk import Variable


PREFIX = "task_studio_consumed"


def _key(
    dag_id: str,
    task_id: str,
) -> str:
    return (
        f"{PREFIX}__"
        f"{dag_id}__"
        f"{task_id}"
    )


def record_consumption(
    *,
    override_id: str,
    dag_id: str,
    task_id: str,
    run_id: str,
    try_number: int | None,
    map_index: int | None,
    values: dict[str, Any],
) -> None:
    payload = {
        "override_id": override_id,
        "dag_id": dag_id,
        "task_id": task_id,
        "run_id": run_id,
        "try_number": try_number,
        "map_index": map_index,
        "values": values,

        "consumed_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    Variable.set(
        _key(
            dag_id=dag_id,
            task_id=task_id,
        ),
        json.dumps(payload),
    )
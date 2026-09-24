import json

from airflow.models import Variable


PREFIX = "task_studio_override"


def _key(
    dag_id: str,
    task_id: str,
) -> str:
    return (
        f"{PREFIX}__"
        f"{dag_id}__"
        f"{task_id}"
    )


def save_next_run_override(
    *,
    override_id: str,
    dag_id: str,
    task_id: str,
    values: dict,
) -> dict:
    key = _key(
        dag_id=dag_id,
        task_id=task_id,
    )

    payload = {
        "override_id": override_id,
        "dag_id": dag_id,
        "task_id": task_id,
        "scope": "next_run",
        "values": values,
    }

    Variable.set(
        key,
        json.dumps(payload),
    )

    return payload


def get_override(
    dag_id: str,
    task_id: str,
) -> dict | None:
    key = _key(
        dag_id=dag_id,
        task_id=task_id,
    )

    raw = Variable.get(
        key,
        default_var=None,
    )

    if raw is None:
        return None

    if isinstance(raw, dict):
        return raw

    return json.loads(raw)


def delete_override(
    dag_id: str,
    task_id: str,
) -> dict | None:
    """
    Delete and return the pending override.

    Returning the payload allows callers to know
    exactly which override_id was cancelled.
    """

    key = _key(
        dag_id=dag_id,
        task_id=task_id,
    )

    existing = get_override(
        dag_id=dag_id,
        task_id=task_id,
    )

    if existing is None:
        return None

    Variable.delete(key)

    return existing
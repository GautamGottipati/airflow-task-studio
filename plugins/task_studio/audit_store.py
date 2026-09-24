import json
from datetime import datetime, timezone

from airflow.models import Variable


PREFIX = "task_studio_audit"
MAX_HISTORY = 100


def _key(
    dag_id: str,
    task_id: str,
) -> str:
    return (
        f"{PREFIX}__"
        f"{dag_id}__"
        f"{task_id}"
    )


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _read_history(
    dag_id: str,
    task_id: str,
) -> list[dict]:
    raw = Variable.get(
        _key(
            dag_id=dag_id,
            task_id=task_id,
        ),
        default_var=None,
    )

    if raw is None:
        return []

    if isinstance(raw, list):
        return raw

    return json.loads(raw)


def _write_history(
    dag_id: str,
    task_id: str,
    history: list[dict],
) -> None:
    Variable.set(
        _key(
            dag_id=dag_id,
            task_id=task_id,
        ),
        json.dumps(
            history[-MAX_HISTORY:]
        ),
    )


def create_audit_entry(
    *,
    override_id: str,
    dag_id: str,
    task_id: str,
    values: dict,
) -> dict:
    history = _read_history(
        dag_id=dag_id,
        task_id=task_id,
    )

    entry = {
        "override_id": override_id,
        "dag_id": dag_id,
        "task_id": task_id,
        "scope": "next_run",
        "values": values,
        "status": "pending",
        "created_at": _now(),

        "run_id": None,
        "try_number": None,
        "map_index": None,

        "consumed_at": None,
        "cancelled_at": None,
    }

    history.append(entry)

    _write_history(
        dag_id=dag_id,
        task_id=task_id,
        history=history,
    )

    return entry


def get_history(
    dag_id: str,
    task_id: str,
) -> list[dict]:
    history = _read_history(
        dag_id=dag_id,
        task_id=task_id,
    )

    return list(
        reversed(history)
    )


def cancel_override_by_id(
    *,
    dag_id: str,
    task_id: str,
    override_id: str,
) -> bool:
    history = _read_history(
        dag_id=dag_id,
        task_id=task_id,
    )

    found = False

    for entry in history:
        if (
            entry.get("override_id")
            == override_id
            and entry.get("status")
            == "pending"
        ):
            entry["status"] = "cancelled"
            entry["cancelled_at"] = _now()

            found = True
            break

    if found:
        _write_history(
            dag_id=dag_id,
            task_id=task_id,
            history=history,
        )

    return found


def mark_consumed(
    *,
    dag_id: str,
    task_id: str,
    override_id: str,
    run_id: str,
    try_number: int | None,
    map_index: int | None,
    consumed_at: str,
) -> bool:
    """
    Mark one exact Task Studio override as
    consumed by one Airflow task execution.
    """

    history = _read_history(
        dag_id=dag_id,
        task_id=task_id,
    )

    found = False

    for entry in history:
        if (
            entry.get("override_id")
            == override_id
        ):
            entry["status"] = "consumed"

            entry["run_id"] = run_id

            entry["try_number"] = (
                try_number
            )

            entry["map_index"] = (
                map_index
            )

            entry["consumed_at"] = (
                consumed_at
            )

            found = True
            break

    if found:
        _write_history(
            dag_id=dag_id,
            task_id=task_id,
            history=history,
        )

    return found
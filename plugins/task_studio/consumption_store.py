import json

from airflow.models import Variable


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


def get_consumption(
    *,
    dag_id: str,
    task_id: str,
) -> dict | None:
    """
    Read a runtime consumption acknowledgement.
    """

    raw = Variable.get(
        _key(
            dag_id=dag_id,
            task_id=task_id,
        ),
        default_var=None,
    )

    if raw is None:
        return None

    if isinstance(raw, dict):
        return raw

    return json.loads(raw)


def delete_consumption(
    *,
    dag_id: str,
    task_id: str,
) -> bool:
    """
    Delete a consumption acknowledgement after
    it has been reconciled into audit history.
    """

    key = _key(
        dag_id=dag_id,
        task_id=task_id,
    )

    existing = get_consumption(
        dag_id=dag_id,
        task_id=task_id,
    )

    if existing is None:
        return False

    Variable.delete(key)

    return True
from pathlib import Path
import mimetypes
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from task_studio.task_inspector import (
    inspect_task,
    discover_editable_tasks,
    validate_override,
)

from task_studio.override_store import (
    get_override,
    save_next_run_override,
    delete_override,
)

from task_studio.audit_store import (
    create_audit_entry,
    get_history,
    cancel_override_by_id,
    mark_consumed,
)

from task_studio.consumption_store import (
    get_consumption,
    delete_consumption,
)


# Make sure JavaScript bundles are served
# with the correct MIME type.
mimetypes.add_type(
    "application/javascript",
    ".cjs",
)


app = FastAPI()


# ---------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------

class OverrideRequest(BaseModel):
    dag_id: str
    task_id: str
    values: dict


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "message": "Task Studio is running!",
    }


# ---------------------------------------------------------
# TASK DISCOVERY
# ---------------------------------------------------------

@app.get("/api/tasks")
def get_editable_tasks():
    tasks = discover_editable_tasks()

    return {
        "tasks": tasks,
        "count": len(tasks),
    }


# ---------------------------------------------------------
# TASK DETAILS
# ---------------------------------------------------------

@app.get("/api/task/{dag_id}/{task_id}")
def get_task_details(
    dag_id: str,
    task_id: str,
):
    try:
        return inspect_task(
            dag_id=dag_id,
            task_id=task_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# CREATE / REPLACE PENDING OVERRIDE
# ---------------------------------------------------------

@app.post("/api/overrides")
def create_override(
    request: OverrideRequest,
):
    try:
        validated_values = validate_override(
            dag_id=request.dag_id,
            task_id=request.task_id,
            values=request.values,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    #
    # ONE identity for the entire lifecycle.
    #
    override_id = str(
        uuid.uuid4()
    )

    override = save_next_run_override(
        override_id=override_id,
        dag_id=request.dag_id,
        task_id=request.task_id,
        values=validated_values,
    )

    create_audit_entry(
        override_id=override_id,
        dag_id=request.dag_id,
        task_id=request.task_id,
        values=validated_values,
    )

    return override


# ---------------------------------------------------------
# READ PENDING OVERRIDE
# ---------------------------------------------------------

@app.get(
    "/api/overrides/{dag_id}/{task_id}"
)
def read_override(
    dag_id: str,
    task_id: str,
):
    override = get_override(
        dag_id=dag_id,
        task_id=task_id,
    )

    return {
        "override": override,
    }


# ---------------------------------------------------------
# CANCEL PENDING OVERRIDE
# ---------------------------------------------------------

@app.delete(
    "/api/overrides/{dag_id}/{task_id}"
)
def cancel_override(
    dag_id: str,
    task_id: str,
):
    deleted = delete_override(
        dag_id=dag_id,
        task_id=task_id,
    )

    if deleted is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No pending override found."
            ),
        )

    override_id = deleted.get(
        "override_id"
    )

    if override_id:
        cancel_override_by_id(
            dag_id=dag_id,
            task_id=task_id,
            override_id=override_id,
        )

    return {
        "status": "ok",
        "message":
            "Pending override cancelled.",
        "dag_id": dag_id,
        "task_id": task_id,
        "override_id": override_id,
    }


# ---------------------------------------------------------
# OVERRIDE HISTORY
# ---------------------------------------------------------

@app.get("/api/history/{dag_id}/{task_id}")
def read_override_history(
    dag_id: str,
    task_id: str,
):
    #
    # Look for an acknowledgement written by
    # the task runtime.
    #
    consumption = get_consumption(
        dag_id=dag_id,
        task_id=task_id,
    )

    if consumption:
        override_id = consumption.get(
            "override_id"
        )

        #
        # Only reconcile acknowledgements that
        # have a real override identity.
        #
        if override_id:
            updated = mark_consumed(
                dag_id=dag_id,
                task_id=task_id,
                override_id=override_id,
                run_id=consumption.get(
                    "run_id",
                    "unknown",
                ),
                try_number=consumption.get(
                    "try_number"
                ),
                map_index=consumption.get(
                    "map_index"
                ),
                consumed_at=consumption.get(
                    "consumed_at"
                ),
            )

            #
            # Delete acknowledgement ONLY after
            # successfully writing it into audit.
            #
            if updated:
                delete_consumption(
                    dag_id=dag_id,
                    task_id=task_id,
                )

    #
    # Read history AFTER reconciliation.
    #
    history = get_history(
        dag_id=dag_id,
        task_id=task_id,
    )

    return {
        "history": history,
        "count": len(history),
    }


# ---------------------------------------------------------
# REACT PRODUCTION BUNDLE
# ---------------------------------------------------------

DIST_DIR = (
    Path(__file__).parent
    / "frontend"
    / "dist"
)


if DIST_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(
            directory=str(DIST_DIR)
        ),
        name="task_studio_static",
    )
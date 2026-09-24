# Airflow Task Studio

A local Airflow 3 sandbox with a custom plugin, **Task Studio**, that lets you inspect editable task parameters and queue one-off overrides for a task's *next* run — with full audit history — from a React UI embedded directly in the Airflow webserver.

## What's here

- `docker-compose.yaml` — standard Airflow 3.1.8 CeleryExecutor stack (postgres, redis, apiserver, scheduler, dag-processor, triggerer, worker).
- `dags/` — example DAGs, including `demo_task_studio.py` which defines a task decorated as editable.
- `plugins/task_studio/` — the Task Studio plugin:
  - `plugin.py` — registers a FastAPI sub-app and React app with Airflow's plugin manager.
  - `routes.py` — REST API: task discovery, task detail inspection, create/read/cancel override, override history.
  - `editable.py` — decorator that marks a task's callable arguments as overridable, and resolves any pending override at task execution time.
  - `task_inspector.py` — statically parses DAG source to discover which tasks/parameters are editable.
  - `override_store.py` / `audit_store.py` / `consumption_store.py` / `runtime_store.py` — persistence for pending overrides, audit trail, and runtime acknowledgement, backed by Airflow `Variable`s.
  - `frontend/` — Vite + React + TypeScript UI, built to `frontend/dist` and served by the FastAPI sub-app at `/task-studio`.

## Prerequisites

- Docker Desktop (8 GB+ memory allocated to Docker is recommended)
- Node.js and npm, if you want to build/develop the `frontend/` app

## Running Airflow

```bash
# one-time DB init
docker compose up airflow-init

# start everything
docker compose up -d

# check status
docker compose ps
```

Airflow UI: http://localhost:8080
Default login: `airflow` / `airflow` (set via `_AIRFLOW_WWW_USER_USERNAME` / `_AIRFLOW_WWW_USER_PASSWORD` in `docker-compose.yaml`)

Stop / reset:

```bash
docker compose stop      # stop, keep data
docker compose down      # stop and remove containers
docker compose down -v   # also wipe the database
```

## Task Studio plugin

Once Airflow is running, Task Studio is available:

- As a nav item: **Browse → Task Studio**
- Contextually, on a task instance's detail view

API is mounted under `/task-studio`, e.g. `GET /task-studio/health`, `GET /task-studio/api/tasks`.

### Frontend development

```bash
cd plugins/task_studio/frontend
npm install
npm run dev      # local dev server
npm run build    # produces dist/, served by the plugin's FastAPI app
```

## Notes

- `dags/`, `plugins/`, `config/`, and `logs/` are bind-mounted into the containers, so local edits are picked up by the dag-processor / plugin manager without rebuilding images.
- The dag-processor scans `dags/` for new/changed files on an interval (`dag_dir_list_interval`, default 300s), so a newly added DAG file can take a few minutes to appear in the UI.

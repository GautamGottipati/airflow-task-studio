# Airflow Task Studio

> **See, understand, and safely modify task parameters without leaving Apache Airflow.**

Airflow Task Studio is an Apache Airflow 3.1 plugin that gives operators a UI for inspecting opted-in tasks and safely overriding selected task arguments for the **next successful run**.

The project is currently a **hackathon / functional prototype**, not a production-ready control plane. See [Production Readiness](#production-readiness) for known limitations.

## What Task Studio Does

Task Studio lets a DAG author opt a Python task into runtime parameter editing with `@editable`:

```python
from task_studio import editable

@task
@editable(
    fields={
        "target": {
            "choices": ["snowflake", "postgres", "bigquery"],
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
```

An operator can then use Task Studio to:

- discover tasks explicitly marked with `@editable`;
- inspect the task's Python code and parameters;
- see defaults, types, descriptions and developer-defined constraints;
- preview changes before applying them;
- apply a parameter override for the next run;
- cancel a pending override;
- see override history;
- identify the exact Airflow run that consumed an override.

The core idea is:

> **Code defines what a task can do. Task Studio controls how it runs.**

Task Studio does **not** rewrite DAG source code.

---

## Current Feature Set

- Apache Airflow 3.1 plugin
- FastAPI plugin backend
- React plugin UI
- Global Task Studio entry in Airflow navigation
- Contextual Task Studio entry on task-instance pages
- `@editable` opt-in decorator
- AST-based task/function inspection
- Automatic parameter discovery
- Parameter type/default display
- `choices`, `min`, `max`, `description`, and `editable=False` controls
- Preview Changes
- API-side validation
- Runtime validation
- Apply for Next Run
- Pending Override indicator
- Cancel Override
- Edit Once semantics
- Multiple DAG/task namespacing
- Override audit history
- Runtime consumption acknowledgement
- Run ID / try number / map index tracking

---

## Architecture

```text
                         Apache Airflow 3.1

 DAG source
     │
     │ @editable
     ▼
 Task Inspector ────────────────────────┐
     │                                  │
     ▼                                  ▼
 FastAPI plugin                    React plugin
     │                                  │
     │ POST override                    │
     ▼                                  │
 Pending Override Variable              │
     │                                  │
     ▼                                  │
 Airflow task execution                 │
     │                                  │
     │ airflow.sdk.Variable             │
     ▼                                  │
 Override applied                       │
     │                                  │
     ▼                                  │
 Original task succeeds                 │
     │                                  │
     ├── consumption acknowledgement    │
     └── pending override deleted       │
                                        │
 Consumption acknowledgement ──────────►│
     │                                  │
     ▼                                  │
 Audit reconciliation ─────────────────►│
     │
     ▼
 CONSUMED + run identity
```

A key Airflow 3 design rule in this project is that **running DAG/task code does not directly access the Airflow metadata database through SQLAlchemy/ORM**. Runtime access uses the Airflow Task SDK (`airflow.sdk.Variable` and `get_current_context`).

---

## Repository Layout

A typical checkout looks like:

```text
airflow-task-studio/
├── docker-compose.yaml
├── dags/
│   └── demo_task_studio.py
├── plugins/
│   └── task_studio/
│       ├── __init__.py
│       ├── plugin.py
│       ├── routes.py
│       ├── task_inspector.py
│       ├── override_store.py
│       ├── audit_store.py
│       ├── consumption_store.py
│       ├── runtime_store.py
│       ├── editable.py
│       └── frontend/
│           ├── package.json
│           ├── vite.config.ts
│           ├── src/
│           │   ├── App.tsx
│           │   └── main.tsx
│           └── dist/
│               └── main.umd.cjs
├── logs/
├── config/
└── .env
```

---

# Tester Setup

## Prerequisites

Install the following before testing:

- Docker Desktop
- Docker Compose
- Git
- Node.js + npm (required only if rebuilding the React UI)

The current development environment uses **Apache Airflow 3.1.x** and has been tested with the official Airflow Docker Compose setup.

Check Docker:

```bash
docker --version
docker compose version
```

If you plan to rebuild the frontend:

```bash
node --version
npm --version
```

---

## 1. Clone the Repository

```bash
git clone <REPOSITORY_URL>
cd airflow-task-studio
```

Replace `<REPOSITORY_URL>` with the repository URL supplied by the project author.

---

## 2. Create Required Airflow Directories

From the project root:

```bash
mkdir -p dags logs plugins config
```

On Linux, the official Airflow Docker setup may also require an Airflow UID in `.env`:

```bash
echo "AIRFLOW_UID=$(id -u)" > .env
```

On Docker Desktop for macOS, follow the Docker Compose configuration included with this repository.

---

## 3. Build the Task Studio Frontend

If `plugins/task_studio/frontend/dist/main.umd.cjs` is already included in the repository, testers can normally skip this step.

To rebuild it:

```bash
cd plugins/task_studio/frontend
npm install
npm run build
cd ../../..
```

The important build artifact is:

```text
plugins/task_studio/frontend/dist/main.umd.cjs
```

Task Studio uses a Vite UMD library build because Airflow loads the React plugin bundle itself.

The Vite configuration should expose the library as `AirflowPlugin` and externalize Airflow-provided React dependencies.

---

## 4. Initialize Airflow

For a fresh official Docker Compose environment:

```bash
docker compose up airflow-init
```

Wait for initialization to complete successfully.

---

## 5. Start Airflow

```bash
docker compose up -d
```

Check containers:

```bash
docker compose ps
```

Wait until the required Airflow services are healthy/running.

Then open Airflow in your browser at:

```text
http://localhost:8080
```

Use the credentials configured by your Docker Compose environment.

---

## 6. Verify That Airflow Loaded Task Studio

Inside an Airflow container, run:

```bash
airflow plugins
```

You should see a plugin named:

```text
task_studio
```

You can also verify the Task Studio health endpoint in the browser:

```text
http://localhost:8080/task-studio/health
```

A successful response confirms that the FastAPI portion of the plugin is loaded.

---

## 7. Verify the React Bundle

Open:

```text
http://localhost:8080/task-studio/static/main.umd.cjs
```

The JavaScript bundle should be served rather than returning a 404.

Task Studio should also appear in Airflow's navigation under the configured Browse/navigation entry.

---

# Demo DAG

A simple tester DAG can be created at:

```text
dags/demo_task_studio.py
```

Example:

```python
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
```

Notice that `internal_cleanup` does **not** use `@editable`. It should therefore not be exposed as an editable Task Studio task.

---

# Testing Task Studio

## Test 1 — Discover Editable Tasks

Open Task Studio from Airflow's navigation.

For the demo DAG, Task Studio should discover:

```text
extract_customers
load_customers
```

It should not expose `internal_cleanup` for editing.

---

## Test 2 — Contextual Task Studio

Open the `task_studio_demo` DAG and navigate to a task instance such as `load_customers`.

Open the contextual **Task Studio** tab/entry.

Task Studio should receive Airflow context including:

```text
dagId
taskId
runId
mapIndex
```

and automatically display the selected task instead of requiring the tester to search for it again.

---

## Test 3 — Inspect Parameters

For `load_customers`, Task Studio should show approximately:

```text
target
Default: snowflake
Choices: snowflake, postgres, bigquery

batch_size
Default: 4000
Min: 100
Max: 50000
```

The task's source code should also be available for inspection.

---

## Test 4 — Validation

Try setting:

```text
batch_size = 60000
```

The override should be rejected because the DAG author configured:

```python
"max": 50000
```

Try a valid value such as:

```text
batch_size = 12000
```

Task Studio should allow it.

---

## Test 5 — Preview Changes

Before applying an override, use **Preview Changes**.

The UI should make the intended change clear, for example:

```text
batch_size
4000 → 12000
```

No DAG source code is modified by this operation.

---

## Test 6 — Apply for Next Run

Apply:

```text
batch_size = 12000
```

for `task_studio_demo / load_customers`.

Task Studio should show a pending override.

The pending runtime record is namespaced by DAG and task:

```text
task_studio_override__task_studio_demo__load_customers
```

You can inspect it from an Airflow container:

```bash
airflow variables get \
  task_studio_override__task_studio_demo__load_customers
```

A new override should include an `override_id`, for example:

```json
{
  "override_id": "<uuid>",
  "dag_id": "task_studio_demo",
  "task_id": "load_customers",
  "scope": "next_run",
  "values": {
    "batch_size": 12000
  }
}
```

---

## Test 7 — Execute the DAG

Trigger `task_studio_demo` from Airflow.

Wait for `load_customers` to complete successfully.

Its logs should contain:

```text
Target: snowflake
Batch size: 12000
```

This proves that the runtime argument was changed without rewriting the DAG's Python source.

---

## Test 8 — Verify Edit Once

After successful execution, run:

```bash
airflow variables get \
  task_studio_override__task_studio_demo__load_customers
```

You should receive a message indicating that the Variable no longer exists.

That is expected.

The lifecycle is:

```text
PENDING
   ↓
task reads override
   ↓
task executes successfully
   ↓
consumption acknowledged
   ↓
pending override deleted
```

If the original task function raises an exception, Task Studio intentionally does **not** consume/delete the override so that a retry can use it again.

---

## Test 9 — Verify Consumption Acknowledgement

After successful execution, check:

```bash
airflow variables get \
  task_studio_consumed__task_studio_demo__load_customers
```

Before server-side reconciliation, the acknowledgement looks similar to:

```json
{
  "override_id": "<uuid>",
  "dag_id": "task_studio_demo",
  "task_id": "load_customers",
  "run_id": "manual__...",
  "try_number": 1,
  "map_index": -1,
  "values": {
    "batch_size": 12000
  },
  "consumed_at": "..."
}
```

The `override_id` should match the ID stored in the corresponding audit entry.

---

## Test 10 — Verify Audit Reconciliation

Open or request:

```text
http://localhost:8080/task-studio/api/history/task_studio_demo/load_customers
```

The history endpoint reconciles a successful runtime acknowledgement with the audit entry that has the same `override_id`.

The history should then contain an entry similar to:

```json
{
  "override_id": "<uuid>",
  "dag_id": "task_studio_demo",
  "task_id": "load_customers",
  "scope": "next_run",
  "values": {
    "batch_size": 12000
  },
  "status": "consumed",
  "created_at": "...",
  "run_id": "manual__...",
  "try_number": 1,
  "map_index": -1,
  "consumed_at": "...",
  "cancelled_at": null
}
```

Once reconciliation succeeds, the temporary `task_studio_consumed__...` acknowledgement is deleted because its information has been incorporated into audit history.

The React history panel should display the override as **CONSUMED**, together with the Airflow run identity.

---

## Test 11 — Cancel an Override

Create another override but do **not** trigger the DAG.

Use **Cancel Override** in Task Studio.

Expected behavior:

- pending override is deleted;
- matching audit record is changed from `pending` to `cancelled`;
- cancellation timestamp is recorded;
- the history UI shows the cancelled entry.

---

# `@editable` Usage

## Make Every Function Parameter Editable

```python
@task
@editable
def extract(
    source: str = "postgres",
    batch_size: int = 8000,
):
    ...
```

## Add Constraints

```python
@task
@editable(
    fields={
        "batch_size": {
            "min": 100,
            "max": 50000,
            "description": "Rows per batch",
        }
    }
)
def extract(
    batch_size: int = 8000,
):
    ...
```

## Restrict Values

```python
@task
@editable(
    fields={
        "target": {
            "choices": [
                "snowflake",
                "postgres",
                "bigquery",
            ]
        }
    }
)
def load(
    target: str = "snowflake",
):
    ...
```

## Hide a Parameter from Editing

```python
@task
@editable(
    fields={
        "internal_flag": {
            "editable": False,
        }
    }
)
def process(
    batch_size: int = 1000,
    internal_flag: bool = False,
):
    ...
```

Task Studio validates overrides when they are submitted and validates them again inside task execution as defense in depth.

---

# Useful API Endpoints

```text
GET    /task-studio/health
GET    /task-studio/api/tasks
GET    /task-studio/api/task/{dag_id}/{task_id}
POST   /task-studio/api/overrides
GET    /task-studio/api/overrides/{dag_id}/{task_id}
DELETE /task-studio/api/overrides/{dag_id}/{task_id}
GET    /task-studio/api/history/{dag_id}/{task_id}
```

The frontend bundle is served under:

```text
/task-studio/static/
```

---

# Useful Debugging Commands

List Task Studio Variables:

```bash
airflow variables list | grep task_studio
```

Inspect a pending override:

```bash
airflow variables get \
  task_studio_override__task_studio_demo__load_customers
```

Inspect runtime consumption acknowledgement:

```bash
airflow variables get \
  task_studio_consumed__task_studio_demo__load_customers
```

Inspect audit history:

```bash
airflow variables get \
  task_studio_audit__task_studio_demo__load_customers
```

Check loaded plugins:

```bash
airflow plugins
```

Check Docker services:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

If you change Python plugin code and Airflow does not pick up the change, restart the relevant Airflow containers:

```bash
docker compose restart
```

If you change React source code, rebuild the bundle:

```bash
cd plugins/task_studio/frontend
npm run build
```

Then refresh Airflow in the browser. A hard refresh may be useful if the browser has cached an older JavaScript bundle.

---

# Troubleshooting

## Task Studio Does Not Appear in Airflow

Check:

```bash
airflow plugins
```

Confirm that `task_studio` is listed and that the `plugins/` directory is mounted into the Airflow containers.

Also check container logs for plugin import errors.

## React Page Is Blank or Returns 404

Verify:

```text
plugins/task_studio/frontend/dist/main.umd.cjs
```

exists.

Then verify that this URL is served:

```text
http://localhost:8080/task-studio/static/main.umd.cjs
```

If the source changed, run `npm run build` again.

## Override Variable Disappeared

If the task completed successfully, this is expected for an **Edit Once** override.

Check the audit/history and consumption acknowledgement instead.

## Task Uses the Original Value

Check that:

1. the task is decorated with `@editable`;
2. the override is for the correct `dag_id` and `task_id`;
3. the pending override exists before task execution;
4. the task's parameter name matches the override parameter;
5. the override satisfies the configured validation rules.

## Parameter Is Missing from Task Studio

Task Studio inspects the Python function represented by `@editable`. Confirm that the parameter still exists in the function signature and that it has not explicitly been configured with `editable=False`.

---

# Current Storage Model

The prototype currently uses Airflow Variables with separate namespaces:

```text
task_studio_override__{dag_id}__{task_id}
task_studio_consumed__{dag_id}__{task_id}
task_studio_audit__{dag_id}__{task_id}
```

Each newly applied override receives a UUID `override_id` that follows it through its lifecycle:

```text
CREATE
  │
  ▼
override_id = abc-123
  │
  ├── Pending Override
  │
  ├── Audit Entry: PENDING
  │
  ▼
Task execution
  │
  ▼
Consumption acknowledgement
  │
  ▼
Audit Entry: CONSUMED
     run_id
     try_number
     map_index
     consumed_at
```

This ID is important because two overrides may contain identical parameter values; matching by `override_id` avoids ambiguous audit reconciliation.

---

# Production Readiness

**Task Studio is currently a functional prototype / hackathon project. It should not yet be deployed as an unrestricted production control plane.**

Before production use, the project still needs several important hardening steps.

### Authentication and Authorization

Plugin API routes must be protected so that only authenticated and authorized users can inspect, create, or cancel overrides. Production authorization should distinguish read access from override-management permissions.

### Atomic Override Claiming

The current Variable key is namespaced by `(dag_id, task_id)`. Two simultaneous executions of the same DAG/task may therefore race for the same Edit Once override.

A production implementation needs an atomic claim operation so that exactly one task instance owns a one-time override.

### Transactional Persistence

Airflow Variables are convenient for the prototype but are not being used here as a transactional event store. Production audit/override state should use durable transactional persistence or another appropriate backend.

### Concurrent Acknowledgements

The current consumption acknowledgement also uses one Variable namespace per DAG/task. Concurrent executions of the same task require stronger event/claim semantics to prevent acknowledgement overwrites.

### Failure Recovery

Production behavior should explicitly cover partial-failure scenarios, including:

```text
task succeeds → acknowledgement write fails
acknowledgement succeeds → override deletion fails
worker terminates during consumption
retry occurs after partial completion
DAG/task renamed while override is pending
```

### Testing

Production hardening should include:

- unit tests for type coercion and validation;
- API tests;
- Airflow integration tests;
- retry/failure tests;
- concurrent-run tests;
- mapped-task tests;
- authentication/authorization tests;
- plugin upgrade/version compatibility tests;
- structured logging and operational metrics.

---

# Scope and Safety Model

Task Studio intentionally does **not** provide arbitrary Python editing from the Airflow UI.

The DAG author remains in control by explicitly choosing:

```text
which task is editable
which parameters exist
which parameters are editable
allowed choices
minimum values
maximum values
parameter descriptions
```

The operator can only tune the surface intentionally exposed by the DAG author.

This distinction is central to the project:

> **Don't edit the pipeline. Tune the pipeline.**

---

# Current Status

At the current milestone, the following flow has been demonstrated end-to-end:

```text
@editable task
      ↓
Task Studio discovers task
      ↓
Operator changes parameter
      ↓
Preview Changes
      ↓
Apply for Next Run
      ↓
PENDING audit entry
      ↓
Airflow executes task
      ↓
Runtime override applied
      ↓
Task succeeds
      ↓
Consumption acknowledgement
      ↓
Pending override removed
      ↓
Audit reconciled
      ↓
CONSUMED
      ↓
Exact Airflow run displayed
```

The next major engineering milestones are **authentication/authorization** and **concurrency-safe atomic claiming**.

---

## Project Philosophy

Task Studio treats task parameters as a controlled operational interface rather than forcing operators to edit DAG source code for routine runtime tuning.

**Code defines what a task can do. Task Studio controls how it runs.**

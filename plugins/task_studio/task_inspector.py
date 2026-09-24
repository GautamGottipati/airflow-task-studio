import ast
from pathlib import Path
from typing import Any

from airflow.models.dagbag import DagBag


def _literal_value(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return ast.unparse(node)


def _decorator_name(node: ast.AST) -> str | None:
    """
    Extract a readable decorator name.

    Examples:
        @editable              -> "editable"
        @editable(...)         -> "editable"
        @task_studio.editable  -> "task_studio.editable"
    """

    if isinstance(node, ast.Call):
        return _decorator_name(node.func)

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parts = []
        current: ast.AST = node

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        return ".".join(reversed(parts))

    return None


def _is_task_studio_editable(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """
    Return True if the function uses:

        @editable

    or:

        @editable(...)

    or:

        @task_studio.editable
    """

    for decorator in node.decorator_list:
        name = _decorator_name(decorator)

        if name in {
            "editable",
            "task_studio.editable",
        }:
            return True

    return False


def _editable_config(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict:
    """
    Extract optional fields={} configuration from:

        @editable(
            fields={
                "batch_size": {
                    "min": 100,
                    "max": 50000,
                }
            }
        )

    Plain:

        @editable

    returns {}.

    Important:
    fields={} is NOT treated as an allowlist.

    Parameters remain editable by default unless:

        "editable": False
    """

    for decorator in node.decorator_list:
        # Plain @editable
        if isinstance(decorator, ast.Name):
            if decorator.id == "editable":
                return {}

        # Plain @task_studio.editable
        if isinstance(decorator, ast.Attribute):
            name = _decorator_name(decorator)

            if name == "task_studio.editable":
                return {}

        # @editable(...)
        if not isinstance(decorator, ast.Call):
            continue

        name = _decorator_name(decorator.func)

        if name not in {
            "editable",
            "task_studio.editable",
        }:
            continue

        for keyword in decorator.keywords:
            if keyword.arg != "fields":
                continue

            try:
                value = ast.literal_eval(
                    keyword.value
                )

                if isinstance(value, dict):
                    return value

            except Exception:
                # If the config cannot be statically evaluated,
                # fall back to no extra configuration.
                return {}

    return {}


def inspect_task(
    dag_id: str,
    task_id: str,
) -> dict:
    """
    Inspect one Airflow task and return the parameters
    exposed through Task Studio.
    """

    dag_bag = DagBag(include_examples=False)

    dag = dag_bag.get_dag(dag_id)

    if dag is None:
        raise ValueError(
            f"DAG '{dag_id}' not found"
        )

    try:
        dag.get_task(task_id)
    except Exception:
        raise ValueError(
            f"Task '{task_id}' not found in DAG '{dag_id}'"
        )

    dag_file = Path(dag.fileloc)

    if not dag_file.exists():
        raise ValueError(
            f"DAG source file does not exist: {dag_file}"
        )

    source = dag_file.read_text()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        if node.name != task_id:
            continue

        if not _is_task_studio_editable(node):
            raise ValueError(
                f"Task '{task_id}' is not exposed to "
                "Task Studio. Add @editable to enable it."
            )

        editable_config = _editable_config(node)

        arguments = node.args.args
        defaults = node.args.defaults

        default_offset = (
            len(arguments) - len(defaults)
        )

        parameters = []

        for index, arg in enumerate(arguments):
            annotation = None

            if arg.annotation is not None:
                annotation = ast.unparse(
                    arg.annotation
                )

            default = None
            has_default = False

            if index >= default_offset:
                default_node = defaults[
                    index - default_offset
                ]

                default = _literal_value(
                    default_node
                )

                has_default = True

            field_config = editable_config.get(
                arg.arg,
                {},
            )

            is_editable = field_config.get(
                "editable",
                True,
            )

            # Explicitly hidden fields should not appear
            # in the Task Studio UI.
            if not is_editable:
                continue

            parameters.append(
                {
                    "name": arg.arg,
                    "type": annotation,
                    "default": default,
                    "has_default": has_default,
                    "config": field_config,
                }
            )

        function_code = ast.get_source_segment(
            source,
            node,
        )

        return {
            "dag_id": dag_id,
            "task_id": task_id,
            "file": str(dag_file),
            "editable": True,
            "parameters": parameters,
            "code": function_code,
        }

    raise ValueError(
        f"Could not find Python function "
        f"'{task_id}' in {dag_file}"
    )


def validate_override(
    dag_id: str,
    task_id: str,
    values: dict,
) -> dict:
    """
    Validate Task Studio override values against the
    task's @editable contract.

    Returns normalized values when valid.

    Raises ValueError when invalid.
    """

    task = inspect_task(
        dag_id=dag_id,
        task_id=task_id,
    )

    parameters = {
        parameter["name"]: parameter
        for parameter in task["parameters"]
    }

    validated = {}

    for name, raw_value in values.items():

        if name not in parameters:
            raise ValueError(
                f"Parameter '{name}' is not editable "
                f"for task '{task_id}'."
            )

        parameter = parameters[name]

        parameter_type = parameter.get("type")

        config = parameter.get(
            "config",
            {},
        )

        # Convert incoming JSON/string values into
        # the task's declared Python type.
        try:
            if parameter_type == "int":
                value = int(raw_value)

            elif parameter_type == "float":
                value = float(raw_value)

            elif parameter_type == "bool":
                if isinstance(raw_value, bool):
                    value = raw_value

                elif isinstance(raw_value, str):
                    normalized = (
                        raw_value
                        .strip()
                        .lower()
                    )

                    if normalized in {
                        "true",
                        "1",
                        "yes",
                        "on",
                    }:
                        value = True

                    elif normalized in {
                        "false",
                        "0",
                        "no",
                        "off",
                    }:
                        value = False

                    else:
                        raise ValueError(
                            f"Invalid boolean value "
                            f"'{raw_value}'."
                        )

                else:
                    value = bool(raw_value)

            elif parameter_type == "str":
                value = str(raw_value)

            else:
                value = raw_value

        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid value for '{name}'. "
                f"Expected {parameter_type or 'a valid value'}."
            ) from exc

        # Minimum
        if "min" in config:
            if value < config["min"]:
                raise ValueError(
                    f"'{name}' must be at least "
                    f"{config['min']}."
                )

        # Maximum
        if "max" in config:
            if value > config["max"]:
                raise ValueError(
                    f"'{name}' must be at most "
                    f"{config['max']}."
                )

        # Allowed values
        if "choices" in config:
            if value not in config["choices"]:
                raise ValueError(
                    f"'{name}' must be one of: "
                    + ", ".join(
                        str(choice)
                        for choice
                        in config["choices"]
                    )
                )

        validated[name] = value

    return validated


def discover_editable_tasks() -> list[dict]:
    """
    Discover all Airflow tasks explicitly exposed
    using @editable.
    """

    dag_bag = DagBag(
        include_examples=False
    )

    editable_tasks = []

    for dag_id, dag in dag_bag.dags.items():
        dag_file = Path(dag.fileloc)

        if not dag_file.exists():
            continue

        try:
            source = dag_file.read_text()
            tree = ast.parse(source)

        except Exception:
            continue

        editable_functions = set()

        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                if _is_task_studio_editable(
                    node
                ):
                    editable_functions.add(
                        node.name
                    )

        if not editable_functions:
            continue

        for task in dag.tasks:
            if task.task_id not in editable_functions:
                continue

            editable_tasks.append(
                {
                    "dag_id": dag_id,
                    "task_id": task.task_id,
                    "file": str(dag_file),
                }
            )

    editable_tasks.sort(
        key=lambda item: (
            item["dag_id"],
            item["task_id"],
        )
    )

    return editable_tasks
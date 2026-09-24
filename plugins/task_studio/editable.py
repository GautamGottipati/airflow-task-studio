from functools import wraps
import inspect
from typing import Any, Callable

from airflow.sdk import (
    Variable,
    get_current_context,
)

from task_studio.runtime_store import (
    record_consumption,
)


PREFIX = "task_studio_override"


def _override_key(
    dag_id: str,
    task_id: str,
) -> str:
    """
    Build the same Variable key used by the
    Task Studio API.
    """
    return (
        f"{PREFIX}__"
        f"{dag_id}__"
        f"{task_id}"
    )


def _coerce_value(
    value: Any,
    annotation: Any,
) -> Any:
    """
    Convert a stored override into the type
    declared by the task function.
    """

    if annotation is inspect._empty:
        return value

    if value is None:
        return None

    if annotation is int:
        return int(value)

    if annotation is float:
        return float(value)

    if annotation is str:
        return str(value)

    if annotation is bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            normalized = (
                value
                .strip()
                .lower()
            )

            if normalized in {
                "true",
                "1",
                "yes",
                "on",
            }:
                return True

            if normalized in {
                "false",
                "0",
                "no",
                "off",
            }:
                return False

            raise ValueError(
                f"Invalid boolean value: "
                f"{value!r}"
            )

        return bool(value)

    return value


def _validate_value(
    name: str,
    value: Any,
    config: dict,
) -> None:
    """
    Revalidate an override at task runtime.

    The API already validates before storing
    the override. This provides defense in depth.
    """

    if config.get("editable", True) is False:
        raise ValueError(
            f"Task Studio parameter '{name}' "
            f"is not editable."
        )

    if (
        "min" in config
        and value < config["min"]
    ):
        raise ValueError(
            f"Task Studio override '{name}' "
            f"must be >= {config['min']}. "
            f"Got {value}."
        )

    if (
        "max" in config
        and value > config["max"]
    ):
        raise ValueError(
            f"Task Studio override '{name}' "
            f"must be <= {config['max']}. "
            f"Got {value}."
        )

    if "choices" in config:
        if value not in config["choices"]:
            raise ValueError(
                f"Task Studio override '{name}' "
                f"must be one of "
                f"{config['choices']}. "
                f"Got {value!r}."
            )


def editable(
    _func: Callable | None = None,
    *,
    fields: dict[str, dict] | None = None,
):
    """
    Mark an Airflow task as editable by
    Task Studio.

    Basic usage:

        @editable

    Optional configuration:

        @editable(
            fields={
                "batch_size": {
                    "min": 100,
                    "max": 50000,
                },
                "target": {
                    "choices": [
                        "snowflake",
                        "postgres",
                        "bigquery",
                    ],
                },
            }
        )

    All parameters are editable by default.

    Disable a parameter with:

        "editable": False
    """

    def decorator(
        func: Callable,
    ):
        signature = inspect.signature(
            func
        )

        field_config = fields or {}

        #
        # Validate developer configuration
        # during DAG parsing.
        #
        for field_name in field_config:
            if (
                field_name
                not in signature.parameters
            ):
                raise ValueError(
                    f"Task Studio field "
                    f"'{field_name}' does not "
                    f"exist in function "
                    f"'{func.__name__}'."
                )

        @wraps(func)
        def wrapper(
            *args,
            **kwargs,
        ):
            #
            # -------------------------------------------------
            # AIRFLOW EXECUTION CONTEXT
            # -------------------------------------------------
            #
            context = get_current_context()

            task_instance = context.get(
                "task_instance"
            )

            if task_instance is not None:
                dag_id = (
                    task_instance.dag_id
                )

                task_id = (
                    task_instance.task_id
                )

                #
                # Execution identity.
                #
                run_id = getattr(
                    task_instance,
                    "run_id",
                    None,
                )

                try_number = getattr(
                    task_instance,
                    "try_number",
                    None,
                )

                map_index = getattr(
                    task_instance,
                    "map_index",
                    None,
                )

            else:
                #
                # Fallback for execution contexts
                # where task_instance is not
                # available.
                #
                dag_id = (
                    context["dag"].dag_id
                )

                task_id = (
                    context["task"].task_id
                )

                run_id = context.get(
                    "run_id"
                )

                try_number = None
                map_index = None

            #
            # -------------------------------------------------
            # LOAD PENDING OVERRIDE
            # -------------------------------------------------
            #
            # IMPORTANT:
            #
            # airflow.sdk.Variable is used here.
            # The running task does NOT access
            # Airflow's metadata DB via ORM.
            #
            key = _override_key(
                dag_id=dag_id,
                task_id=task_id,
            )

            override = Variable.get(
                key,
                default=None,
                deserialize_json=True,
            )

            #
            # -------------------------------------------------
            # BIND ORIGINAL TASK ARGUMENTS
            # -------------------------------------------------
            #
            bound = signature.bind_partial(
                *args,
                **kwargs,
            )

            bound.apply_defaults()

            #
            # -------------------------------------------------
            # APPLY TASK STUDIO OVERRIDE
            # -------------------------------------------------
            #
            if override:
                values = override.get(
                    "values",
                    {},
                )

                for (
                    name,
                    raw_value,
                ) in values.items():

                    #
                    # Ignore parameters that no
                    # longer exist in the DAG.
                    #
                    if (
                        name
                        not in
                        signature.parameters
                    ):
                        continue

                    config = (
                        field_config.get(
                            name,
                            {},
                        )
                    )

                    #
                    # Explicitly non-editable
                    # parameter.
                    #
                    if (
                        config.get(
                            "editable",
                            True,
                        )
                        is False
                    ):
                        raise ValueError(
                            f"Task Studio "
                            f"parameter '{name}' "
                            f"is not editable."
                        )

                    parameter = (
                        signature
                        .parameters[name]
                    )

                    #
                    # Convert the incoming value
                    # into the function's declared
                    # type.
                    #
                    value = _coerce_value(
                        raw_value,
                        parameter.annotation,
                    )

                    #
                    # Revalidate constraints at
                    # execution time.
                    #
                    _validate_value(
                        name=name,
                        value=value,
                        config=config,
                    )

                    #
                    # Change only this execution's
                    # bound argument.
                    #
                    bound.arguments[name] = (
                        value
                    )

            #
            # -------------------------------------------------
            # EXECUTE ORIGINAL TASK
            # -------------------------------------------------
            #
            # IMPORTANT:
            #
            # Anything after this line executes
            # only if the task function succeeds.
            #
            # If func() raises:
            #
            #   - override remains pending
            #   - no consumption acknowledgement
            #   - retry can use the override again
            #
            result = func(
                *bound.args,
                **bound.kwargs,
            )

            #
            # -------------------------------------------------
            # EDIT ONCE CONSUMPTION
            # -------------------------------------------------
            #
            if (
                override
                and override.get(
                    "scope"
                ) == "next_run"
            ):
                values = override.get(
                    "values",
                    {},
                )

                #
                # Record WHICH Airflow execution
                # successfully used this override.
                #
                # This happens before deleting the
                # pending override.
                #
                override_id = override.get(
                    "override_id"
                )

                if override_id:
                    record_consumption(
                        override_id=override_id,
                        dag_id=dag_id,
                        task_id=task_id,
                        run_id=(
                            str(run_id)
                            if run_id is not None
                            else "unknown"
                        ),
                        try_number=try_number,
                        map_index=map_index,
                        values=values,
                    )

                Variable.delete(key)

                #
                # The override is Edit Once, so
                # remove it after successful use.
                #
                Variable.delete(key)

            return result

        #
        # -------------------------------------------------
        # TASK STUDIO METADATA
        # -------------------------------------------------
        #
        wrapper.__task_studio_editable__ = (
            True
        )

        wrapper.__task_studio_fields__ = (
            field_config
        )

        return wrapper

    #
    # Support:
    #
    #     @editable
    #
    # and:
    #
    #     @editable(...)
    #
    if _func is not None:
        return decorator(_func)

    return decorator
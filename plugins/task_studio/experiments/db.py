from airflow import settings

from plugins.task_studio.experiments.override_model import (
    TaskStudioOverride,
)


def initialize_task_studio_db() -> None:
    """
    Hackathon/dev initialization.

    Before packaging Task Studio for production,
    this should become a proper migration.
    """

    TaskStudioOverride.__table__.create(
        bind=settings.engine,
        checkfirst=True,
    )
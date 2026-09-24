from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    String,
)

from airflow.models.base import Base


class TaskStudioOverride(Base):
    """
    Stores Task Studio overrides and their lifecycle.

    Lifecycle:

        pending
            ↓
        claimed
            ↓
        consumed

    Or:

        pending
            ↓
        cancelled
    """

    __tablename__ = "task_studio_override"

    # Internal database primary key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Public identifier for the override
    override_id = Column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
    )

    # Airflow DAG
    dag_id = Column(
        String(250),
        nullable=False,
        index=True,
    )

    # Airflow task
    task_id = Column(
        String(250),
        nullable=False,
        index=True,
    )

    # For now:
    # next_run
    #
    # Later we can support:
    # current_run
    # specific_run
    scope = Column(
        String(50),
        nullable=False,
        default="next_run",
    )

    # Lifecycle:
    #
    # pending
    # claimed
    # consumed
    # cancelled
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    # Example:
    #
    # {
    #     "batch_size": 20000,
    #     "target": "bigquery"
    # }
    values = Column(
        JSON,
        nullable=False,
    )

    # When Task Studio created the override
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    # DAG run that successfully claimed
    # this override
    claimed_by_run_id = Column(
        String(500),
        nullable=True,
        index=True,
    )

    # When a DAG run claimed it
    claimed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # When the task finished consuming it
    consumed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # When a user cancelled it
    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    def to_dict(self) -> dict:
        """
        Convert the SQLAlchemy model into a
        JSON-serializable dictionary.
        """

        return {
            "override_id": self.override_id,
            "dag_id": self.dag_id,
            "task_id": self.task_id,
            "scope": self.scope,
            "status": self.status,
            "values": self.values,

            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),

            "claimed_by_run_id": (
                self.claimed_by_run_id
            ),

            "claimed_at": (
                self.claimed_at.isoformat()
                if self.claimed_at
                else None
            ),

            "consumed_at": (
                self.consumed_at.isoformat()
                if self.consumed_at
                else None
            ),

            "cancelled_at": (
                self.cancelled_at.isoformat()
                if self.cancelled_at
                else None
            ),
        }
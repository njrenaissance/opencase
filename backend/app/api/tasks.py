"""Task router — submit, list, read, update, and cancel background tasks."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from opentelemetry import trace
from shared.models.base import MessageResponse
from shared.models.enums import Role, TaskState
from shared.models.task import (
    SubmitTaskRequest,
    TaskResponse,
    TaskSubmitResponse,
    TaskSummary,
    UpdateTaskRequest,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.permissions import require_role
from app.db import get_db
from app.db.models.task_submission import TaskSubmission
from app.db.models.user import User
from app.workers.broker import TaskBroker, get_task_broker
from app.workers.registry import TASK_REGISTRY

tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _submission_to_summary(sub: TaskSubmission) -> TaskSummary:
    return TaskSummary(
        id=sub.id,
        task_name=sub.task_name,
        status=TaskState(sub.status),
        submitted_at=sub.submitted_at,
        submitted_by=sub.user_id,
    )


def _submission_to_response(
    sub: TaskSubmission,
    *,
    status: str | None = None,
    result: Any = None,
    date_done: datetime | None = None,
    traceback: str | None = None,
) -> TaskResponse:
    return TaskResponse(
        id=sub.id,
        task_name=sub.task_name,
        status=TaskState(status or sub.status),
        submitted_at=sub.submitted_at,
        submitted_by=sub.user_id,
        firm_id=sub.firm_id,
        args=json.loads(sub.args_json),
        kwargs=json.loads(sub.kwargs_json),
        result=result,
        date_done=date_done,
        traceback=traceback,
    )


# ---------------------------------------------------------------------------
# POST /tasks/
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {}},
)
async def submit_task(
    body: SubmitTaskRequest,
    user: User = Depends(require_role(Role.admin, Role.attorney)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    broker: TaskBroker = Depends(get_task_broker),  # noqa: B008
) -> TaskSubmitResponse:
    with tracer.start_as_current_span(
        "tasks.submit",
        attributes={"user.id": str(user.id), "task.name": body.task_name},
    ):
        celery_name = TASK_REGISTRY.get(body.task_name)
        if celery_name is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown task: {body.task_name}",
            )

        task_id = await asyncio.to_thread(
            broker.submit, celery_name, body.args, body.kwargs
        )

        sub = TaskSubmission(
            id=task_id,
            firm_id=user.firm_id,
            user_id=user.id,
            task_name=body.task_name,
            args_json=json.dumps(body.args),
            kwargs_json=json.dumps(body.kwargs),
            status=TaskState.pending,
        )
        db.add(sub)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            await asyncio.to_thread(broker.revoke, task_id, terminate=True)
            raise
        return TaskSubmitResponse(task_id=task_id)


# ---------------------------------------------------------------------------
# GET /tasks/
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[TaskSummary])
async def list_tasks(
    task_status: TaskState | None = Query(None, alias="status"),  # noqa: B008
    task_name: str | None = Query(None),
    submitted_after: datetime | None = Query(None),  # noqa: B008
    submitted_before: datetime | None = Query(None),  # noqa: B008
    limit: int = Query(100, ge=1, le=1000),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[TaskSummary]:
    with tracer.start_as_current_span(
        "tasks.list",
        attributes={"user.id": str(user.id)},
    ):
        stmt = select(TaskSubmission).where(TaskSubmission.firm_id == user.firm_id)

        if task_status is not None:
            stmt = stmt.where(TaskSubmission.status == task_status)
        if task_name is not None:
            stmt = stmt.where(TaskSubmission.task_name == task_name)
        if submitted_after is not None:
            stmt = stmt.where(TaskSubmission.submitted_at >= submitted_after)
        if submitted_before is not None:
            stmt = stmt.where(TaskSubmission.submitted_at <= submitted_before)

        stmt = stmt.order_by(TaskSubmission.submitted_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await db.execute(stmt)
        return [_submission_to_summary(s) for s in result.scalars().all()]


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}
# ---------------------------------------------------------------------------


@router.get("/{task_id}", response_model=TaskResponse, responses={404: {}})
async def get_task(
    task_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    broker: TaskBroker = Depends(get_task_broker),  # noqa: B008
) -> TaskResponse:
    with tracer.start_as_current_span(
        "tasks.get",
        attributes={"user.id": str(user.id), "task.id": task_id},
    ):
        stmt = select(TaskSubmission).where(
            TaskSubmission.id == task_id,
            TaskSubmission.firm_id == user.firm_id,
        )
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        # Enrich with live Celery status
        live = await asyncio.to_thread(broker.get_status, task_id)

        # Update denormalized status if changed
        if live.state != sub.status:
            sub.status = live.state
            await db.commit()

        return _submission_to_response(
            sub,
            status=live.state,
            result=live.result,
            date_done=live.date_done,
            traceback=live.traceback,
        )


# ---------------------------------------------------------------------------
# PUT /tasks/{task_id}  (scaffold)
# ---------------------------------------------------------------------------


@router.put("/{task_id}", response_model=TaskResponse, responses={404: {}})
async def update_task(
    task_id: str,
    body: UpdateTaskRequest,  # noqa: ARG001
    user: User = Depends(require_role(Role.admin)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    broker: TaskBroker = Depends(get_task_broker),  # noqa: B008
) -> TaskResponse:
    with tracer.start_as_current_span(
        "tasks.update",
        attributes={"user.id": str(user.id), "task.id": task_id},
    ):
        stmt = select(TaskSubmission).where(
            TaskSubmission.id == task_id,
            TaskSubmission.firm_id == user.firm_id,
        )
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        live = await asyncio.to_thread(broker.get_status, task_id)
        return _submission_to_response(
            sub,
            status=live.state,
            result=live.result,
            date_done=live.date_done,
            traceback=live.traceback,
        )


# ---------------------------------------------------------------------------
# DELETE /tasks/{task_id}
# ---------------------------------------------------------------------------


@router.delete("/{task_id}", response_model=MessageResponse, responses={404: {}})
async def cancel_task(
    task_id: str,
    user: User = Depends(require_role(Role.admin)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    broker: TaskBroker = Depends(get_task_broker),  # noqa: B008
) -> MessageResponse:
    with tracer.start_as_current_span(
        "tasks.cancel",
        attributes={"user.id": str(user.id), "task.id": task_id},
    ):
        stmt = select(TaskSubmission).where(
            TaskSubmission.id == task_id,
            TaskSubmission.firm_id == user.firm_id,
        )
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        await asyncio.to_thread(broker.revoke, task_id, terminate=False)

        sub.status = TaskState.revoked
        await db.commit()
        return MessageResponse(detail="Task revoked")

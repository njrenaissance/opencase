"""Unit tests for task CRUD API endpoints.

Uses AsyncClient + in-memory overrides via shared FakeSession / api_client
from conftest.py.  TaskBroker is replaced with a fake via dependency override.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from shared.models.enums import Role, TaskState

from app.workers.broker import TaskStatusResult, get_task_broker
from tests.conftest import FakeSession, api_client, auth_header
from tests.factories import make_task_submission, make_user

# ---------------------------------------------------------------------------
# Fake broker
# ---------------------------------------------------------------------------

_FAKE_TASK_ID = str(uuid.uuid4())


class FakeBroker:
    """Stand-in for TaskBroker that records calls."""

    def __init__(
        self,
        task_id: str = _FAKE_TASK_ID,
        state: str = TaskState.pending,
        result: object = None,
    ) -> None:
        self.task_id = task_id
        self.state = state
        self.result = result
        self.submitted: list[tuple[str, list, dict]] = []
        self.revoked: list[str] = []

    def submit(self, celery_name: str, args: list, kwargs: dict) -> str:
        self.submitted.append((celery_name, args, kwargs))
        return self.task_id

    def get_status(self, task_id: str) -> TaskStatusResult:
        return TaskStatusResult(
            state=self.state,
            result=self.result,
            date_done=datetime.now(UTC) if self.state == TaskState.success else None,
            traceback=None,
        )

    def revoke(self, task_id: str, *, terminate: bool = False) -> None:
        self.revoked.append(task_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIRM_ID = uuid.uuid4()
_NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# POST /tasks/
# ---------------------------------------------------------------------------


class TestSubmitTask:
    @pytest.mark.asyncio
    async def test_submit_returns_201(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        broker = FakeBroker()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: broker
            resp = await ac.post(
                "/tasks/",
                json={"task_name": "ping"},
                headers=auth_header(user),
            )
        assert resp.status_code == 201
        assert resp.json()["task_id"] == broker.task_id
        assert len(broker.submitted) == 1
        assert broker.submitted[0][0] == "gideon.ping"

    @pytest.mark.asyncio
    async def test_submit_unknown_task_returns_400(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        broker = FakeBroker()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: broker
            resp = await ac.post(
                "/tasks/",
                json={"task_name": "nonexistent"},
                headers=auth_header(user),
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", [Role.paralegal, Role.investigator])
    async def test_submit_forbidden_for_restricted_roles(self, role: Role) -> None:
        user = make_user(firm_id=_FIRM_ID, role=role)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: FakeBroker()
            resp = await ac.post(
                "/tasks/",
                json={"task_name": "ping"},
                headers=auth_header(user),
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_attorney_can_submit(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        broker = FakeBroker()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: broker
            resp = await ac.post(
                "/tasks/",
                json={"task_name": "ping"},
                headers=auth_header(user),
            )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# GET /tasks/
# ---------------------------------------------------------------------------


class TestListTasks:
    @pytest.mark.asyncio
    async def test_list_returns_tasks(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        sub = make_task_submission(firm_id=_FIRM_ID, user_id=user.id)
        fake = FakeSession()
        fake.add_results_list([sub])
        async with api_client(user, fake) as ac:
            resp = await ac.get("/tasks/", headers=auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["task_name"] == "ping"

    @pytest.mark.asyncio
    async def test_list_empty(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake.add_results_list([])
        async with api_client(user, fake) as ac:
            resp = await ac.get("/tasks/", headers=auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}
# ---------------------------------------------------------------------------


class TestGetTask:
    @pytest.mark.asyncio
    async def test_get_returns_detail(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        sub = make_task_submission(firm_id=_FIRM_ID, user_id=user.id)
        fake = FakeSession()
        fake.add_result(sub)
        broker = FakeBroker(state=TaskState.success, result="pong")
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: broker
            resp = await ac.get(f"/tasks/{sub.id}", headers=auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == TaskState.success
        assert data["result"] == "pong"

    @pytest.mark.asyncio
    async def test_get_not_found(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        broker = FakeBroker()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: broker
            resp = await ac.get(f"/tasks/{uuid.uuid4()}", headers=auth_header(user))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /tasks/{task_id}  (scaffold)
# ---------------------------------------------------------------------------


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_update_returns_200(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        sub = make_task_submission(firm_id=_FIRM_ID, user_id=user.id)
        fake = FakeSession()
        fake.add_result(sub)
        broker = FakeBroker(state=TaskState.pending)
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: broker
            resp = await ac.put(f"/tasks/{sub.id}", json={}, headers=auth_header(user))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_forbidden_for_non_admin(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: FakeBroker()
            resp = await ac.put(
                f"/tasks/{uuid.uuid4()}", json={}, headers=auth_header(user)
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /tasks/{task_id}
# ---------------------------------------------------------------------------


class TestCancelTask:
    @pytest.mark.asyncio
    async def test_cancel_returns_200(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        sub = make_task_submission(firm_id=_FIRM_ID, user_id=user.id)
        fake = FakeSession()
        fake.add_result(sub)
        broker = FakeBroker()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: broker
            resp = await ac.delete(f"/tasks/{sub.id}", headers=auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Task revoked"
        assert sub.id in broker.revoked

    @pytest.mark.asyncio
    async def test_cancel_forbidden_for_non_admin(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: FakeBroker()
            resp = await ac.delete(f"/tasks/{uuid.uuid4()}", headers=auth_header(user))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_cancel_not_found(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        broker = FakeBroker()
        async with api_client(user, fake) as ac:
            from app.main import app

            app.dependency_overrides[get_task_broker] = lambda: broker
            resp = await ac.delete(f"/tasks/{uuid.uuid4()}", headers=auth_header(user))
        assert resp.status_code == 404

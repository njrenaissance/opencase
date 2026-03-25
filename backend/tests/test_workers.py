"""Smoke tests for Celery app and task registration.

These catch import errors and misconfiguration before integration tests
spin up the full Docker stack.
"""

from celery import Celery

from app.core.config import settings


def test_celery_app_is_importable():
    """Celery app module loads without error."""
    from app.workers import celery_app

    assert isinstance(celery_app, Celery)


def test_celery_broker_url_matches_settings():
    from app.workers import celery_app

    assert celery_app.conf.broker_url == settings.celery.broker_url


def test_celery_result_backend_matches_settings():
    from app.workers import celery_app

    assert celery_app.conf.result_backend == settings.celery.result_backend


def test_ping_task_is_registered():
    """Task module is discoverable and registers with the Celery app."""
    # Import the task module to trigger shared_task registration.
    import app.workers.tasks.ping  # noqa: F401
    from app.workers import celery_app

    assert "opencase.ping" in celery_app.tasks


def test_ping_task_returns_pong():
    """Calling the task function directly returns 'pong'."""
    from app.workers.tasks.ping import ping

    assert ping() == "pong"

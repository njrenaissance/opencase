"""Unit tests for application logging configuration."""

import logging
import os
import sys

import pytest

from app.core.logging import setup_logging


@pytest.fixture(autouse=True)
def _reset_app_logger():
    """Remove handlers from the app logger between tests."""
    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    yield
    app_logger.handlers.clear()
    app_logger.setLevel(logging.WARNING)


def test_sets_level_debug():
    setup_logging("DEBUG")
    assert logging.getLogger("app").level == logging.DEBUG


def test_sets_level_warning():
    setup_logging("WARNING")
    assert logging.getLogger("app").level == logging.WARNING


def test_child_logger_inherits_level():
    setup_logging("DEBUG")
    child = logging.getLogger("app.api.health")
    assert child.getEffectiveLevel() == logging.DEBUG


def test_default_handler_outputs_to_stdout():
    setup_logging("INFO")
    handlers = logging.getLogger("app").handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)
    assert handlers[0].stream is sys.stdout


def test_handler_outputs_to_stderr():
    setup_logging("INFO", output="stderr")
    handlers = logging.getLogger("app").handlers
    assert len(handlers) == 1
    assert handlers[0].stream is sys.stderr


def test_idempotent_no_duplicate_handlers():
    setup_logging("INFO")
    setup_logging("INFO")
    assert len(logging.getLogger("app").handlers) == 1


def test_quiets_noisy_loggers():
    setup_logging("DEBUG")
    assert logging.getLogger("uvicorn.access").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def _clear_opencase_env(monkeypatch):
    """Strip all OPENCASE_ env vars, then re-set required ones."""
    for key in list(os.environ):
        if key.startswith("OPENCASE_"):
            monkeypatch.delenv(key, raising=False)
    # Required fields that have no defaults:
    monkeypatch.setenv("OPENCASE_AUTH_SECRET_KEY", "test")
    monkeypatch.setenv("OPENCASE_DB_URL", "postgresql+asyncpg://u:p@h/db")


def test_log_level_config_default(monkeypatch):
    _clear_opencase_env(monkeypatch)
    from app.core.config import Settings

    cfg = Settings()
    assert cfg.log_level == "INFO"


def test_log_level_config_from_env(monkeypatch):
    _clear_opencase_env(monkeypatch)
    monkeypatch.setenv("OPENCASE_LOG_LEVEL", "DEBUG")
    from app.core.config import Settings

    cfg = Settings()
    assert cfg.log_level == "DEBUG"

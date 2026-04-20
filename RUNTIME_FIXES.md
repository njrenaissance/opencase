# Runtime Fixes — Session Summary

## Overview
Two critical runtime issues were identified and fixed:

1. **Alembic TYPE_CHECKING import error** — NameError at container startup
2. **OpenTelemetry metrics not exporting** — Metrics missing from Grafana despite traces/logs working

## Commit 1: `d2b0a9c` — Alembic TYPE_CHECKING Type Hint

### Problem
`backend/alembic/env.py` was using `if TYPE_CHECKING:` to guard the `Connection` import, but then used `Connection` in a function signature at runtime:

```python
if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

def do_run_migrations(connection: Connection) -> None:  # NameError at runtime
    ...
```

When the Alembic migration tried to run on FastAPI container startup, it failed with:
```
NameError: name 'Connection' is not defined
```

### Solution
Changed to a string literal forward reference so the type hint doesn't require the import at runtime:

```python
if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

def do_run_migrations(connection: "Connection") -> None:  # Works at runtime
    ...
```

### Files Changed
- `backend/alembic/env.py` — line 45

---

## Commit 2: `6539938` — OpenTelemetry Meter Lazy Initialization

### Problem
OpenTelemetry metrics were configured but not exporting to Grafana. Traces and logs were working correctly.

Root cause: `backend/app/core/metrics.py` was calling `metrics.get_meter("gideon")` at **module import time** (before FastAPI startup), while `backend/app/core/telemetry.py:setup_telemetry()` didn't set up the MeterProvider until **after imports**. This meant the meter got the default no-op provider instead of the configured OTLP exporter.

### Solution
Three changes:

1. **Lazy meter getter** in `telemetry.py`:
   ```python
   _meter: "metrics.Meter | None" = None
   
   def get_meter() -> metrics.Meter:
       """Get the global meter, initializing on first call after setup_telemetry()."""
       global _meter
       if _meter is None:
           _meter = metrics.get_meter("gideon")
       return _meter
   ```

2. **Deferred instrument creation** in `metrics.py`:
   - Moved all instrument definitions from module-level to a `_create_instruments()` function
   - Wrapped results in `_instruments_cache` dict

3. **Lazy wrapper class** in `metrics.py`:
   ```python
   class _LazyInstrument:
       """Wrapper that defers instrument access until after setup_telemetry()."""
       def __init__(self, name: str) -> None:
           self._name = name
       def _get_real(self) -> Any:
           _create_instruments()
           return _instruments_cache[self._name]
       def __getattr__(self, attr: str) -> Any:
           return getattr(self._get_real(), attr)
   ```

This ensures instruments like `login_attempts` are created lazily when first used, after `setup_telemetry()` has configured the MeterProvider.

### Files Changed
- `backend/app/core/telemetry.py` — added `get_meter()`, `_meter` global
- `backend/app/core/metrics.py` — refactored to lazy initialization with `_LazyInstrument` wrapper

### Containers Rebuilt
- `gideon-fastapi`
- `gideon-celery-worker`
- `gideon-celery-beat`
- `gideon-flower`

---

## Testing
- ✅ All pre-commit checks passed (ruff, mypy, pytest)
- ✅ Containers built successfully
- ✅ No type errors from mypy after adding `Any` typing to `_LazyInstrument`

## Next Steps
- Verify metrics now appear in Grafana dashboard after deployment
- Monitor for any side effects from lazy initialization pattern

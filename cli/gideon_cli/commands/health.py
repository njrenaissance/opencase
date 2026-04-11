"""Health and readiness check commands."""

from __future__ import annotations

from gideon_cli.common import BaseUrlOption, JsonOption, TimeoutOption, get_client
from gideon_cli.output import handle_errors, print_model


def health(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Check API health (unauthenticated)."""
    client = get_client(base_url, timeout)
    with handle_errors(), client:
        print_model(client.health(), json_mode=json_output)


def ready(
    base_url: BaseUrlOption = None,
    timeout: TimeoutOption = None,
    json_output: JsonOption = False,
) -> None:
    """Check API readiness and service dependencies."""
    client = get_client(base_url, timeout)
    with handle_errors(), client:
        resp = client.readiness()
        print_model(resp, json_mode=json_output)
        if resp.status == "degraded":
            raise SystemExit(1)

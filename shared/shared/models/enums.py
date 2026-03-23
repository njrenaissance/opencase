"""Shared enums used by API, SDK, and database models."""

import enum


class Role(enum.StrEnum):
    admin = "admin"
    attorney = "attorney"
    paralegal = "paralegal"
    investigator = "investigator"


class MatterStatus(enum.StrEnum):
    open = "open"
    closed = "closed"
    archived = "archived"

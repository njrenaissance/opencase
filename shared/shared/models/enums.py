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


class DocumentSource(enum.StrEnum):
    government_production = "government_production"
    defense = "defense"
    court = "court"
    work_product = "work_product"


class Classification(enum.StrEnum):
    brady = "brady"
    giglio = "giglio"
    jencks = "jencks"
    rule16 = "rule16"
    work_product = "work_product"
    inculpatory = "inculpatory"
    unclassified = "unclassified"

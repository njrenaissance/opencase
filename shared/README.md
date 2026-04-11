# gideon-shared

Shared Pydantic models and enums for the Gideon API and SDK.

This package has minimal dependencies (`pydantic[email]` only) so it can be
imported by both the FastAPI backend and the lightweight Python SDK without
pulling in server-side dependencies.

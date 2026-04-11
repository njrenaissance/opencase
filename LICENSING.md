# Third-Party Licenses

Gideon is licensed under [Apache 2.0](LICENSE). This
document inventories the licenses of all third-party
components used by the project.

All directly-linked Python dependencies use permissive
licenses (MIT, BSD, Apache 2.0). Components with
copyleft licenses (AGPL, LGPL) are either isolated
network services or dynamically-linked C extensions,
neither of which imposes obligations on the Gideon
source code. See the
[compatibility analysis](#license-compatibility-analysis)
for details.

**Last updated:** 2026-03-28
**Source:** `uv.lock`, `backend/pyproject.toml`,
`infrastructure/docker-compose.yml`

---

## Infrastructure Services

These run as separate Docker containers, accessed over
TCP/HTTP. Gideon never links against their source code.

| Component | Image | License | SPDX |
| --- | --- | --- | --- |
| PostgreSQL | `postgres:17-alpine` | PostgreSQL License | `PostgreSQL` |
| Redis | `redis:7-alpine` | BSD-3-Clause / RSALv2+SSPLv1 | See note below |
| MinIO | `minio/minio:latest` | AGPL-3.0 | `AGPL-3.0-or-later` |
| MinIO Client | `minio/mc:latest` | AGPL-3.0 | `AGPL-3.0-or-later` |
| Ollama | `ollama/ollama:latest` | MIT | `MIT` |
| Qdrant | `qdrant/qdrant:latest` | Apache 2.0 | `Apache-2.0` |
| Grafana OTEL-LGTM | `grafana/otel-lgtm:latest` | AGPL-3.0 | `AGPL-3.0-or-later` |

**Redis licensing note.** Redis changed its server
license from BSD-3-Clause to RSALv2 + SSPLv1 starting
with version 7.4. The `redis:7-alpine` tag is a moving
target and may resolve to 7.4+. Regardless, Redis is
used as a standalone network service (Celery broker and
cache). Neither RSALv2 nor SSPL restricts the license of
applications that merely connect to Redis over the
network. The Python `redis` client library remains MIT.

---

## Container Base Images

| Image | License | Usage |
| --- | --- | --- |
| `python:3.12-slim` | PSF-2.0 + Debian free software | build / runtime |
| `node:22-slim` | MIT + Debian free software | build / runtime (planned) |
| `ghcr.io/astral-sh/uv:latest` | MIT | build (package installer) |

---

## Python Runtime Dependencies

Packages listed in `backend/pyproject.toml` under
`dependencies`. Versions resolved from `uv.lock`.

| Package | Version | License | SPDX |
| --- | --- | --- | --- |
| FastAPI | 0.135.1 | MIT | `MIT` |
| Uvicorn | 0.42.0 | BSD-3-Clause | `BSD-3-Clause` |
| Pydantic | 2.12.5 | MIT | `MIT` |
| pydantic-settings | 2.13.1 | MIT | `MIT` |
| SQLAlchemy | 2.0.48 | MIT | `MIT` |
| Alembic | 1.18.4 | MIT | `MIT` |
| asyncpg | 0.31.0 | Apache 2.0 | `Apache-2.0` |
| psycopg2-binary | 2.9.11 | LGPL-3.0 | `LGPL-3.0-or-later` |
| Celery | 5.6.2 | BSD-3-Clause | `BSD-3-Clause` |
| redis (Python) | 6.4.0 | MIT | `MIT` |
| LangChain | 1.2.13 | MIT | `MIT` |
| langchain-community | 0.4.1 | MIT | `MIT` |
| langchain-ollama | 1.0.1 | MIT | `MIT` |
| qdrant-client | 1.17.1 | Apache 2.0 | `Apache-2.0` |
| minio (Python) | 7.2.20 | Apache 2.0 | `Apache-2.0` |
| python-jose | 3.5.0 | MIT | `MIT` |
| passlib | 1.7.4 | BSD-3-Clause | `BSD-3-Clause` |
| PyOTP | 2.9.0 | MIT | `MIT` |
| cryptography | 46.0.5 | Apache 2.0 / BSD-3-Clause | `Apache-2.0 OR BSD-3-Clause` |
| python-multipart | 0.0.22 | Apache 2.0 | `Apache-2.0` |

---

## OpenTelemetry Stack

All OpenTelemetry packages are Apache 2.0.

| Package | Version |
| --- | --- |
| opentelemetry-api | 1.40.0 |
| opentelemetry-sdk | 1.40.0 |
| opentelemetry-instrumentation-fastapi | 0.61b0 |
| opentelemetry-instrumentation-celery | 0.61b0 |
| opentelemetry-instrumentation-sqlalchemy | 0.61b0 |
| opentelemetry-exporter-otlp-proto-http | 1.40.0 |

---

## CLI and SDK Dependencies

| Package | Version | License | Workspace |
| --- | --- | --- | --- |
| Typer | 0.24.1 | MIT | cli |
| Rich | 14.3.3 | MIT | cli |
| tomli-w | 1.2.0 | MIT | cli |
| httpx | 0.28.1 | BSD-3-Clause | sdk |

---

## Monitoring

| Package | Version | License | SPDX |
| --- | --- | --- | --- |
| Flower | 2.0.1 | BSD-3-Clause | `BSD-3-Clause` |

Flower is an optional dependency
(`backend/pyproject.toml [monitoring]`).

---

## Dev and Test Dependencies

These are not shipped in production containers.

| Package | Version | License | Usage |
| --- | --- | --- | --- |
| ruff | 0.15.7 | MIT | linter/formatter |
| mypy | 1.19.1 | MIT | type checker |
| pre-commit | 4.5.1 | MIT | git hooks |
| pytest | 9.0.2 | MIT | test framework |
| pytest-bdd | 8.1.0 | MIT | BDD testing |
| pytest-asyncio | 1.3.0 | Apache 2.0 | async tests |
| pytest-cov | 7.1.0 | MIT | coverage |
| pytest-docker | 3.2.5 | MIT | Docker fixtures |
| pytest-playwright | 0.7.2 | Apache 2.0 | browser tests |
| factory-boy | 3.3.3 | MIT | test fixtures |
| hatchling | 1.29.0 | MIT | build backend |
| hatch | 1.16.5 | MIT | project manager |

---

## LLM Models

Models are downloaded at runtime by the user via Ollama.
Gideon does not distribute any model weights.

| Model | License | Notes |
| --- | --- | --- |
| Llama 3 8B | Meta Llama 3 Community License | Acceptable use policy; 700M MAU threshold |
| Mistral 7B | Apache 2.0 | |
| nomic-embed-text | Apache 2.0 | |

---

## Document Parsing (Planned)

Not yet in the dependency tree. Will be added as Docker
services or Python packages when document ingestion is
implemented.

| Component | License | SPDX |
| --- | --- | --- |
| Apache Tika | Apache 2.0 | `Apache-2.0` |
| Tesseract OCR | Apache 2.0 | `Apache-2.0` |

---

## Frontend (Planned)

The frontend is not yet implemented. These are the
planned dependencies per the architecture spec.

| Component | License | SPDX |
| --- | --- | --- |
| Next.js | MIT | `MIT` |
| React | MIT | `MIT` |

---

## License Compatibility Analysis

### Permissive licenses (no concerns)

MIT, BSD-2-Clause, BSD-3-Clause, Apache 2.0, and the
PostgreSQL License are all permissive and fully
compatible with Apache 2.0 as the project license.
Every directly-linked Python dependency falls into this
category.

### AGPL-3.0 (MinIO, Grafana OTEL-LGTM)

MinIO and Grafana run as **separate network services**
inside their own Docker containers. Gideon communicates
with them exclusively over TCP/HTTP. The AGPL's copyleft
clause triggers when software is "conveyed" or when
users interact with a "modified version" over a network.
Because Gideon does not modify, link against, or
distribute AGPL source code, the copyleft obligation
does not propagate to the Gideon codebase.

### LGPL-3.0 (psycopg2-binary)

`psycopg2-binary` is a C extension dynamically loaded
at runtime as a shared library. The LGPL explicitly
permits dynamic linking without imposing copyleft on
the calling application. Gideon does not modify
psycopg2 source code. The `-binary` wheel bundles
`libpq`, which is PostgreSQL-licensed (permissive).

### Redis server license (RSALv2 + SSPLv1)

If `redis:7-alpine` resolves to Redis 7.4+, the server
is under RSALv2 + SSPLv1. These licenses restrict
offering Redis itself as a managed service but do not
restrict applications that use Redis as an internal
component. Gideon uses Redis solely as a Celery
broker and cache within its own Docker network.

### Meta Llama 3 Community License

Gideon does not distribute Llama 3 model weights.
Users download models themselves via Ollama. The Meta
Llama 3 Community License has an acceptable use policy
and a 700 million monthly active user threshold, neither
of which applies to Gideon's distribution of its own
source code.

### Attribution requirements

Apache 2.0 and BSD licenses require retention of
copyright and license notices. For Python packages
installed via `pip` or `uv`, these notices are preserved
in each package's `dist-info/LICENSE` directory inside
the virtual environment. Docker images carry their own
license terms independently. No additional `NOTICE` file
is required at this time since Gideon does not bundle
or redistribute third-party source code in its own
distribution artifacts.

### Conclusion

**Apache 2.0 is confirmed as a valid license for
Gideon.** All directly-linked dependencies are
permissively licensed. Copyleft components (AGPL, LGPL)
are isolated by architectural boundaries (network
services, dynamic linking) that prevent license
propagation. Model licenses do not apply because
Gideon does not distribute model weights.

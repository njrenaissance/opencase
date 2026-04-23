# BDD Test Structure

Gideon uses Behavior-Driven Development (BDD) for testing. Tests are written
in Gherkin (human-readable) and executed with `pytest-bdd`.

---

## Directory Structure

```text
backend/
└── tests/
    ├── features/
    │   ├── ingestion/
    │   ├── chatbot/
    │   ├── brady_tracker/
    │   ├── document_review/
    │   ├── witness_index/
    │   ├── rbac/
    │   └── audit/
    └── step_defs/
        ├── ingestion/
        ├── chatbot/
        └── ...
```

---

## How It Works

Each `.feature` file describes one MVP feature area in Gherkin syntax:

```gherkin
Feature: Document Ingestion
  Scenario: User uploads a PDF
    Given the user is authenticated
    When the user uploads a PDF file
    Then the document is stored in MinIO
    And the document is hashed with SHA-256
    And the audit log records the upload
```

Step definitions (Python functions) live in matching subdirectories under
`step_defs/` and implement the "Given/When/Then" steps.

---

## Running Tests

```bash
# Run all BDD tests
uv run pytest backend/tests/features/

# Run tests for a specific feature
uv run pytest backend/tests/features/ingestion/

# Run with verbose output
uv run pytest backend/tests/features/ -v
```

---

## Writing New Tests

1. Create a `.feature` file in the appropriate feature directory
2. Write scenarios in Gherkin (human language)
3. Create step definitions in `step_defs/` matching the feature name
4. Implement each step as a Python function with the `@given`, `@when`, `@then` decorators

**Example step definition:**

```python
from pytest_bdd import given, when, then

@given("the user is authenticated")
def authenticated_user(client, user):
    client.headers["Authorization"] = f"Bearer {user.token}"

@when("the user uploads a PDF file")
def upload_pdf(client, tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"PDF content")
    response = client.post("/documents/upload", files={"file": open(pdf_file, "rb")})
    assert response.status_code == 200
    return response.json()["document_id"]

@then("the document is stored in MinIO")
def check_minio_storage(s3_client, document_id):
    assert s3_client.get_object("gideon", f"docs/{document_id}") is not None
```

---

## Best Practices

- **One scenario per behavior** — Don't combine multiple business rules in one scenario
- **Readable Gherkin** — Non-technical stakeholders should understand scenarios
- **Reusable steps** — Share step definitions across scenarios
- **Fast execution** — Use fixtures and mocks, not slow external services
- **Isolation** — Each scenario should set up its own data

---

## See Also

- [Coding Standards — Testing](coding_standards/gideon-essentials.md#testing-standards) — Unit test best practices
- [pytest-bdd Documentation](https://pytest-bdd.readthedocs.io/)

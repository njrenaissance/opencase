# gideon-sdk

Python REST client for the Gideon API, providing a synchronous, type-safe
interface with automatic JWT token management, error mapping, and thread-safe
operations.

## Installation

From the repo root, run:

```bash
uv sync
```

The `gideon-sdk` package is available in the Python environment once the workspace is
synced. Import as:

```python
from gideon import Client, Session
```

## Configuration

The client accepts a base URL pointing to the Gideon FastAPI server:

```python
from gideon import Client

# Basic setup
client = Client(base_url="http://localhost:8000")

# With custom timeout (seconds)
client = Client(base_url="http://localhost:8000", timeout=60.0)
```

The client handles JWT authentication transparently: after `login()`, all
subsequent requests automatically include the JWT and refresh it when needed
(with a 30-second expiry buffer).

## Quick Start

### Basic Authentication Flow

```python
from gideon import Client

client = Client(base_url="http://localhost:8000")

# Authenticate
client.login(email="attorney@firm.com", password="secret")

# Verify access
me = client.get_current_user()
print(f"Logged in as: {me.email} ({me.role})")

# Logout
client.logout()
```

### Working with Matters (Legal Cases)

```python
# List all matters you have access to
matters = client.list_matters()
for matter in matters:
    print(f"Matter: {matter.name} (ID: {matter.id})")

# Get specific matter
matter = client.get_matter(matter_id="<uuid>")
print(f"Status: {matter.status}, Client: {matter.client_id}")

# Create a new matter
new_matter = client.create_matter(
    name="People v. Smith",
    client_id="<client-uuid>"
)
```

### Managing Users

```python
# List firm users
users = client.list_users()
for user in users:
    print(f"{user.email} ({user.role})")

# Create new user
new_user = client.create_user(
    email="newatty@firm.com",
    password="SecurePass123!",
    first_name="Jane",
    last_name="Doe",
    role="attorney"  # admin, attorney, paralegal, investigator
)

# Update user
client.update_user(
    user_id="<uuid>",
    first_name="Janet"
)
```

### Uploading Documents

```python
# Upload a single document
response = client.upload_document(
    file_path="./evidence.pdf",
    matter_id="<matter-uuid>",
    source="defense",  # defense, government_production, court, work_product
    classification="brady",  # brady, giglio, jencks, rule16, work_product, unclassified
    bates_number="SMITH_001"
)
print(f"Uploaded: {response.id}")

# Check for duplicate before upload
file_hash = client.hash_file("./evidence.pdf")
is_duplicate = client.check_duplicate(
    matter_id="<matter-uuid>",
    file_hash=file_hash
)
if not is_duplicate:
    client.upload_document(...)
```

### Submitting Queries

```python
# Submit a question to the AI chatbot
response = client.submit_prompt(
    matter_id="<matter-uuid>",
    query="What Brady material exists in this case?"
)
print(f"Query ID: {response.id}")

# Retrieve prompt results
prompt = client.get_prompt(prompt_id="<uuid>")
print(f"Query: {prompt.query}")
```

### Managing Background Tasks

```python
# Submit a background task
task = client.submit_task(
    task_name="ping",
    args=[],
    kwargs={}
)
print(f"Task ID: {task.id}, Status: {task.status}")

# Monitor task progress
task = client.get_task(task_id="<uuid>")
print(f"Status: {task.status}, Result: {task.result}")

# List tasks with filtering
tasks = client.list_tasks(status="pending")
for task in tasks:
    print(f"{task.task_name}: {task.status}")

# Cancel a task
client.cancel_task(task_id="<uuid>")
```

### Using Context Manager

For automatic login/logout, use the `Session` context manager:

```python
from gideon import Session

with Session(
    base_url="http://localhost:8000",
    email="attorney@firm.com",
    password="secret"
) as client:
    matters = client.list_matters()
    # Token management and logout handled automatically
```

## Core Features

- **Automatic Token Management**: JWT tokens are refreshed transparently with a
  30-second expiry buffer. If a token expires, the client automatically retries
  the request once after refreshing.

- **Type Safety**: All API responses are validated against Pydantic models from
  `gideon-shared`, ensuring type correctness and IDE autocomplete support.

- **Thread Safety**: The internal token manager uses locks to safely handle
  concurrent requests and token refresh across multiple threads.

- **Error Mapping**: HTTP errors are mapped to specific exception types
  (`AuthenticationError`, `AuthorizationError`, `NotFoundError`,
  `ValidationError`, `ServerError`) for precise error handling.

- **Matter-Based Access Control**: All document and prompt operations are
  scoped to a specific matter; the API filters results based on your access
  grants.

- **File Hashing**: Built-in SHA-256 file hashing for duplicate detection before upload.

- **MFA Support**: Complete multi-factor authentication workflow (setup, confirm, disable).

- **Task Queue Integration**: Submit, monitor, and cancel background jobs (ingestion,
  processing, etc.).

## Error Handling

```python
from gideon import Client
from gideon.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    ServerError
)

client = Client(base_url="http://localhost:8000")

try:
    client.login(email="bad@firm.com", password="wrong")
except AuthenticationError as e:
    print(f"Login failed: {e}")

try:
    matters = client.list_matters()
except AuthorizationError as e:
    print(f"Access denied: {e}")
except ServerError as e:
    print(f"API error: {e}")
```

## CLI Alternative

For command-line interaction, see [`../cli/README.md`](../cli/README.md) for the
`gideon` CLI tool, which wraps this SDK and provides shell commands for all operations.

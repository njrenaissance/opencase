# opencase-sdk

Python REST client for the OpenCase API.

## Usage

```python
from opencase import OpenCaseClient

client = OpenCaseClient(base_url="http://localhost:8000")
client.login(email="user@firm.com", password="secret")

health = client.health()
print(health.status)

client.logout()
```

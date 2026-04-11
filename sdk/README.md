# gideon-sdk

Python REST client for the Gideon API.

## Usage

```python
from gideon import Client

client = Client(base_url="http://localhost:8000")
client.login(email="user@firm.com", password="secret")

health = client.health()
print(health.status)

client.logout()
```

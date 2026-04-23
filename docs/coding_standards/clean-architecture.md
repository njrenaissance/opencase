# Clean Architecture

Clean Architecture ensures systems remain flexible, testable, and independent
of frameworks. It's based on Uncle Bob's architecture principles and SOLID.

---

## The Dependency Rule

The central principle: **dependencies always point inward**. Code in outer
layers can depend on inner layers, but never the reverse.

```

Frameworks & Drivers (Web, UI, DB)
         ↓ depends on
Interface Adapters (Controllers, Presenters, Gateways)
         ↓ depends on
Use Cases (Application Business Rules)
         ↓ depends on
Entities (Enterprise Business Rules)
         ↓ depends on
(nothing)

```

- Entities know nothing about use cases

- Use cases know nothing about presenters

- Presenters know nothing about the web framework

- The web framework is a detail; business logic is the center

---

## Four-Layer Architecture

### Layer 1: Entities (Enterprise Business Rules)

Core business concepts. No framework dependencies. These are the slowest to
change.

**Examples:**

- `User`, `Matter`, `Document`, `AuditLog` classes

- Domain logic that would be the same in any implementation

**Rules:**

- No imports from other layers

- No framework dependencies (no FastAPI, no SQLAlchemy, no React)

- Pure business logic only

```python
# ✅ GOOD
class AuditLog:
    def __init__(self, user_id: str, action: str, timestamp: datetime):
        self.user_id = user_id
        self.action = action
        self.timestamp = timestamp
    
    def is_valid(self) -> bool:
        return self.user_id and self.action and self.timestamp

```

### Layer 2: Use Cases (Application Business Rules)

Orchestrate entities. Implement workflows specific to this application.
E.g., "create matter", "run RAG query", "check legal hold before delete".

**Examples:**

- `CreateMatterUseCase`, `QueryDocumentsUseCase`, `DeleteDocumentUseCase`

- Boundary objects (`Request`, `Response`) that decouple from web frameworks

**Rules:**

- Depend on entities and other use cases

- Do not depend on presentation or persistence details

- Use interfaces/protocols for dependencies (database, LLM, etc.)

```python
# ✅ GOOD
class QueryDocumentsUseCase:
    def __init__(self, qdrant_gateway: QdrantGateway, permissions_filter_builder):
        self.qdrant = qdrant_gateway
        self.filter_builder = permissions_filter_builder
    
    def execute(self, request: QueryRequest) -> QueryResponse:
        # Business logic: build filter, query, format response
        filter = self.filter_builder.build(
            user=request.user,
            matter_id=request.matter_id
        )
        results = self.qdrant.search(query_vector=..., filter=filter)
        return QueryResponse(documents=results)

```

### Layer 3: Interface Adapters

Convert data between use cases and external systems. Controllers, presenters,
gateways.

**Examples:**

- FastAPI routes (`/documents/query` → deserialize request → call use case)

- React components (serialize state → display)

- Repository pattern (use case → database)

**Rules:**

- Depend on use cases and entities

- Know about web frameworks, databases, etc.

- Translate between external formats and internal objects

```python
# ✅ GOOD
@router.post("/documents/search")
async def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user)
) -> SearchResponse:
    use_case = QueryDocumentsUseCase(
        qdrant_gateway=qdrant_client,
        permissions_filter_builder=build_permissions_filter
    )
    result = use_case.execute(QueryRequest(
        user=current_user,
        query=request.query,
        matter_id=request.matter_id
    ))
    return result

```

### Layer 4: Frameworks & Drivers

Web frameworks, databases, libraries. The outermost layer. Changes here should
never affect inner layers.

**Examples:**

- FastAPI, Next.js, React, SQLAlchemy, Qdrant client

- These are swappable. Replacing FastAPI with Flask should require no changes
  to use cases or entities.

**Rules:**

- Depend on everything inward

- Minimal business logic here

- Wire up dependencies and handle I/O

---

## SOLID Principles

### S: Single Responsibility Principle (SRP)

A class should have one reason to change. See also Clean Code Rule 25.

**Bad:**

```python
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
    
    def save_to_db(self):  # Persistence — different reason to change
        db.insert(self)
    
    def send_welcome_email(self):  # Email — different reason to change
        email.send(f"Welcome, {self.name}")

```

**Good:**

```python
class User:  # User entity — one reason to change (user definition)
    def __init__(self, name, email):
        self.name = name
        self.email = email

class UserRepository:  # Persistence — one reason to change (how to save)
    def save(self, user: User):
        db.insert(user)

class UserService:  # Business logic — one reason to change (signup process)
    def __init__(self, repository: UserRepository, email_service: EmailService):
        self.repository = repository
        self.email_service = email_service
    
    def signup(self, user: User):
        self.repository.save(user)
        self.email_service.send_welcome(user)

```

### O: Open/Closed Principle (OCP)

Software should be open for extension, closed for modification.

**Bad:**

```python
class DocumentValidator:
    def validate(self, doc):
        if doc.type == "pdf":
            return self.validate_pdf(doc)
        elif doc.type == "docx":
            return self.validate_docx(doc)
        # Adding a new type requires modifying this class

```

**Good:**

```python
class DocumentValidator:
    def __init__(self, validators: Dict[str, Validator]):
        self.validators = validators
    
    def validate(self, doc):
        validator = self.validators.get(doc.type)
        return validator.validate(doc)

# Extend by adding to validators, not by modifying DocumentValidator

```

### L: Liskov Substitution Principle (LSP)

A subclass should be usable wherever its parent is used.

**Bad:**

```python
class Bird:
    def fly(self):
        pass

class Penguin(Bird):
    def fly(self):
        raise NotImplementedError("Penguins can't fly")

```

**Good:**

```python
class Animal:
    pass

class FlyingBird(Animal):
    def fly(self):
        pass

class Penguin(Animal):
    def swim(self):
        pass

```

### I: Interface Segregation Principle (ISP)

Many client-specific interfaces are better than one general-purpose interface.

**Bad:**

```python
class DocumentService:
    def upload(self):
        pass
    
    def delete(self):
        pass
    
    def search(self):
        pass

# Client that only uploads shouldn't depend on delete and search
uploader = DocumentService()

```

**Good:**

```python
class Uploader(Protocol):
    def upload(self): ...

class Deleter(Protocol):
    def delete(self): ...

class Searcher(Protocol):
    def search(self): ...

# Clients depend only on what they need
def upload_documents(uploader: Uploader):
    uploader.upload()

```

### D: Dependency Inversion Principle (DIP)

High-level modules should not depend on low-level modules. Both should depend
on abstractions.

**Bad:**

```python
class QueryEngine:
    def __init__(self):
        self.qdrant_client = QdrantClient(...)  # Hard-coded dependency
    
    def search(self, query):
        return self.qdrant_client.search(query)

```

**Good:**

```python
class QueryEngine:
    def __init__(self, vector_store: VectorStore):  # Injected abstraction
        self.vector_store = vector_store
    
    def search(self, query):
        return self.vector_store.search(query)

# In tests, inject a mock
# In production, inject real QdrantClient

```

---

## Practical Architecture Decisions

### Package by Component (Not by Layer)

**Bad:**

```

backend/
├── models/          (all entities here)
├── repositories/    (all data access here)
├── services/        (all use cases here)
├── schemas/         (all DTOs here)

```

**Good:**

```

backend/
├── documents/       (entity, use case, repository, schema for documents)
├── matters/         (entity, use case, repository, schema for matters)
├── users/           (entity, use case, repository, schema for users)
├── core/            (shared: auth, permissions, audit)
└── common/          (shared utilities)

```

**Why:** Easy to find related code; easier to extract into a module; reduces
cross-dependencies.

### Use Access Modifiers Consistently

Make internal details private; expose only what's needed.

- ❌ BAD: All methods public (no way to know what's safe to call)

- ✅ GOOD: Private methods (underscore prefix), public contracts explicit

### Enforce Dependency Direction at Compile-Time

If architecture says "use cases depend on entities", make it impossible to
import use cases into entity files.

- Python: `from app.use_cases import ...` (in use_cases only, not in entities)

- TypeScript: Similar; use path aliases in `tsconfig.json` to make it obvious

---

## Testing Architecture

Tests are part of the architecture. The test layer is the outermost.

```

Tests (depend on all layers, both real and mock)
  ↓
Frameworks & Drivers (can be mocked)
  ↓
Interface Adapters (can be mocked)
  ↓
Use Cases (mostly real, but dependencies mocked)
  ↓
Entities (always real, never mocked)

```

**Humble Object Pattern:** Move complexity away from the thing that's hard to
test (e.g., HTTP handling) into a use case that's easy to test.

```python
# ❌ Hard to test (web framework details mixed with logic)
@router.post("/documents/delete")
async def delete_document(doc_id: str, current_user: User):
    # Check permissions
    # Check legal hold
    # Delete from Qdrant
    # Delete from MinIO
    # Log to audit

# ✅ Easy to test (logic in use case, web layer is humble)
use_case = DeleteDocumentUseCase(qdrant, minio, audit_log)
result = use_case.execute(DeleteDocumentRequest(doc_id=..., user=...))

# Web layer just translates request/response
@router.post("/documents/delete")
async def delete_document(doc_id: str, current_user: User):
    result = use_case.execute(DeleteDocumentRequest(doc_id, current_user))
    if result.is_success():
        return {"status": "deleted"}
    else:
        raise HTTPException(status_code=403, detail=result.error)

```

---

## Screaming Architecture

> The architecture of a system should scream its business domain, not the
> frameworks it uses.

A file listing of Gideon should reveal:

- Documents, Matters, Users, Witnesses

- Brady, Giglio, Jencks tracking

- Legal hold, audit logging

- Permission filtering

Not:

- FastAPI, SQLAlchemy, Qdrant, MinIO (those are implementation details)

```

gideon/
├── documents/       ← What is this system about?
├── matters/
├── users/
├── witnesses/
├── brady_tracker/
├── legal_hold/
├── audit/
├── permissions/
└── core/

```

---

## See Also

- [Clean Code Principles](clean-code.md) — 40 specific rules

- [Design Patterns](design-patterns.md) — Structural approaches to common problems

- [Gideon Essentials](gideon-essentials.md) — Gideon-specific rules

---

## Further Reading

- Robert C. Martin, *Clean Architecture* (Prentice Hall, 2017)

- Mark Seemann, *Dependency Injection Principles, Practices, and Patterns* (Manning, 2019)

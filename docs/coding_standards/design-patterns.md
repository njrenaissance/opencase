# Design Patterns

Design patterns are reusable solutions to common problems. These 11 patterns
(Gang of Four) account for ~80% of real-world use cases.

---

## Quick Decision Tree

**Structuring objects/hierarchies?**

- Need flexibility to add behaviors → **Decorator**

- Need to compose into trees → **Composite**

- Need to adapt incompatible interfaces → **Adapter**

**Handling requests/commands?**

- Pass request through a chain of handlers → **Chain of Responsibility**

- Turn a request into an object → **Command**

- Different behavior for different types → **Strategy**

**Creating complex objects?**

- Step-by-step construction → **Builder**

- Multiple ways to create the same thing → **Factory Method**

- Multiple related families → **Abstract Factory**

**Coordinating behavior across objects?**

- Notify many objects when state changes → **Observer**

- Vary algorithm steps independently → **Template Method**

**Managing state/behavior across multiple types?**

- Different behavior per state → **State**

---

## Creational Patterns

### Factory Method

Use when: Object creation depends on conditions, and you want to hide the
creation logic.

**Problem:**

```python
if document.type == "pdf":
    parser = PDFParser()
elif document.type == "docx":
    parser = DocxParser()
elif document.type == "txt":
    parser = TxtParser()

```

Every new document type requires code changes.

**Solution:**

```python
class ParserFactory:
    _parsers = {
        "pdf": PDFParser,
        "docx": DocxParser,
        "txt": TxtParser
    }
    
    @classmethod
    def create(cls, document_type: str) -> Parser:
        parser_class = cls._parsers.get(document_type)
        if not parser_class:
            raise ValueError(f"Unknown type: {document_type}")
        return parser_class()

# Usage
parser = ParserFactory.create(document.type)
chunks = parser.parse(document.content)

```

**In Gideon:** Use for creating different parsers (PDF, DOCX, images) without
hardcoding in the ingestion pipeline.

### Builder

Use when: Creating complex objects with many optional parameters.

**Problem:**

```python
Document(
    title="...",
    content="...",
    classification="brady",
    source="government_production",
    bates_number="...",
    page_number=1,
    document_hash="...",
    created_at=...,
    # 5 more params...
)

```

Hard to read; easy to mix up order.

**Solution:**

```python
builder = DocumentBuilder() \
    .with_title("Evidence") \
    .with_content(content) \
    .with_classification(Classification.BRADY) \
    .with_source(Source.GOVERNMENT) \
    .with_bates_number("GOV-001") \
    .build()

```

**In Gideon:** Use for constructing complex query filters or audit log entries.

### Abstract Factory

Use when: You have multiple related families of objects that vary together.

**Problem:** Your application needs to work with different storage backends
(MinIO, local disk, cloud storage) but they all need the same interface.

**Solution:**

```python
class StorageFactory(ABC):
    @abstractmethod
    def create_uploader(self) -> Uploader:
        pass
    
    @abstractmethod
    def create_downloader(self) -> Downloader:
        pass

class MinIOFactory(StorageFactory):
    def create_uploader(self) -> Uploader:
        return MinIOUploader(client)
    
    def create_downloader(self) -> Downloader:
        return MinIODownloader(client)

class LocalStorageFactory(StorageFactory):
    def create_uploader(self) -> Uploader:
        return LocalUploader(base_path)
    
    def create_downloader(self) -> Downloader:
        return LocalDownloader(base_path)

```

**In Gideon:** Use for pluggable cloud storage providers (MinIO, S3, Azure Blob).

---

## Structural Patterns

### Adapter

Use when: You have incompatible interfaces that need to work together.

**Problem:** Your code uses `VectorStore` interface, but the Qdrant client has
a different API.

**Solution:**

```python
class QdrantAdapter(VectorStore):
    def __init__(self, client: QdrantClient):
        self.client = client
    
    def search(self, query_vector, filter=None):
        # Translate VectorStore.search() to Qdrant API
        results = self.client.search(
            collection_name="documents",
            query_vector=query_vector,
            query_filter=filter
        )
        return [Document(...) for r in results]

```

**In Gideon:** Use to adapt Ollama's embedding API to your `Embedder` interface,
or to adapt Tika's parsing API.

### Decorator

Use when: You want to add behavior to objects dynamically without modifying
the class.

**Problem:**

```python
# Bad: Create one class per combination
class EncryptedAuditLog { }
class EncryptedSignedAuditLog { }
class CompressedEncryptedSignedAuditLog { }

```

**Solution:**

```python
class AuditLog:
    def write(self, entry: str):
        pass

class EncryptedAuditLog(AuditLog):
    def __init__(self, inner: AuditLog, cipher):
        self.inner = inner
        self.cipher = cipher
    
    def write(self, entry):
        encrypted = self.cipher.encrypt(entry)
        self.inner.write(encrypted)

# Stack decorators
log = AuditLog()
log = EncryptedAuditLog(log, cipher)
log = SignedAuditLog(log, signer)
log.write(entry)  # Encrypted and signed

```

**In Gideon:** Use for audit logging (add encryption, signing, compression
without modifying AuditLog).

---

## Behavioral Patterns

### Strategy

Use when: You have multiple algorithms for the same task, and you want to
choose at runtime.

**Problem:**

```python
if search_strategy == "bm25":
    results = bm25_search(query)
elif search_strategy == "semantic":
    results = semantic_search(query)
elif search_strategy == "hybrid":
    results = hybrid_search(query)

```

**Solution:**

```python
class SearchStrategy(ABC):
    @abstractmethod
    def search(self, query: str) -> List[Document]:
        pass

class BM25Search(SearchStrategy):
    def search(self, query):
        return bm25(query)

class SemanticSearch(SearchStrategy):
    def search(self, query):
        return qdrant_search(query)

class HybridSearch(SearchStrategy):
    def __init__(self, bm25: BM25Search, semantic: SemanticSearch):
        self.bm25 = bm25
        self.semantic = semantic
    
    def search(self, query):
        return merge_results(self.bm25.search(query), self.semantic.search(query))

# Usage
strategy = HybridSearch(...)
results = strategy.search(user_query)

```

**In Gideon:** Use for different document parsing strategies (PDFs, images,
text) or different query strategies (full-text, semantic, hybrid).

### Observer

Use when: You want multiple objects to react when something changes.

**Problem:**

```python
document = Document(...)
document.delete()  # Who's listening? Nobody knows.

```

**Solution:**

```python
class Document:
    def __init__(self):
        self.observers = []
    
    def attach(self, observer: DocumentObserver):
        self.observers.append(observer)
    
    def delete(self):
        # ... do deletion ...
        for observer in self.observers:
            observer.on_document_deleted(self)

class AuditLog(DocumentObserver):
    def on_document_deleted(self, doc):
        self.log(f"Document {doc.id} deleted")

class LegalHoldEnforcer(DocumentObserver):
    def on_document_deleted(self, doc):
        if doc.legal_hold:
            raise PermissionError("Cannot delete held document")

```

**In Gideon:** Use for legal hold enforcement, audit logging, and real-time
notifications when documents are deleted, tagged, or classified.

### Chain of Responsibility

Use when: You want to pass a request through a chain of handlers until one
handles it.

**Problem:** Validation with if-else chains.

**Solution:**

```python
class ValidationHandler(ABC):
    def __init__(self, next_handler=None):
        self.next = next_handler
    
    @abstractmethod
    def validate(self, document):
        pass

class EmailValidator(ValidationHandler):
    def validate(self, user):
        if not user.email:
            raise ValueError("Email required")
        return self.next.validate(user) if self.next else True

class PhoneValidator(ValidationHandler):
    def validate(self, user):
        if not user.phone:
            raise ValueError("Phone required")
        return self.next.validate(user) if self.next else True

# Chain
chain = EmailValidator(PhoneValidator())
chain.validate(user)

```

**In Gideon:** Use for permission checking (user is admin? → check firm
access → check matter access → grant or deny).

### Command

Use when: You want to encapsulate a request as an object.

**Problem:**

```python
def delete_document(doc_id, current_user):
    # ... auth, validation, deletion, logging, audit ...

```

Hard to test, hard to undo, hard to queue.

**Solution:**

```python
@dataclass
class DeleteDocumentCommand:
    document_id: str
    user_id: str

class DeleteDocumentHandler:
    def __init__(self, document_repo, audit_log, permissions):
        self.document_repo = document_repo
        self.audit_log = audit_log
        self.permissions = permissions
    
    def execute(self, command: DeleteDocumentCommand):
        doc = self.document_repo.find(command.document_id)
        if not self.permissions.can_delete(command.user_id, doc):
            raise PermissionError()
        if doc.legal_hold:
            raise PermissionError("Cannot delete held document")
        
        self.document_repo.delete(doc)
        self.audit_log.log(f"Deleted {command.document_id}")

# Easy to test, easy to queue for background processing
handler = DeleteDocumentHandler(...)
handler.execute(DeleteDocumentCommand("doc-123", "user-456"))

```

**In Gideon:** Use for document operations, matter creation, user actions.

### Template Method

Use when: Multiple classes share the same algorithm structure, but differ in
specific steps.

**Problem:**

```python
class PDFParser:
    def parse(self):
        self.open_file()
        self.extract_text()
        self.chunk_text()
        self.return_chunks()

class DocxParser:
    def parse(self):
        self.open_file()
        self.extract_text()
        self.chunk_text()
        self.return_chunks()
    # Same structure, different implementations

```

**Solution:**

```python
class DocumentParser(ABC):
    def parse(self, path):
        raw_text = self.extract_text(path)
        chunks = self.chunk_text(raw_text)
        return chunks
    
    @abstractmethod
    def extract_text(self, path) -> str:
        pass
    
    def chunk_text(self, text):
        # Default implementation; subclasses can override
        return text.split("\n\n")

class PDFParser(DocumentParser):
    def extract_text(self, path):
        # PDF-specific extraction
        return extract_pdf_text(path)

class DocxParser(DocumentParser):
    def extract_text(self, path):
        # DOCX-specific extraction
        return extract_docx_text(path)

```

**In Gideon:** Use for document parsing (all parsers: open, extract, chunk,
return) or workflow steps.

---

## Pattern Flagging Convention

When reviewing code, use TODO comments to suggest patterns:

```

// TODO @pattern: This looks like a Strategy pattern opportunity
// Reasoning: Multiple algorithms (BM25, semantic, hybrid) for same task
// See: docs/coding_standards/design-patterns.md#strategy

// TODO @pattern: Observer pattern would decouple legal hold from deletion logic
// Current: DeleteDocument checks legal_hold directly
// Better: Legal hold enforcer subscribes to on_delete events
// See: docs/coding_standards/design-patterns.md#observer

```

This makes pattern opportunities visible without being prescriptive.

---

## P2 & P3 Patterns

For a complete catalog of all 23 Gang of Four patterns, including P2 (Singleton,
Composite, Proxy, State, Iterator, Mediator, Memento) and P3 (Prototype, Bridge,
Flyweight, Visitor), see the full pattern repository:

<https://github.com/SignaTrustDev/engineering-standards/tree/main/patterns>

Each pattern file includes:

- Problem description

- Before/after code examples

- Pitfalls and when NOT to use it

- Real-world examples from Gideon's domain

---

## Anti-Patterns to Avoid

### God Class

A class that does too much. Violates SRP.

- ❌ BAD: `DocumentManager` that handles parsing, storage, searching, deletion

- ✅ GOOD: `DocumentParser`, `DocumentRepository`, `DocumentSearcher`

### Primitive Obsession

Using primitives (strings, ints) instead of small objects.

- ❌ BAD: `def validate_email(email: str)`

- ✅ GOOD: `def validate_email(email: Email)`; now Email can validate itself

### Cargo Cult Programming

Using patterns "because everyone does" without understanding why.

- ❌ BAD: "The architecture says to use Factory, so use Factory"

- ✅ GOOD: "We have 5 different parsers and this code will grow; Factory reduces if-else chains"

---

## See Also

- [Clean Code Principles](clean-code.md) — Individual rules

- [Clean Architecture](clean-architecture.md) — Structural guidance (layers, SOLID)

- [Gideon Essentials](gideon-essentials.md) — Gideon-specific practices

---

## Further Reading

- Gang of Four (Gamma, Helm, Johnson, Vlissides), *Design Patterns* (Addison-Wesley, 1994)

- Refactoring.Guru Design Patterns Guide: <https://refactoring.guru/design-patterns>

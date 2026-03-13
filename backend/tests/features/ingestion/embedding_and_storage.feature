Feature: Embedding and vector storage
  As the ingestion pipeline
  I want to embed document chunks and store them in Qdrant
  So that they are searchable via semantic queries

  Background:
    Given a firm "Cora Firm" exists
    And a matter "People v. Smith" exists for "Cora Firm"
    And the Ollama embedding model "nomic-embed-text" is available

  Scenario: Chunks are embedded and stored in Qdrant
    Given a document with 5 text chunks
    When the chunks are processed by the embedding pipeline
    Then 5 vectors should be stored in Qdrant
    And each vector should have a non-empty embedding

  Scenario: Every vector carries required permission payload
    Given a document with 1 text chunk
    And the document belongs to matter "People v. Smith"
    And the document has classification "unclassified"
    And the document source is "government_production"
    When the chunk is processed by the embedding pipeline
    Then the stored vector payload should contain "firm_id"
    And the stored vector payload should contain "matter_id"
    And the stored vector payload should contain "client_id"
    And the stored vector payload should contain "document_id"
    And the stored vector payload should contain "chunk_index"
    And the stored vector payload should contain "classification"
    And the stored vector payload should contain "source"
    And the stored vector payload should contain "page_number"

  Scenario: Bates number is preserved in vector payload
    Given a document with Bates number "GOV-00142"
    When the document is processed by the ingestion pipeline
    Then the stored vector payload "bates_number" should be "GOV-00142"

  Scenario: Document without Bates number stores null
    Given a document without a Bates number
    When the document is processed by the ingestion pipeline
    Then the stored vector payload "bates_number" should be null

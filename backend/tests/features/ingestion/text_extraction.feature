Feature: Text extraction and chunking
  As the ingestion pipeline
  I want to extract text from uploaded documents and split it into chunks
  So that the content can be embedded and searched

  Background:
    Given a firm "Cora Firm" exists
    And a matter "People v. Smith" exists for "Cora Firm"

  Scenario: Extract text from a PDF
    Given a PDF document with 10 pages of text
    When the document is processed by the ingestion pipeline
    Then text should be extracted from all 10 pages
    And the text should be split into chunks

  Scenario: Extract text from a scanned image via OCR
    Given a scanned image document with no embedded text
    When the document is processed by the ingestion pipeline
    Then Tesseract OCR should extract the visible text
    And the text should be split into chunks

  Scenario: Extract text from a Word document
    Given a Word document with formatted text and tables
    When the document is processed by the ingestion pipeline
    Then text should be extracted including table content
    And the text should be split into chunks

  Scenario: Chunks carry page number metadata
    Given a PDF document with 5 pages
    When the document is processed by the ingestion pipeline
    Then each chunk should reference its source page number

  Scenario: Empty document produces no chunks
    Given a PDF document with zero extractable text
    When the document is processed by the ingestion pipeline
    Then the document should be stored with status "empty"
    And no chunks should be created

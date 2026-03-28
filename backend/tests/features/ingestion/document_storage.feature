Feature: Document storage in MinIO S3
  As the ingestion pipeline
  I want to store original files in S3-compatible object storage
  So that originals are preserved and OpenCase controls document lifecycle

  # All original files are stored in MinIO regardless of ingestion
  # source (manual upload or cloud poll). SharePoint is
  # read-only — OpenCase never writes back to cloud storage.
  #
  # Bucket layout: opencase/{firm_id}/{matter_id}/{document_id}/original.{ext}

  Background:
    Given a firm "Cora Firm" exists
    And a matter "People v. Smith" exists for "Cora Firm"
    And MinIO S3 storage is available

  Scenario: Manual upload stores original in S3
    Given I am logged in as an attorney assigned to "People v. Smith"
    When I upload "discovery_batch_001.pdf" to matter "People v. Smith"
    Then the original file should be stored in the S3 bucket
    And the S3 key should follow the pattern "{firm_id}/{matter_id}/{document_id}/original.pdf"
    And the stored file should be byte-identical to the uploaded file

  Scenario: Cloud-ingested file stores original in S3
    Given a SharePoint top-level folder "People v. Smith" is mapped to that matter
    And the folder contains "prosecution_filing.docx"
    When the cloud ingestion worker runs
    Then the original file should be stored in the S3 bucket
    And the S3 key should follow the pattern "{firm_id}/{matter_id}/{document_id}/original.docx"

  Scenario: Original file is never modified after storage
    Given "exhibit_a.pdf" has been ingested and stored in S3
    When the document is processed through text extraction and chunking
    Then the original file in S3 should remain byte-identical
    And the SHA-256 hash should still match the stored record

  Scenario: S3 storage records the document metadata
    Given I am logged in as an attorney assigned to "People v. Smith"
    When I upload "evidence.pdf" to matter "People v. Smith"
    Then the S3 object metadata should include the document_id
    And the S3 object metadata should include the matter_id
    And the S3 object metadata should include the SHA-256 hash
    And the S3 object metadata should include the ingestion timestamp

  Scenario: Retrieving an original file from S3
    Given "exhibit_a.pdf" has been ingested and stored in S3
    And I am logged in as an attorney assigned to "People v. Smith"
    When I request the original file for "exhibit_a.pdf"
    Then the file should be served from S3
    And the file should be byte-identical to what was uploaded

Feature: Scheduled cloud ingestion
  As a firm administrator
  I want documents from SharePoint to be ingested automatically
  So that new discovery productions are processed without manual upload

  Background:
    Given a firm "Cora Firm" exists
    And the deployment mode is "internet"
    And Microsoft Graph API credentials are configured
    And a matter "People v. Smith" exists for "Cora Firm"

  # Top-level folder name in SharePoint maps to the matter.
  # Every file encountered is recorded with its SHA-256 hash in
  # PostgreSQL, regardless of whether it is new or already ingested.
  # This ensures integrity verification and prevents reprocessing.

  Scenario: Poll SharePoint folder and ingest new files
    Given a SharePoint top-level folder "People v. Smith" is mapped to that matter
    And the folder contains 3 new PDF files
    When the cloud ingestion worker runs
    Then all 3 files should be downloaded to the temp volume
    And all 3 files should be processed through the ingestion pipeline
    And each original file should be stored in S3
    And each file should be recorded with its SHA-256 hash
    And each file should be recorded with its ingestion timestamp
    And no file should be processed more than once
    And the temp files should be deleted after processing

  Scenario: Skip already-ingested files based on hash
    Given a SharePoint top-level folder "People v. Smith" is mapped to that matter
    And "report.pdf" has been ingested with SHA-256 hash "abc123"
    And "new_filing.pdf" has SHA-256 hash "def456" which is not in the database
    When the cloud ingestion worker runs
    Then the worker should compute the SHA-256 hash of each file before processing
    And "new_filing.pdf" should be processed because its hash is unrecognized
    And "report.pdf" should be skipped because its hash matches an existing record

  Scenario: Handle modified files in cloud storage
    Given a SharePoint top-level folder "People v. Smith" is mapped to that matter
    And "witness_list.docx" was previously ingested
    And "witness_list.docx" has been modified since last ingestion
    When the cloud ingestion worker runs
    Then the modified file should be re-ingested
    And both versions should exist in the matter

  # In air-gapped mode the cloud ingestion service is excluded from
  # the Docker Compose stack entirely — there is no container to run.
  # Enabling cloud ingestion requires the administrator to explicitly
  # set DEPLOYMENT_MODE=internet. This is a deliberate operator action,
  # not something that can happen by accident.

  Scenario: Cloud ingestion service does not exist in air-gapped mode
    Given the deployment mode is "airgapped"
    Then the cloud ingestion service should not be present in the compose stack
    And no outbound network calls should be possible from any service

  Scenario: Temp files are cleaned up on failure
    Given a SharePoint top-level folder "People v. Smith" is mapped to that matter
    And the folder contains "corrupt_file.pdf"
    When the cloud ingestion worker runs
    And processing fails for "corrupt_file.pdf"
    Then the temp file for "corrupt_file.pdf" should be deleted
    And an error should be logged in the audit trail

  Scenario: Orphaned temp files are cleaned on startup
    Given the temp volume contains files from a previous crashed run
    When the cloud ingestion worker starts
    Then all orphaned temp files should be deleted

  Scenario: Ingestion run is recorded in audit log
    Given a SharePoint top-level folder "People v. Smith" is mapped to that matter
    And the folder contains 1 new file
    When the cloud ingestion worker runs
    Then an audit log entry should record the ingestion run
    And the entry should include the file count and matter

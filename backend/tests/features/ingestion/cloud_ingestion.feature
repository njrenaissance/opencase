Feature: Scheduled cloud ingestion
  As a firm administrator
  I want documents from OneDrive/SharePoint to be ingested automatically
  So that new discovery productions are processed without manual upload

  Background:
    Given a firm "Cora Firm" exists
    And the deployment mode is "internet"
    And Microsoft Graph API credentials are configured
    And a matter "People v. Smith" exists for "Cora Firm"

  Scenario: Poll OneDrive folder and ingest new files
    Given a OneDrive folder is mapped to matter "People v. Smith"
    And the folder contains 3 new PDF files
    When the cloud ingestion worker runs
    Then all 3 files should be downloaded to the temp volume
    And all 3 files should be processed through the ingestion pipeline
    And the temp files should be deleted after processing

  Scenario: Skip already-ingested files
    Given a OneDrive folder is mapped to matter "People v. Smith"
    And "report.pdf" in the folder has already been ingested
    And "new_filing.pdf" in the folder has not been ingested
    When the cloud ingestion worker runs
    Then only "new_filing.pdf" should be processed
    And "report.pdf" should be skipped

  Scenario: Handle modified files in cloud storage
    Given a OneDrive folder is mapped to matter "People v. Smith"
    And "witness_list.docx" was previously ingested
    And "witness_list.docx" has been modified since last ingestion
    When the cloud ingestion worker runs
    Then the modified file should be re-ingested
    And both versions should exist in the matter

  Scenario: Cloud ingestion is disabled in air-gapped mode
    Given the deployment mode is "airgapped"
    When the cloud ingestion worker attempts to run
    Then the worker should exit without making any network calls

  Scenario: Temp files are cleaned up on failure
    Given a OneDrive folder is mapped to matter "People v. Smith"
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
    Given a OneDrive folder is mapped to matter "People v. Smith"
    And the folder contains 1 new file
    When the cloud ingestion worker runs
    Then an audit log entry should record the ingestion run
    And the entry should include the file count and matter

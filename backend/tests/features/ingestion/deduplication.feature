Feature: Document deduplication
  As a defense attorney
  I want duplicate documents to be detected at ingestion
  So that the same file is not stored and searched twice

  Background:
    Given a firm "Cora Firm" exists
    And a matter "People v. Smith" exists for "Cora Firm"
    And I am logged in as an attorney assigned to "People v. Smith"

  Scenario: Duplicate file is rejected
    Given "evidence_photo.pdf" has already been ingested into "People v. Smith"
    When I upload "evidence_photo.pdf" again to "People v. Smith"
    Then the upload should be rejected as a duplicate
    And the original document should remain unchanged

  Scenario: Same content with different filename is rejected
    Given "report_v1.pdf" has already been ingested into "People v. Smith"
    When I upload "report_v1_copy.pdf" with identical content to "People v. Smith"
    Then the upload should be rejected as a duplicate

  Scenario: Different content with same filename is accepted
    Given "witness_statement.pdf" has already been ingested into "People v. Smith"
    When I upload "witness_statement.pdf" with different content to "People v. Smith"
    Then the document should be stored with status "processed"
    And both versions should exist in the matter

  Scenario: Same file in different matters is accepted
    Given "evidence_photo.pdf" has already been ingested into "People v. Smith"
    And a matter "People v. Jones" exists for "Cora Firm"
    And I am assigned to "People v. Jones"
    When I upload "evidence_photo.pdf" to "People v. Jones"
    Then the document should be stored with status "processed"

  Scenario: SHA-256 hash is computed at ingestion
    When I upload "discovery_batch_001.pdf" to matter "People v. Smith"
    Then the document record should include a SHA-256 content hash
    And the hash should match the actual file content

Feature: Legal hold enforcement during ingestion
  As a defense attorney
  I want documents under legal hold to be immutable
  So that evidence integrity is preserved for court

  Background:
    Given a firm "Cora Firm" exists
    And a matter "People v. Smith" exists for "Cora Firm"
    And I am logged in as an attorney assigned to "People v. Smith"

  Scenario: Cannot delete a document under legal hold
    Given "exhibit_a.pdf" is ingested into "People v. Smith"
    And a legal hold is active on matter "People v. Smith"
    When I attempt to delete "exhibit_a.pdf"
    Then the deletion should be rejected
    And the document should still exist

  Scenario: Cannot modify a document under legal hold
    Given "exhibit_a.pdf" is ingested into "People v. Smith"
    And a legal hold is active on matter "People v. Smith"
    When I attempt to replace "exhibit_a.pdf" with new content
    Then the modification should be rejected
    And the document content should be unchanged

  Scenario: New uploads are allowed under legal hold
    Given a legal hold is active on matter "People v. Smith"
    When I upload "new_evidence.pdf" to matter "People v. Smith"
    Then the document should be stored with status "processed"

  Scenario: Legal hold applies to all documents in the matter
    Given "doc_1.pdf" is ingested into "People v. Smith"
    And "doc_2.pdf" is ingested into "People v. Smith"
    And a legal hold is active on matter "People v. Smith"
    When I attempt to delete "doc_1.pdf"
    Then the deletion should be rejected
    When I attempt to delete "doc_2.pdf"
    Then the deletion should be rejected

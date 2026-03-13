Feature: Manual document upload
  As a defense attorney
  I want to upload discovery documents through the UI
  So that they are searchable in my matter

  Background:
    Given a firm "Cora Firm" exists
    And a matter "People v. Smith" exists for "Cora Firm"
    And I am logged in as an attorney assigned to "People v. Smith"

  Scenario: Upload a PDF document
    When I upload "discovery_production_001.pdf" to matter "People v. Smith"
    Then the document should be stored with status "processed"
    And the document should have a SHA-256 content hash
    And an audit log entry should record the upload

  Scenario: Upload a Word document
    When I upload "witness_statement.docx" to matter "People v. Smith"
    Then the document should be stored with status "processed"
    And the document should have a SHA-256 content hash

  Scenario: Upload an email file
    When I upload "prosecution_correspondence.msg" to matter "People v. Smith"
    Then the document should be stored with status "processed"

  Scenario: Upload an EML email file
    When I upload "defense_reply.eml" to matter "People v. Smith"
    Then the document should be stored with status "processed"

  Scenario: Upload an image with OCR
    When I upload "handwritten_note.jpg" to matter "People v. Smith"
    Then the document should be stored with status "processed"
    And the extracted text should contain OCR output

  Scenario: Reject upload to unassigned matter
    Given a matter "People v. Jones" exists for "Cora Firm"
    And I am not assigned to "People v. Jones"
    When I attempt to upload "document.pdf" to matter "People v. Jones"
    Then the upload should be rejected with a 403 error

  Scenario: Reject upload without authentication
    Given I am not logged in
    When I attempt to upload "document.pdf" to matter "People v. Smith"
    Then the upload should be rejected with a 401 error

# Legal & Ethical Compliance

Gideon is designed from the ground up to comply with the legal and ethical frameworks governing criminal defense practice, particularly in New York and federal courts. This document outlines the key compliance requirements that inform the system architecture and operational policies.

## ABA Model Rules of Professional Conduct

### Rule 1.6 — Confidentiality

Attorneys must make reasonable efforts to prevent unauthorized disclosure of client information.

**Gideon's Implementation:**
- **Fully self-hosted**: Client data never leaves firm infrastructure under any circumstances
- **No API calls to third parties**: All LLM inference, embeddings, and document processing happens locally via Ollama
- **Encryption at rest and in transit**: All stored data and network traffic is encrypted
- **Per-matter access control**: Users see only matters explicitly assigned to them; vector queries are filtered server-side by matter scope
- **No telemetry**: Zero third-party calls for observability, logging, or monitoring

### Rule 1.1 — Competence

Attorneys must understand the technology they deploy, including AI tools.

**Gideon's Implementation:**
- **Full citations on every chatbot answer**: Sources are documented with document name, Bates number (if present), page number, and relevant text excerpt
- **Separation of document-sourced findings from general knowledge**: System prompt enforces clear labeling of where answers come from — either from case documents or from the model's training data
- **Accuracy prioritized over completeness**: The system prompt explicitly instructs the model to prioritize correctness and flag uncertainty rather than generate speculative answers
- **Immutable audit log**: All LLM queries, responses, and document accesses are logged with cryptographic verification
- **Transparent limitations**: The UI displays an AI-generated content disclaimer on all chatbot responses

### ABA Formal Opinion 512 (2024)

Informed client consent required before using AI on client data; attorneys must verify AI is not self-learning; boilerplate consent is insufficient; all AI queries must be logged.

**Gideon's Implementation:**
- **No model training on client data**: Zero retention of conversations or documents for fine-tuning or retraining
- **Self-hosted model weights**: The attorney controls the model and can verify it is not calling out to training systems
- **Immutable audit log of all queries**: Every chatbot interaction is logged to an audit trail that can be produced to clients or bar inquiry

**Engagement Letter Guidance:**

Attorneys using Gideon should disclose the use of AI in case work to clients
and obtain informed consent. The ABA provides model engagement letter language
and AI disclosures through its [Practice Resources](https://www.americanbar.org/groups/legal_services/initiatives/artificial_intelligence/resources/).
State bar associations and practice-specific organizations (e.g., criminal
defense bar associations) may provide jurisdiction-specific templates.

---

## Federal Criminal Discovery Framework

### Federal Rule of Criminal Procedure 16

Governs standard government production. Reciprocal once invoked by either side.

**Gideon's Implementation:**
- Document tagging system supports classification as "rule_16" material
- Matter-scoped search ensures no cross-matter contamination when discussing Rule 16 discovery
- Chatbot can answer "What Rule 16 material is outstanding?" via the discovery tracker

### Brady v. Maryland (1963)

Government must disclose all exculpatory evidence material to guilt or punishment.

**Gideon's Implementation:**
- **Brady/Giglio tracker**: Log all Brady demands sent and government responses received
- **Document classification**: Documents tagged as "brady" throughout the case
- **Deadline tracking**: Automatically flag when government Brady production is overdue under applicable statutes
- **Audit log**: Every Brady-classified document access is logged

### Giglio v. United States (1972)

Extends Brady to all impeachment evidence affecting government witness credibility.

**Gideon's Implementation:**
- **Witness index**: Automatic entity extraction builds a witness list across all documents
- **Giglio flagging**: Attorney can flag witnesses where impeachment material has been found
- **Document classification**: Documents tagged as "giglio" throughout the case
- **Jencks Act integration**: Giglio material is subject to distinct release rules depending on witness testimony status (see Jencks Rule below)

### Jencks Act (18 U.S.C. §3500)

Prior statements of government witnesses are discoverable only AFTER the witness has testified, with strict timing and scope requirements. Distinct from Brady/Giglio — prosecutors frequently misuse this rule to delay constitutional obligations.

**Gideon's Implementation:**
- **Jencks flag in vector payload**: Every chunk carries a "classification" field including "jencks" as a possible value
- **Witness testimony gate**: The vector search respects a "has_testified" flag on each witness record in PostgreSQL
- **Architectural enforcement**: Jencks material is filtered from chatbot queries until "has_testified = true" is set — this is enforced inside `build_qdrant_filter()` and is never bypassed
- **Audit trail**: Every Jencks classification is logged; access to Jencks material after testimony is granted is fully audit-logged

---

## New York State — CPL Article 245 (2020, amended 2022, 2025)

Automatic open discovery is a cornerstone of modern New York criminal procedure. Hard statutory deadlines govern prosecution disclosure obligations.

### Key Dates and Deadlines

- **20 days** from arraignment (incarcerated defendant)
- **35 days** from arraignment (non-incarcerated defendant)
- **Certificate of Compliance (COC)** requirement: prosecution cannot declare trial-ready until COC is filed, confirming all discoverable material has been produced
- **CPL 30.30 linkage**: Late or incomplete discovery under CPL 245 stops the speedy trial clock; cases can be dismissed if the prosecution fails to meet disclosure deadlines

### 2025 Amendments

Recent amendments narrowed mandatory disclosure scope in some categories. COC challenges must be raised within 35 days of service.

**Gideon's Implementation:**
- **Brady/Giglio tracker**: Log automatic discovery demands, responses, and outstanding items
- **Deadline clock**: Automatic countdown from arraignment date (20-day / 35-day)
- **CPL 30.30 calendar**: Track whether COC has been filed and when the speedy trial clock is running
- **Alert system**: Flag overdue or incomplete government production relative to statutory deadlines
- **Dashboard**: Brady/Giglio tracker dashboard shows demands sent, responses received, and elapsed days

---

## Additional Compliance Frameworks

### HIPAA (Health Insurance Portability and Accountability Act)

Applies when case documents include protected health information (PHI) — common in matters involving personal injury, medical malpractice, or health-related evidence.

**Gideon's Implementation:**
- Self-hosted data storage means no inadvertent disclosure to third-party cloud services
- Encryption at rest and in transit protects PHI
- Per-matter access control limits exposure to authorized users only
- Audit log tracks all document access — critical for HIPAA compliance investigations

### GDPR (General Data Protection Regulation)

Applicable to matters involving EU clients or internationally held data.

**Gideon's Implementation:**
- Self-hosted architecture enables GDPR-compliant data handling with no international transfers
- User deletion and data export capabilities support subject access requests
- Audit logging supports breach notification and investigation

---

## Security & Data Integrity Principles

### Immutable Audit Log

All user actions are logged to an immutable hash-chained audit trail:
- Document ingestion
- Document access and download
- Chatbot queries and responses
- Permission changes
- User login/logout
- Brady/Giglio tracker updates

The hash chain enables tamper detection — if any log entry is altered, all subsequent entries' hashes will be invalid, making unauthorized modification detectable.

### Legal Hold

Documents placed under legal hold cannot be deleted or modified. This enforces litigation hold obligations and prevents spoliation.

### Document Deduplication

Every ingested document is hashed with SHA-256. The hash is used to detect and prevent reprocessing of duplicate files, preserving Bates number assignments and chain of custody.

### Role-Based Access Control

| Role | Work product | Jencks material | Matter access |
|---|---|---|---|
| Admin | Yes | Yes | All matters |
| Attorney | Yes | Yes | Assigned matters |
| Paralegal | If `view_work_product` granted | Yes | Assigned matters |
| Investigator | No | No | Assigned matters |

Work product is fully protected and is never disclosed to investigators or paralegals unless explicitly authorized by the attorney.

---

## Jurisdictional Scope

Gideon is designed for:
- **English-language documents** (MVP)
- **United States criminal defense** (primary focus)
- **New York State (CPL Article 245)** and **Federal courts (Rule 16 / Brady / Giglio / Jencks)** (initial target frameworks)

Future versions may support:
- Additional US states and jurisdictions
- Multi-language document support
- State-specific discovery rule sets

---

## Deployment Modes & Confidentiality

### Air-gapped / On-premise

Fully self-contained with no external network calls. Manual document upload only. Ideal for classified defense work or firms requiring maximum air-gapping.

### Internet-accessible

Firm-controlled server or private cloud tenant (Azure VPC, AWS VPC, etc.). Enables optional integrations with cloud storage (e.g., OneDrive/SharePoint), but all integration traffic is outbound only — no inbound API calls or webhooks expose client data to external services.

Both modes enforce full encryption and access control. The deployment mode is a configuration choice, not a security trade-off.

---

## References & Further Reading

- **ABA Model Rules of Professional Conduct** (esp. Rules 1.1 and 1.6)
- **ABA Formal Opinion 512** (2024) — Generative AI
- **Federal Rule of Criminal Procedure 16**
- **Brady v. Maryland**, 373 U.S. 83 (1963)
- **Giglio v. United States**, 405 U.S. 150 (1972)
- **Jencks Act**, 18 U.S.C. §3500
- **New York CPL Article 245** (Automatic Discovery) — as amended 2025
- **New York CPL 30.30** (Speedy Trial Clock)
- **HIPAA Privacy Rule**, 45 CFR Parts 160 and 164
- **GDPR** (EU Regulation 2016/679)


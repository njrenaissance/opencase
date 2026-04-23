# Security Policy

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**
Responsible disclosure protects users and gives the maintainers time to
prepare a fix.

To report a vulnerability, email **<security@corafirm.com>** with the subject
line `[SECURITY] Gideon`.

Include:

- **Description** — What is the vulnerability? What system component does it
  affect?
- **Reproduction steps** — How can it be triggered? What are the preconditions?
- **Affected version** — Which Gideon version(s) are vulnerable? (Check
  `git log --oneline` for the commit SHA if running from source.)
- **Impact** — What is the worst-case consequence? Can data be leaked, deleted,
  or corrupted? Can an attacker gain unauthorized access?

## Scope of Vulnerability Reports

Security vulnerabilities in Gideon include:

- Access control bypass (e.g., one user accessing another user's matters)
- Data isolation failures (e.g., cross-matter data leakage)
- Audit log tampering (e.g., deleting or forging audit records)
- Qdrant filter bypass (e.g., circumventing `build_qdrant_filter()`)
- Authentication/JWT weaknesses (e.g., token forgery, replay attacks)
- LLM prompt injection (e.g., jailbreaking system prompts)
- Encryption bypass (e.g., plaintext storage of sensitive data)
- Legal hold violations (e.g., deletion of held documents)

**Out of scope:**

- Denial of service (slow queries, resource exhaustion) — report as a regular
  issue
- Configuration errors (e.g., weak passwords chosen by the operator)
- Undocumented features that do not affect security

## Response Timeline

- **48 hours** — initial acknowledgment
- **7 days** — triage and initial assessment
- **90 days** — coordinated disclosure window (we aim to fix and release
  before this date; you may request an extension if needed)

After 90 days, you may publish details of the vulnerability publicly.

## Confidentiality

Your identity and the details of the vulnerability will be kept confidential
during the disclosure process. Credit for the report will be offered when the
fix is released, with your consent.

## Why This Matters

Gideon handles criminal defense discovery materials — privileged documents
that clients entrust to their attorneys under ABA Rule 1.6 (attorney-client
privilege). A security breach could:

- Expose confidential attorney-client communications
- Compromise client strategies and defense theories
- Violate discovery obligations to the prosecution
- Undermine defendants' constitutional right to effective assistance of
  counsel
- Breach applicable data protection and privacy regulations

Security is non-negotiable. We take all reports seriously.

## Additional Resources

For general guidance on responsible disclosure, see:

- [OWASP: Responsible Disclosure](https://owasp.org/www-community/attacks/Responsible_Disclosure_Process)
- [CWE Top 25](https://cwe.mitre.org/top25/)

## Security in Development

Maintainers review security-sensitive code carefully:

- `build_qdrant_filter()` — every vector query must pass through this
  function; bypassing it is a critical security issue
- `create_audit_log_entry()` — every LLM query, document access, and
  permission change is logged
- Authentication endpoints — JWT signing, MFA verification, scope/quota
  checks
- Encryption at rest and in transit — enabled by default

If you are contributing code that touches these areas, security review is
mandatory and will be thorough.

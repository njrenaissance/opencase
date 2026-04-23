# Governance

## Mission

Named after *Gideon v. Wainwright* (1963) — the Supreme Court decision
establishing the constitutional right to effective counsel for criminal
defendants who cannot afford an attorney.

The principle is simple: **a defendant's right to counsel is meaningless
without the tools to mount an effective defense.**

Large law firms have access to enterprise eDiscovery platforms (Relativity,
Concordance, etc.). Solo practitioners and small criminal defense firms do
not. This creates a two-tier system where a defendant's access to quality
discovery analysis depends on their attorney's budget — not the strength of
their case.

Gideon exists to level that playing field. It's built on two commitments:

1. **Data stays on-premise** — Client confidentiality is non-negotiable. No
   third-party APIs, no cloud ingestion, no telemetry. Your discovery
   materials never leave your infrastructure.

2. **Free and open source** — No licensing fees, no vendor lock-in, no
   proprietary black boxes. You own your data and your tools.

## Governance Model

This project is currently governed by a single maintainer (BDFL model). As the community grows, the intent is to evolve toward a core committer group where trusted contributors earn commit rights and shared decision-making authority.

## Maintainer

- **Name:** Jonathan Phillips
- **Email:** jonphilnj@gmail.com
- **GitHub:** [@njrenaissance](https://github.com/njrenaissance)

## Decision-Making Process

- The BDFL has final decision authority on architecture, scope, and feature prioritization
- Significant changes should be proposed via GitHub Issues as RFCs (Requests for Comments)
- Minor bug fixes and documentation improvements can be submitted directly as PRs without prior issues
- All PRs are reviewed for code quality, test coverage, and alignment with project goals before merge

## Release Naming Convention

Releases are named after famous jurists in honor of their contributions to justice and the law.

| Version | Codename | Jurist |
| --- | --- | --- |
| v1.0 | Ginsburg | Ruth Bader Ginsburg |

Future major releases will follow this naming pattern, each honoring a different jurist.

## Roadmap Ownership

The roadmap is maintained by the BDFL in GitHub Issues (tagged with roadmap labels) and GitHub Milestones. Community input is always welcome — open an issue to suggest features or discuss priorities.

## Design Partner

The Cora Firm is the founding design partner for Gideon. Their real-world criminal defense workflow and feedback informed the feature set, priority order, and user experience design for the v1 MVP.

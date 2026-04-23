# Gideon Coding Standards

This directory contains the complete coding standards for Gideon contributors.
Start with **Gideon Essentials**, then explore the universal principles and
patterns.

## Quick Navigation

1. **[Gideon Essentials](gideon-essentials.md)** — Security rules, legal
   constraints, and domain-specific practices. **Read this first.**

2. **[Clean Code Principles](clean-code.md)** — 40 rules from Robert C. Martin
   for writing maintainable, professional code. Rules organized by category
   (naming, functions, comments, testing, etc.)

3. **[Clean Architecture](clean-architecture.md)** — Architectural patterns,
   SOLID principles, and the dependency rule. How to structure systems for
   longevity and testability.

4. **[Design Patterns](design-patterns.md)** — 11 most-used Gang of Four patterns
   with Gideon-relevant examples. Includes a decision tree to help choose the
   right pattern.

5. **[References](references.md)** — Links to the full engineering-standards
   repository, additional patterns (P2/P3), and external resources.

---

## Standard Enforcement

- **Pre-commit:** Code must pass linting (ruff for Python, ESLint for TypeScript)
  and type checking (mypy, strict TypeScript).

- **Code review:** All contributions are reviewed against these standards.

- **Security:** Rules in Gideon Essentials cannot be violated. Period.

- **Patterns:** Code reviewers will flag pattern opportunities using the
  [flagging convention](design-patterns.md#pattern-flagging-convention).

---

## For AI Assistants (Claude, Copilot, Cursor, etc.)

When working in Gideon:

1. **Always enforce Gideon Essentials** — These are non-negotiable, especially
   the security rules in section 1.
2. **Prefer these patterns:** Use Clean Code and Design Patterns to guide code
   generation.
3. **Check against 40 rules:** Before suggesting code, scan mentally against the
   Clean Code checklist (see end of clean-code.md).
4. **Suggest patterns:** When you see an opportunity to apply a pattern, mention
   it in a TODO comment using the flagging convention.

---

## How to Use This Guide

**Starting a new feature:**
1. Read Gideon Essentials (especially the security rules)
2. Skim Clean Architecture (especially SOLID principles)
3. Code your feature using Clean Code principles
4. Before PR: check against the [Clean Code checklist](clean-code.md#pre-commit-checklist)

**Refactoring existing code:**
1. Identify which Design Pattern might improve the code
2. Apply the pattern using examples from design-patterns.md
3. Verify the code still satisfies Gideon Essentials
4. PR should reference the pattern applied (e.g., "refactor: apply Strategy pattern to query builder")

**Reviewing someone's code:**
1. Check Gideon Essentials compliance first
2. Scan against Clean Code rules
3. Suggest applicable Design Patterns if code is doing multiple things
4. Use the flagging convention to mark pattern opportunities

---

## Updates & Maintenance

These standards are derived from:

- **Gideon-specific practices** — maintained here as Gideon evolves

- **Engineering Standards repo** — universal best practices maintained at
  <https://github.com/SignaTrustDev/engineering-standards>

When engineering standards are updated, Gideon's copies are refreshed by the
maintainers. Contributors should not manually edit the Clean Code or Clean
Architecture sections; those are synced from the source of truth.

If you find a rule that doesn't apply to Gideon or conflicts with Gideon's
mission, open an issue rather than ignoring the rule.

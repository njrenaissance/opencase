# References & External Resources

## Engineering Standards Repository

The canonical source for universal software engineering best practices.

**Repository:** <https://github.com/SignaTrustDev/engineering-standards>

**What's in there:**

- **CLEAN-CODE.md** — Full 40 rules with extended explanations

- **CLEAN-ARCHITECTURE.md** — Full architecture guide with advanced topics

- **patterns/** — Complete 23 Gang of Four design patterns
  - `patterns/creational/` — Factory, Abstract Factory, Builder, Singleton, Prototype
  - `patterns/structural/` — Adapter, Bridge, Composite, Decorator, Facade, Flyweight, Proxy
  - `patterns/behavioral/` — Strategy, Observer, Command, State, Template Method, Chain of Responsibility, Iterator, Mediator, Memento, Visitor

- **CLAUDE.md** — AI-specific instructions for working with patterns

**Key files to reference:**

- `patterns/README.md` — Decision tree for choosing the right pattern

- Individual pattern files — Each includes: problem, solution, Python + TypeScript examples, pitfalls, when to use/avoid

---

## Books

### Clean Code (Must Read)

**Robert C. Martin, *Clean Code: A Handbook of Agile Software Craftsmanship***
(Prentice Hall, 2008)

The foundation for all the rules in this guide. Chapters 2-10 cover naming,
functions, comments, formatting, error handling, and unit testing.

**Key chapters for Gideon:**

- Chapter 2: Meaningful Names

- Chapter 3: Functions

- Chapter 4: Comments

- Chapter 5: Formatting

- Chapter 10: Classes

- Chapter 11: Systems

### Clean Architecture (Highly Recommended)

**Robert C. Martin, *Clean Architecture: A Craftsman's Guide to Software
Structure and Design*** (Prentice Hall, 2017)

Deep dive into layered architecture, SOLID principles, and system design.

**Key chapters:**

- Part II: Starting with the Bricks (SOLID principles)

- Part III: Design Principles (component cohesion, coupling)

- Part IV: Architecture (layers, independence)

### Dependency Injection (Advanced)

**Mark Seemann, *Dependency Injection Principles, Practices, and Patterns***
(Manning, 2019)

Essential reading if you're working on the FastAPI backend. Shows how to
structure injectable dependencies so code remains testable and flexible.

---

## Online Resources

### Refactoring.Guru Design Patterns

<https://refactoring.guru/design-patterns>

Excellent visual guide to all 23 GoF patterns. Each includes:

- Problem description

- UML diagrams

- Code examples (Python, Java, C#, Go, etc.)

- Pros/cons

- When to use

### Clean Code YouTube Lectures

Uncle Bob (Robert Martin) recorded lectures on Clean Code and Clean
Architecture available on YouTube. Highly worth watching while working.

---

## Gideon-Specific Resources

### Security & Legal

- [CLAUDE.md](../CLAUDE.md) — Project context, security rules, architecture

- [docs/LEGAL_COMPLIANCE.md](../LEGAL_COMPLIANCE.md) — Criminal procedure rules

- [docs/AUTHENTICATION.md](../AUTHENTICATION.md) — JWT, MFA, access control

### Architecture

- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — Service topology, data flows

- [docs/TASKS.md](../TASKS.md) — Celery jobs and background task architecture

- [docs/OBSERVABILITY.md](../OBSERVABILITY.md) — Logging and monitoring

### Development

- [docs/DEPLOYMENT.md](../DEPLOYMENT.md) — Production deployment

- [docs/LOCAL_DEPLOYMENT.md](../LOCAL_DEPLOYMENT.md) — Local development setup

- [CONTRIBUTING.md](../../CONTRIBUTING.md) — How to contribute

---

## Quick Lookup

**Question:** How do I handle errors?

- **Answer:** [Clean Code Rule 20](clean-code.md#rule-20-never-suppress-errors-silently)

**Question:** My class has too many responsibilities.

- **Answer:** [SOLID SRP](clean-architecture.md#s-single-responsibility-principle-srp) + [Clean Code Rule 25](clean-code.md#rule-25-single-responsibility-principle-srp)

**Question:** I'm creating lots of similar objects.

- **Answer:** [Factory Method](design-patterns.md#factory-method) or [Builder](design-patterns.md#builder)

**Question:** I have multiple algorithms for the same task.

- **Answer:** [Strategy Pattern](design-patterns.md#strategy)

**Question:** Multiple objects need to react to an event.

- **Answer:** [Observer Pattern](design-patterns.md#observer)

**Question:** Do I need to encrypt this?

- **Answer:** Check [Gideon Essentials](gideon-essentials.md#security--privacy--non-negotiable)

**Question:** Can I delete this document?

- **Answer:** Check [Legal Hold](gideon-essentials.md#5-legal-hold--immutable)

**Question:** Can I send this to an external service?

- **Answer:** No. See [No Third-Party LLM API Calls](gideon-essentials.md#1-no-third-party-llm-api-calls)

---

## About This Guide

This guide is maintained by the Gideon project maintainers. It pulls from:

1. **Universal best practices** — Codified from Clean Code, Clean Architecture,
   and engineering experience
2. **Gideon-specific practices** — Security, legal, and domain constraints
3. **Team experience** — Patterns and anti-patterns the team has learned

Questions or suggestions? Open an issue or submit a PR.

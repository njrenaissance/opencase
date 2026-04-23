# Clean Code Principles

These essential rules are from Robert C. Martin's *Clean Code*. They apply to
Python, TypeScript, and all code in Gideon. (Full 40-rule set with extended
explanations available in [engineering-standards repo](../references.md).)

---

## Naming

### Rule 2: Use Intentional Names

Names should reveal intent. A name is bad if it requires a comment to explain
what it does.

- ❌ BAD: `d`, `elapsed`, `theList`, `genymdhms`

- ✅ GOOD: `daysSinceModification`, `accounts`, `generationTimestamp`

### Rule 3: Avoid Disinformation

Names should not mislead.

- ❌ BAD: `accountList` (if it's not a list), `accountGroup` (if it's not a group)

- ✅ GOOD: `accounts` (let the type system tell you it's a list/array)

### Rule 4: Make Pronounceable Names

Code is read aloud in discussions. Make names pronounceable.

- ❌ BAD: `genymdhms`, `DtaRcrd`

- ✅ GOOD: `generationTimestamp`, `customerRecord`

### Rule 5: Make Names Searchable

Single-letter names and numeric constants are hard to grep for.

- ❌ BAD: `for (int j = 0; j < 34; j++) { ...}`

- ✅ GOOD: `for (int pageSize = 34; ...)`; declare constants with names

### Rule 6: Avoid Encodings

Don't embed type or scope information in the name.

- ❌ BAD: `strAccountName`, `m_name` (member prefix), `iAccountId` (integer prefix)

- ✅ GOOD: `accountName`, `name`, `accountId` (let the IDE and type system do the work)

---

## 2. Functions

### Rule 7: Small Functions

Functions should do one thing. If it has more than 10-20 lines, it's probably
doing too much. Split it.

- ❌ BAD: A 200-line function that validates, transforms, logs, and saves

- ✅ GOOD: Five 30-line functions, each doing one task

### Rule 8: One Level of Abstraction

All statements in a function should be at the same level of abstraction.

- ❌ BAD: Mix high-level business logic (`calculate_tax`) with low-level
  details (`parse_file`, `open_stream`)

- ✅ GOOD: `calculate_tax` calls `get_income` and `get_deductions` (same level)

### Rule 9: Use Descriptive Names

Function names should describe what they do.

- ❌ BAD: `process`, `handle`, `do_stuff`

- ✅ GOOD: `build_permissions_filter`, `validate_email`, `serialize_document`

### Rule 10: Few Arguments

Functions should have 0-2 arguments. More than 3 is hard to test and understand.

- ❌ BAD: `create_user(name, email, phone, address, role, department, manager)`

- ✅ GOOD: `create_user(user_data)` where `user_data` is a dict/object

### Rule 11: No Flag Arguments

Don't use boolean arguments to control function behavior. Split into two
functions instead.

- ❌ BAD: `render_document(doc, format=True)` (does it render or not?)

- ✅ GOOD: `render_document(doc)` and `render_document_formatted(doc)`

### Rule 12: No Side Effects

Functions should not modify state outside their scope. They should do what
their name says, nothing more.

- ❌ BAD: `validate_user()` that also logs, sends an email, and updates lastSeen

- ✅ GOOD: `validate_user()` returns true/false; caller handles side effects

---

## 3. Comments

### Rule 13: Comments Should Explain WHY, Not WHAT

The code explains what it does. Comments should explain why it does it.

- ❌ BAD: `// increment counter` (the `++` already says that)

- ✅ GOOD: `// retry with exponential backoff because Qdrant can be slow under load`

### Rule 14: Warn of Consequences

Use comments to flag performance gotchas, non-obvious dependencies, or risks.

- ✅ GOOD: `// WARNING: This query is O(n²) on document count. Optimize if corpus > 100k docs.`

- ✅ GOOD: `// NOTE: build_permissions_filter() MUST be called here or we leak data across firms`

### Rule 15: Don't Comment Out Code

Delete dead code. Version control has history if you need to resurrect it.

- ❌ BAD: `// if (some_old_logic) { ... }`

- ✅ GOOD: Delete it. `git log` will find it if needed.

---

## 4. Formatting

### Rule 16: Declare Variables Close to Use

Don't declare variables at the top of the function.

- ❌ BAD: All variables at the top of a 100-line function

- ✅ GOOD: Declare variables immediately before use

### Rule 17: Place Caller Above Callee

If function A calls function B, define A before B in the file. Readers see
the high-level logic first.

- ❌ BAD: Define `_helper_function()` first, then call it from `main()`

- ✅ GOOD: Define `main()` first, then helpers below

---

## 5. Objects & Data

### Rule 18: Hide Internal Data

Use getters/setters or properties, not public fields. Never let external code
directly modify internal state.

- ❌ BAD: `user.name = "Alice"`

- ✅ GOOD: `user.set_name("Alice")` (allows validation)

### Rule 19: Law of Demeter (No Train Wrecks)

Don't chain method calls across object boundaries.

- ❌ BAD: `user.get_address().get_city().get_name()`

- ✅ GOOD: `user.get_city_name()` (user handles the chain internally)

---

## 6. Error Handling

### Rule 20: Never Suppress Errors Silently

If an error occurs, handle it explicitly. Never catch and ignore.

- ❌ BAD: `try: validate(x) except: pass`

- ✅ GOOD: `try: validate(x) except ValidationError as e: log_error(e); raise`

---

## 7. Unit Tests

### Rule 21: One Assertion Per Test

Each test should verify one outcome. Multiple assertions in one test make it
hard to see what failed.

- ❌ BAD: `test_user()` with 10 assertions about user creation

- ✅ GOOD: `test_user_requires_email()`, `test_user_validates_phone()`, etc.

### Rule 22: Tests Must Be Fast

Slow tests won't be run. Unit tests should execute in milliseconds, not seconds.

- ❌ BAD: Tests that hit the database, sleep, or make HTTP calls

- ✅ GOOD: Unit tests with mocks; integration tests in separate suite

### Rule 23: Tests Must Be Independent

Tests should not depend on each other or shared state.

- ❌ BAD: Test A creates data that Test B relies on

- ✅ GOOD: Each test sets up its own fixtures

### Rule 24: Test Names Should Describe Behavior

Test names should read like sentences describing what is being tested.

- ❌ BAD: `test_user()`, `test_create()`

- ✅ GOOD: `test_user_requires_valid_email()`, `test_create_fails_with_duplicate_email()`

---

## 8. Classes

### Rule 25: Single Responsibility Principle (SRP)

A class should have one reason to change.

- ❌ BAD: A `User` class that handles validation, persistence, email sending, logging

- ✅ GOOD: `User` (entity), `UserRepository` (persistence), `UserValidator` (validation)

---

## 9. Systems

### Rule 26: Dependency Injection

Don't instantiate dependencies inside a class. Inject them.

- ❌ BAD: `class UserRepository: def __init__(self): self.db = Database()`

- ✅ GOOD: `class UserRepository: def __init__(self, db: Database):`

---

## 10. Concurrency

### Rule 27: Keep Concurrency Separate from Business Logic

Don't mix threading, async/await, or locks into business logic. Use a separate
layer.

- ❌ BAD: Business logic with `async/await` sprinkled throughout

- ✅ GOOD: Pure business logic; async wrappers at the boundary

---

## 11. Additional Principles

### Rule 28: KISS (Keep It Simple, Stupid)

Simple code is better than clever code. Never optimize for cleverness.

- ❌ BAD: One-liners that are hard to understand

- ✅ GOOD: Three lines that are obvious

### Rule 29: Use Value Objects Over Primitives

Avoid passing around naked strings, ints, bools. Wrap them in types.

- ❌ BAD: `validate_phone(phone_string)`

- ✅ GOOD: `phone = Phone("212-555-1234"); validate(phone)`

### Rule 30: Avoid Rigidity

Code that's hard to change is rigid. Prefer composition over inheritance,
interfaces over concrete classes, and dependency injection over global state.

### Rule 31: Reduce Nesting

Deep nesting is hard to follow. Flatten it with early returns or extracted
functions.

- ❌ BAD: 5 levels of if-else nesting

- ✅ GOOD: Guard clauses and early returns

### Rule 32: Avoid Over-Engineering

Don't build for hypothetical futures. Solve the problem in front of you.

### Rule 33: Use Discriminated Unions (Enums) Over Strings

- ❌ BAD: `status = "pending"` (typos lead to bugs)

- ✅ GOOD: `status = DocumentStatus.PENDING` (compiler catches typos)

### Rule 34: Use `unknown` Instead of `any` (TypeScript)

- ❌ BAD: `const x: any = fetchData();`

- ✅ GOOD: `const x: unknown = fetchData(); // now you must narrow the type`

---

## Pre-Commit Checklist

Before committing, verify:

- [ ] Naming is intentional and searchable

- [ ] Functions are small (<20 lines) and do one thing

- [ ] No boolean flag arguments

- [ ] No side effects outside function scope

- [ ] Comments explain WHY, not WHAT

- [ ] No dead code or commented-out code

- [ ] Variables declared close to use

- [ ] No train wrecks (Law of Demeter)

- [ ] Error handling is explicit, never silent

- [ ] Tests verify one outcome each

- [ ] Test names describe behavior

- [ ] Classes have single responsibility

- [ ] Dependencies are injected

- [ ] Code passes linting and type checking

---

## Further Reading

- Robert C. Martin, *Clean Code* (Prentice Hall, 2008)

- See [design-patterns.md](design-patterns.md) for structural guidance

- See [clean-architecture.md](clean-architecture.md) for SOLID principles

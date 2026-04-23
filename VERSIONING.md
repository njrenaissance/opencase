# Versioning

Gideon follows [Semantic Versioning](https://semver.org/) (SemVer) combined with named major releases honoring famous jurists.

## Version Format

Versions follow the format: `MAJOR.MINOR.PATCH`

- **MAJOR** — Incompatible API changes, breaking changes, removed features
- **MINOR** — New backwards-compatible features
- **PATCH** — Backwards-compatible bug fixes

## Version Bumping Rules

Version bumps are determined by commit types following the
[Conventional Commits](https://www.conventionalcommits.org/) specification:

| Commit Type | Semver Bump | Example |
| --- | --- | --- |
| `feat:` | MINOR (0.X.0) | `feat: add bulk send feature` |
| `fix:` | PATCH (0.0.X) | `fix(auth): resolve login timeout` |
| `feat!:` or `BREAKING CHANGE:` | MAJOR (X.0.0) | `feat!: redesign API` |
| `docs:`, `style:`, `refactor:`, `perf:`, `test:`, `build:`, `ci:`, `chore:` | PATCH (0.0.X) | `docs: update API guide` |

**Breaking Change Indicator:** When a commit is a breaking change, append `!` after the type (e.g., `feat!: ...`) or include `BREAKING CHANGE:` in the commit footer. This triggers a major version bump.

## Named Major Releases

Major releases (MAJOR version bumps) are named after famous jurists in honor of their contributions to justice and the rule of law.

| Version | Codename | Jurist | Released |
| --- | --- | --- | --- |
| v1.0 | Ginsburg | Ruth Bader Ginsburg | — |

Future major releases will follow this naming pattern.

## Pre-Release Versions

Pre-release versions (before v1.0) use the format `0.MINOR.PATCH`:

- `0.1.0` — first feature release (alpha/beta)
- `0.2.0` — subsequent feature releases
- etc.

Breaking changes during pre-release (`0.x.x`) **also bump MINOR** (not MAJOR), since the API is not yet stable.

## Release Cadence

Releases are created when milestones are achieved or enough significant features/fixes accumulate. There is no fixed schedule.

## Automated Release Tooling (In Progress)

Version bumping and release automation are currently in development. When
complete, releases will be automated via GitHub Actions using Conventional
Commits to determine version bumps and generate changelogs. See GitHub
Issues for tracking.

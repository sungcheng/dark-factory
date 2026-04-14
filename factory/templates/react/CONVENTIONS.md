# Engineering Conventions

Organization-wide engineering standards. Every project managed by Dark Factory must follow these conventions. These are non-negotiable.

---

## 1. Project Structure

Every project must have:

```
├── CONVENTIONS.md          # This file (org-wide, don't modify per-project)
├── STYLEGUIDE.md           # Code style rules (project-specific)
├── CHANGELOG.md            # Version history (Keep a Changelog format)
├── README.md               # How to run, develop, test, deploy
├── DESIGN.md               # Architecture decisions and rationale
├── .editorconfig            # Consistent editor settings
��── .gitignore               # Language-appropriate ignores
├── .env.example             # All env vars with placeholder values
├── .github/workflows/ci.yml # CI pipeline
├── Makefile                 # Standard targets (see below)
└── Dockerfile               # Multi-stage, non-root user
```

### Required Makefile Targets

Every project, regardless of language:

```makefile
make develop    # Install all dependencies (dev + prod)
make test       # Run full test suite
make check      # Lint + type check + format check
make format     # Auto-format code
make build      # Build production artifact
make clean      # Remove all build artifacts
```

---

## 2. Git & Branching

### Branch Naming
- `feature/<short-description>` — new functionality
- `fix/<short-description>` — bug fixes
- `chore/<short-description>` — maintenance, deps, CI
- `docs/<short-description>` — documentation only

Branches are **short-lived**. Merge within days, not weeks. No long-running feature branches.

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add weather forecast endpoint
fix: handle empty city name in geocoding
chore: update httpx to 0.28.1
docs: add API versioning section to DESIGN.md
test: add edge cases for cache expiry
refactor: extract geocoding into separate module
```

- Imperative mood ("add" not "added")
- Lowercase first word after prefix
- No period at the end
- Body optional — use for "why", not "what"

### Tags & Versioning

- **Semantic versioning**: `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)
- **Tag every release**: `git tag -a v1.2.3 -m "Release 1.2.3"`
- MAJOR = breaking API changes
- MINOR = new features, backward compatible
- PATCH = bug fixes, backward compatible
- Pre-release: `v1.2.3-rc.1` for release candidates

---

## 3. Pull Requests

### Size Limits
- **Max 400 lines changed** (excluding generated files, lock files, test fixtures)
- If larger, split into stacked PRs
- Exception: initial scaffolding or large refactors (document why in PR description)

### PR Structure
- **Title**: conventional commit format (`feat: add forecast endpoint`)
- **Description**: what changed, why, how to test
- **One logical change per PR** — don't mix features with refactors

### Review Checklist
- [ ] Tests pass (`make test`)
- [ ] Lint passes (`make check`)
- [ ] No secrets in code
- [ ] API backward compatible (or migration plan documented)
- [ ] CHANGELOG.md updated
- [ ] README/DESIGN.md updated if behavior changed
- [ ] New env vars added to `.env.example`

---

## 4. API Design

### Versioning
- All endpoints under `/api/v1/` prefix
- Never remove or rename existing fields — only add new ones
- Deprecate with `Deprecated` header and timeline, don't delete
- New major version = new prefix (`/api/v2/`) alongside old one

### Backward Compatibility
- **Adding fields**: safe, always backward compatible
- **Removing fields**: NEVER in a minor/patch release
- **Renaming fields**: add new name, keep old as alias, deprecate old
- **Changing types**: NEVER — add a new field instead
- **Removing endpoints**: deprecate first, remove in next major version

### Response Standards
- **Success**: return the resource directly (`{"city": "London", ...}`)
- **Errors**: `{"detail": "Human-readable message"}`
- **Status codes**: 200 OK, 201 Created, 202 Accepted, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 410 Gone, 422 Validation Error, 429 Rate Limited, 500 Internal Server Error, 502 Bad Gateway
- **Pagination**: `?page=1&per_page=20` with `Link` headers or `next`/`previous` in response
- **Timestamps**: ISO 8601 UTC (`2026-04-06T12:00:00Z`)

### Resource Identifiers
- **Never expose sequential integer IDs** in external-facing URLs or response bodies. Sequential IDs leak information (creation order, volume) and let attackers enumerate neighbors (`/users/1` → `/users/2` → …).
- **Use unguessable identifiers** for any resource crossing the API boundary: UUIDs (v4 or v7), ULIDs, or equivalent opaque tokens with ≥122 bits of entropy.
- **Sequential primary keys are fine internally** — for joins and indexes within your own database — but must never appear in URLs, cursors, or response payloads.
- **Exception**: intentionally public slugs like tag names or category identifiers where enumeration is the point (e.g., `/categories/electronics`).

---

## 5. Deploy Order & Strategy

### Deploy Sequence
1. **Database migrations first** — schema changes must be backward compatible with current code
2. **Backend second** — new code works with both old and new schema
3. **Frontend last** — new UI only after backend supports it

### Backward Compatibility Rule
- Backend must support the **current frontend AND the previous version** simultaneously
- Never deploy a backend that breaks the currently running frontend
- Use feature flags for changes that can't be backward compatible

### Rollback
- Every deploy must be rollback-safe
- Database migrations must be reversible (no `DROP` without a deprecation period)
- If a rollback would lose data, document it and require explicit approval
- Feature flags for risky changes — deploy off, enable gradually

---

## 6. Database & Migrations

### Migration Rules
- **Forward-only, reversible**: every migration has an `upgrade()` and `downgrade()`
- **One concern per migration**: don't mix schema changes with data migrations
- **Never destructive in production**: no `DROP TABLE`, `DROP COLUMN`, or `TRUNCATE` without a deprecation period
- **Separate schema from code deploys**: migration runs before code deploy

### Safe Migration Pattern
1. **Add** new column/table (nullable or with default)
2. **Deploy** code that writes to both old and new
3. **Backfill** data from old to new
4. **Deploy** code that reads from new only
5. **Remove** old column/table (next release cycle)

### Data Access
- **Parameterized queries only** — never string-concatenate user input into SQL
- **ORM for CRUD, raw SQL for complex queries** — don't fight the ORM
- **Indexes on foreign keys and frequently filtered columns**
- **Connection pooling** in production; scope one connection per request
- **Commit writes explicitly** — don't rely on implicit transactions
- **Bulk writes batched** — never row-at-a-time for large inserts
- **Schema init is idempotent** — safe to re-run on every startup

### Pagination
- **Cursor-based over offset** for anything that might grow past a few thousand rows or where concurrent writes could shift rows between pages. Offset pagination silently skips moved rows.
- **Opaque cursors** — don't leak internal IDs to clients
- **Hard cap on page size** — never allow unbounded result sets
- **Stable sort order** — pagination requires a total ordering; never rely on insertion order

Page-based (`?page=N`) is acceptable for small, admin-only datasets. Never use it for user-facing or high-volume data.

---

## 7. Testing

### Testing Pyramid
- **70% unit tests**: fast, isolated, test business logic
- **20% integration tests**: test module boundaries, database, API contracts
- **10% E2E tests**: critical user journeys only

### Test Discipline
- **2-4 tests per function**: happy path + edge cases + error case
- **Use `parametrize`** instead of duplicating tests with different inputs
- **Name by feature**: `test_weather.py`, never `test_issue13_task1.py`
- **Delete stale tests** — tests for deleted code are dead weight
- **Mock at boundaries**: HTTP, DB, filesystem, external APIs
- **Never mock your own code**: test real integration between your modules
- **Target 80% coverage** on new code — don't chase 100%

### What NOT to Test
- Framework behavior (don't test that FastAPI routing works)
- Private/internal functions (test through the public API)
- Implementation details (exact call counts, internal state)
- Third-party library internals
- Trivial getters/setters

---

## 8. Error Handling & Logging

### Error Handling
- **Never bare `except:`** — always catch specific exceptions
- **Never silently swallow exceptions** — at minimum, log them
- **Custom exceptions for domain errors**: `CityNotFoundError`, not `ValueError`
- **HTTP exceptions for API errors**: `HTTPException(404, "City not found")`
- **Early returns for errors**: keep the happy path unindented
- **Fail fast**: validate inputs at system boundaries, trust internal code

### Logging
- **Structured logging**: JSON format in production, human-readable in dev
- **Log levels mean something**:
  - `ERROR` = requires human intervention, pages on-call
  - `WARNING` = unexpected but handled, investigate later
  - `INFO` = normal operations, request lifecycle
  - `DEBUG` = detailed internals, off in production
- **Include context**: `LOG.info("Fetched weather", extra={"city": city, "source": "cache"})`
- **Never log secrets**: API keys, tokens, passwords, PII
- **Correlation IDs**: every request gets a unique ID, propagated through all log lines

---

## 9. Security

### Secrets
- **Never in code**: no API keys, tokens, passwords in source files
- **Environment variables only**: loaded via `.env` + `python-dotenv` (or equivalent)
- **`.env.example` in repo**: with placeholder values, never real secrets
- **`.env` in `.gitignore`**: never committed
- **Scan on every PR**: automated secret detection

### Input Validation
- **Validate at system boundaries**: API inputs, webhook payloads, file uploads
- **Trust internal code**: don't re-validate between your own modules
- **Pydantic/Zod for schema validation**: never manual parsing of request bodies
- **Parameterized queries**: never string-concatenate user input into SQL

### Dependencies
- **Pin exact versions** in lock files (`uv.lock`, `package-lock.json`)
- **Audit regularly**: `npm audit`, `pip-audit`, `bandit`
- **Update deps in dedicated PRs**: never mixed with feature work
- **No phantom dependencies**: everything you import must be in your manifest

---

## 10. Dependencies

### Rules
- **Minimize dependencies**: stdlib first, well-known libraries second, new deps last
- **One library per concern**: don't install two HTTP clients, two ORMs, two test frameworks
- **Lock files committed**: `uv.lock`, `package-lock.json` are always in git
- **Update cadence**: monthly dependency update PR, reviewed and tested
- **No pre-1.0 dependencies in production** without explicit justification

### Adding a New Dependency
Before adding a dependency, check:
1. Can the stdlib handle this?
2. Does an existing dependency already do this?
3. Is it actively maintained (commits in last 6 months)?
4. Is it widely used (>1000 GitHub stars or equivalent)?
5. Does its license allow commercial use?

---

## 11. Documentation

### README.md (required)
- **What it is**: one-sentence description
- **How to run locally**: step-by-step, copy-pasteable commands
- **How to run tests**: `make test`
- **How to deploy**: or link to deploy docs
- **Environment variables**: table of all vars with descriptions
- **API endpoints**: summary table or link to OpenAPI docs

### DESIGN.md (required)
- **Architecture overview**: components, how they interact
- **Key decisions**: what was chosen and WHY (not just what)
- **Trade-offs**: what was considered and rejected
- **Data model**: entity relationships, key schemas
- Updated when architecture changes — same PR as the code change

### CHANGELOG.md (required)
- [Keep a Changelog](https://keepachangelog.com/) format
- Updated in every PR that changes behavior
- Categories: Added, Changed, Deprecated, Removed, Fixed, Security

### Inline Documentation
- **Docstrings on public functions**: explain what, not how
- **Comments for WHY, not WHAT**: `# Retry because OpenWeather rate-limits at 60/min` not `# retry 3 times`
- **No commented-out code**: delete it, git has history

### Codebase Context Files

Every project must maintain context files so developers (human and AI) can navigate the codebase without reading every file:

**`ARCHITECTURE.md`** (project root, required):
- High-level component diagram: what the major pieces are and how they connect
- Data flow: how a request travels through the system
- External dependencies: what third-party services are used and why
- Updated when components are added/removed or data flow changes

**`CONTEXT.md`** (one per module/package directory):
- What this module does (one paragraph)
- Public API: exported functions/classes with signatures and one-line descriptions
- Dependencies: what other modules this one imports/calls
- Key decisions: non-obvious choices and why they were made
- Updated by the Developer whenever they change the module

Example `CONTEXT.md`:
```markdown
# Weather Service

Fetches weather data from OpenWeather One Call API 3.0 with geocoding and caching.

## Public API
- `geocode_city(city: str) -> tuple[float, float]` — resolve city name to lat/lon
- `fetch_current_weather(city: str) -> WeatherResponse` — current conditions
- `fetch_forecast(city: str) -> ForecastResponse` — 5-day daily forecast

## Dependencies
- `src.cache` — get_cached/set_cached for response caching
- `src.config` — OpenWeather API key
- External: OpenWeather Geocoding API, One Call API 3.0

## Key Decisions
- Using units=metric so API returns Celsius directly (no Kelvin conversion)
- Geocoding results cached separately from weather data (different TTL)
```

---

## 12. Environment & Configuration

### Environment Parity
- Dev, staging, and production should be as similar as possible
- Same database engine, same dependency versions, same OS
- **No environment-specific logic in code**: use configuration, not `if env == "prod"`

### Configuration
- **All config from environment variables**: never hardcoded
- **`.env.example` always in sync**: every new env var gets a placeholder added
- **Sensible defaults for dev**: app should start with just `.env.example` copied to `.env`
- **No secrets in defaults**: placeholder values only (`OPENWEATHER_API_KEY=your_key_here`)

### CI Pipeline
Every push/PR must run:
1. Lint and format check
2. Type check
3. Full test suite
4. Build verification (Docker build or equivalent)
5. Secret scan

---

## 13. Monitoring Readiness

Even if full monitoring isn't set up yet, every project must be **ready** for it:

- **Health check endpoint**: `GET /api/v1/health` returning `{"status": "ok"}`
- **Structured error responses**: consistent format, parseable by monitoring tools
- **Request logging**: method, path, status code, duration for every request
- **No swallowed errors**: every exception either handled explicitly or logged
- **Metrics-friendly**: key operations should be easy to instrument (clear function boundaries, no god functions)

---

## 14. Separation of Concerns

Any service that persists data or has non-trivial business logic must separate layers. Never collapse them into a single file.

- **Routing layer** — parses requests, delegates, serializes responses. No business rules, no data access.
- **Business-logic layer** — decisions, validation, orchestration. No knowledge of HTTP or storage. Takes a data-access dependency. Testable in isolation.
- **Data-access layer** — reads and writes persistent state. No business rules. One class per entity.
- **Internal domain types vs wire schemas** — domain objects describe what the system *is*; wire schemas describe what goes over the network. They have different lifecycles. Don't conflate them.

### Anti-patterns (reject in review)
- God-file doing routing + parsing + storage + business logic in one place
- Business logic inside route handlers (handlers should only parse, delegate, serialize)
- Storage queries outside the data-access layer
- Business-logic layer importing the web framework
- Generic module names (`utils.py`, `helpers.py`, `common.py`) — use concrete names
- Module-level I/O or background work at import time — defer to explicit startup hooks

---

## 15. Long-Running Operations

When an operation takes more than a few seconds:

- **Stream, don't buffer** — never load an entire payload into memory. Process in bounded chunks, write results incrementally.
- **Report progress** — clients need visibility into operation state.
- **Throttle progress updates** — publishing on every iteration drowns consumers. Report at a sensible cadence and always on the final tick.
- **Be cancellable** — clients disappear. Detect disconnects and stop doing work for gone consumers.
- **Clean up idempotently** — cleanup code must not crash if the target is already gone or was never created.
- **Graceful shutdown** — drain in-flight work before terminating; never cancel mid-transaction.
- **Survive individual failures** — one bad job must not take down the worker pool. Isolate failures per unit of work.

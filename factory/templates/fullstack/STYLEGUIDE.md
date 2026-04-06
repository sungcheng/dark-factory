# Style Guide

This document defines the coding standards for this project. All contributors (human and AI) must follow these rules.

## Python

### Formatting
- **Formatter**: ruff format
- **Line length**: 88 characters
- **Indentation**: 4 spaces, no tabs
- **Trailing commas**: always in multi-line lists, dicts, function args, and function parameters
- **Quotes**: double quotes for strings (`"hello"`), single quotes only inside f-strings when needed
- **Blank lines**: 2 between top-level definitions, 1 between methods in a class

### Naming
- **Variables/functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: single leading underscore (`_internal_helper`)
- **No abbreviations**: `temperature` not `temp`, `configuration` not `config` (except well-known: `url`, `api`, `db`, `id`)

### Imports
- **Order**: stdlib, blank line, third-party, blank line, local
- **One per line**: no multi-imports (`from os import path, getcwd`)
- **No wildcard imports**: never `from module import *`
- **Absolute imports only**: no relative imports

### Functions
- **Type hints on everything**: parameters and return types, no exceptions
- **Docstrings on all public functions**: Google style with Args/Returns/Raises sections
- **Max function length**: ~30 lines. If longer, extract helper functions
- **Single responsibility**: one function does one thing

```python
def fetch_weather(city: str, units: str = "metric") -> WeatherResponse:
    """Fetch current weather for a city.

    Args:
        city: City name to look up.
        units: Temperature units (metric or imperial).

    Returns:
        WeatherResponse with current conditions.

    Raises:
        HTTPException: If city not found (404) or service unavailable (502).
    """
```

### Error Handling
- **Never bare `except:`** — always catch specific exceptions
- **Never silently swallow exceptions** — at minimum, log them
- **Use custom exceptions** for domain errors, HTTP exceptions for API errors
- **Early returns** for error cases, keep the happy path unindented

### Data Structures
- **Pydantic models** for all API request/response schemas
- **Dataclasses** for internal data containers
- **TypedDict** only when interfacing with untyped dicts (e.g., JSON from external APIs)
- **Enums** for fixed sets of values, never magic strings

### Strings
- **f-strings only**: never `.format()`, never `%` formatting
- **No string concatenation with `+`**: use f-strings or `"".join()`
- **Multi-line strings**: use triple quotes, not concatenation

### Collections
- **List/dict/set comprehensions** preferred over `map()`/`filter()`
- **Always trailing comma** in multi-line collections:

```python
# Yes
cities = [
    "London",
    "Paris",
    "Tokyo",
]

# No
cities = [
    "London",
    "Paris",
    "Tokyo"
]
```

## SQL

- **Keywords uppercase**: `SELECT`, `FROM`, `WHERE`, `JOIN`, `ORDER BY`
- **One column per line** in SELECT statements
- **Always alias tables**: `FROM users u JOIN orders o ON u.id = o.user_id`
- **CTEs over subqueries**: use `WITH` for readability
- **Parameterized queries only**: never string-concatenate values

## API Design

- **All endpoints versioned**: `/api/v1/resource`
- **RESTful naming**: plural nouns (`/users`, `/orders`), no verbs in URLs
- **Proper HTTP status codes**: 200 OK, 201 Created, 404 Not Found, 422 Validation Error, 502 Bad Gateway
- **Consistent error response**: `{"detail": "Error message"}`
- **Pagination** for list endpoints returning more than 20 items

## Testing — Python (pytest)

### Pyramid
- **70% unit tests** (fast, isolated) / **20% integration** / **10% E2E**
- **2-4 tests per function**: happy path + 1-2 edge cases + error case. Not 20.
- If you need more, use `@pytest.mark.parametrize` instead of duplicating test functions

### Organization
- **One test file per source module**: `test_weather.py` mirrors `weather_service.py`
- **Never name by issue/task**: `test_weather.py` not `test_issue13_task1_weather.py`
- **Group with classes**: `class TestFetchWeather:`, `class TestGeocoding:`
- **Shared fixtures in `conftest.py`**: DB setup, mock clients, test data factories
- **Structure**: `tests/unit/`, `tests/integration/` if the project is large enough

### Naming
- **Pattern**: `test_<function>_<scenario>` — e.g., `test_fetch_weather_returns_404_when_city_not_found`
- **Describe behavior, not implementation**: what it does, not how

### What to Test
- Business logic and state transitions
- Error conditions and edge cases
- Public API contracts (request → response)
- Data validation rules

### What NOT to Test
- Framework/library behavior (don't test FastAPI routing works)
- Private helper functions (test through the public API)
- Implementation details (exact number of DB calls, internal state)
- Trivial getters/setters
- Third-party library internals

### Mocking
- **Mock at boundaries only**: HTTP calls, database, filesystem, external APIs, time
- **Never mock your own code**: test real integration between your modules
- **Use dependency injection** for mockability, not monkey-patching
- **Mock responses should be realistic**: use actual API response shapes, not `{"data": "test"}`

### Fixtures
- **Shared expensive fixtures** via `conftest.py` with appropriate scope
- **Factory functions for test data**: `make_weather_response(city="London", temp=20.0)`
- **Each test is self-contained**: never depend on state from another test
- **Minimal setup**: only create what the test needs

### Coverage
- **Target 80%** for new code — critical paths + error handling
- **Don't chase 100%**: coverage != quality
- **Every branch that changes behavior** must be tested

### Cleanup Rules
- **Delete duplicate tests immediately** — same scenario, different name = bloat
- **Use `@pytest.mark.parametrize`** instead of copy-pasting tests with different inputs
- **Remove stale tests** after refactoring — tests that test deleted code are dead weight
- **When changing a function's behavior**, update existing tests — don't add new ones alongside old ones

## Testing — React (vitest + Testing Library)

### Organization
- **Co-located or in `__tests__/`**: `WeatherCard.tsx` + `WeatherCard.test.tsx`
- **One test file per component**
- **No snapshot tests**: they break on every change and catch nothing useful

### What to Test
- **User interactions**: click, type, submit
- **Rendered output**: what the user sees, not internal state
- **Conditional rendering**: loading, error, empty states
- **Accessibility**: elements findable by role, label, text

### What NOT to Test
- React internals (useState, useEffect behavior)
- CSS classes (test behavior, not styling)
- Third-party component internals

### Patterns
- **Use `getByRole`, `getByText`** — not `getByTestId` (last resort)
- **`userEvent` over `fireEvent`**: more realistic interaction simulation
- **Descriptive names**: `it("shows error message when API returns 502")`
- **Mock API at the fetch level**: `vi.mock` or MSW, never mock React hooks

## Git

- **Commit messages**: imperative mood ("Add feature" not "Added feature")
- **One logical change per commit**
- **No generated files committed**: no `__pycache__`, no `node_modules`, no `.env`, no build artifacts

# ABOUTME: Task runner recipes for the stratification app - see https://just.systems
# ABOUTME: `just test` runs all the tests, `just check` runs linting and type checking

# list the available recipes
default:
    @just --list

# run all the tests
test *args:
    uv run pytest {{ args }}

# run the unit tests only - no Qt, no network
test-unit *args:
    uv run pytest tests/unit {{ args }}

# run the tests with a coverage report
test-cov *args:
    uv run pytest --cov=strat_app --cov-report=term-missing {{ args }}

# run the linter and the type checker
check:
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy .

# fix the lint problems that can be fixed automatically
fix:
    uv run ruff check --fix .
    uv run ruff format .

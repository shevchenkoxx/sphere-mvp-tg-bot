.PHONY: lint format typecheck test check compile-check install-dev

# Quick lint check (ruff)
lint:
	ruff check .

# Auto-fix lint issues
lint-fix:
	ruff check --fix .

# Format code
format:
	ruff format .

# Type checking (mypy)
typecheck:
	mypy adapters/ core/ infrastructure/ config/ main.py

# Run tests
test:
	pytest tests/

# Compile check — verify all Python files parse correctly
compile-check:
	@echo "Checking Python compilation..."
	@find . -name "*.py" -not -path "./.venv/*" -not -path "./venv/*" | xargs -I {} python3 -m py_compile {} && echo "All files compile OK"

# Full quality gate — run before committing
check: lint typecheck compile-check test
	@echo "All checks passed!"

# Install dev dependencies
install-dev:
	pip install ruff mypy pytest pytest-asyncio pre-commit
	pre-commit install

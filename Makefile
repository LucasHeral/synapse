.PHONY: install sync dev run test lint format precommit clean

UV = /Users/lucas.heral/.local/bin/uv

# Default target
all: install

# Install venv & dependencies using uv
install:
	$(UV) venv --clear
	$(UV) sync

# Sync virtual environment
sync:
	$(UV) sync

# Run backend development server
dev:
	cd backend && $(UV) run uvicorn main:app --host 127.0.0.1 --port 8000 --reload

run: dev

# Setup pre-commit hooks
precommit:
	$(UV) run pre-commit install

# Lint code with ruff
lint:
	$(UV) run ruff check .

# Format code with ruff
format:
	$(UV) run ruff format .

# Run tests
test:
	$(UV) run python test_google_genai.py

# Clean cache & virtualenv
clean:
	rm -rf .venv __pycache__ backend/__pycache__ .pytest_cache .ruff_cache

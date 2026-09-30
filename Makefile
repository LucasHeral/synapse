.PHONY: install sync dev run test lint format precommit docs-build docs-serve docs-deploy clean

UV = /Users/lucas.heral/.local/bin/uv
VENV_BIN = $(CURDIR)/.venv/bin

# Default target
all: install

# Install venv & dependencies using uv
install:
	$(UV) venv --clear
	$(UV) sync
	$(VENV_BIN)/pre-commit install

# Sync virtual environment
sync:
	$(UV) sync

# Run backend development server
dev:
	cd backend && $(VENV_BIN)/uvicorn main:app --host 127.0.0.1 --port 8000 --reload

run: dev

# Setup pre-commit hooks
precommit:
	$(VENV_BIN)/pre-commit install

# Lint code with ruff
lint:
	$(VENV_BIN)/ruff check .

# Format code with ruff
format:
	$(VENV_BIN)/ruff format .

# Run tests
test:
	$(VENV_BIN)/pytest

# Build MkDocs documentation
docs-build:
	$(VENV_BIN)/mkdocs build

# Serve MkDocs documentation locally
docs-serve:
	$(VENV_BIN)/mkdocs serve

# Deploy MkDocs documentation to GitHub Pages
docs-deploy:
	$(VENV_BIN)/mkdocs gh-deploy --force

# Clean cache & virtualenv
clean:
	rm -rf .venv __pycache__ backend/__pycache__ .pytest_cache .ruff_cache site

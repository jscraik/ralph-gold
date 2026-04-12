# Harness Development Makefile
# Run `make help` to see available commands

.PHONY: help install dev build test lint fmt check clean hooks hooks-pre-commit hooks-pre-push hooks-commit-msg setup

# Default target
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# === Setup ===

install: ## Install dependencies
	uv sync

setup: install hooks ## Full setup: install deps and configure git hooks

hooks: ## Setup git hooks
	prek install

hooks-pre-commit: ## Run local pre-commit gates before creating a commit
	uv run ruff check .
	uv run python -m ralph_gold.cli --help

hooks-pre-push: ## Run local pre-push governance gates before pushing
	uv run pytest -q

hooks-commit-msg: ## Validate commit message policy (use HOOK_COMMIT_MSG or MSG_FILE=/path)
	@tmp_file="$$(mktemp)"; \
	trap 'rm -f "$$tmp_file"' EXIT; \
	if [ -n "$${HOOK_COMMIT_MSG:-}" ]; then \
		printf '%s\n' "$${HOOK_COMMIT_MSG}" > "$$tmp_file"; \
	elif [ -n "$${MSG_FILE:-}" ]; then \
		cat "$${MSG_FILE}" > "$$tmp_file"; \
	else \
		echo "Usage: HOOK_COMMIT_MSG=\"feat: test\" make hooks-commit-msg or make hooks-commit-msg MSG_FILE=/path/to/commit-msg" >&2; \
		exit 2; \
	fi; \
	node scripts/validate-commit-msg.js "$$tmp_file"

# === Development ===

dev: ## Start development server
	uv run ralph --help

build: ## Build for production
	uv build

# === Quality ===

lint: ## Run linter
	uv run ruff check .

fmt: ## Format code
	uv run ruff check . --fix

typecheck: ## Run TypeScript type checking
	uv run python -m ralph_gold.cli --help

test: ## Run tests
	uv run pytest -q

check: lint typecheck test ## Run all checks (lint, typecheck, test)

# === Security ===

audit: ## Run security audit
	npm audit

secrets: ## Scan for secrets with gitleaks
	@gitleaks detect --source . --verbose || (echo "Install gitleaks: brew install gitleaks" && exit 1)

security: audit secrets ## Run all security checks

# === Maintenance ===

clean: ## Clean build artifacts and caches
	rm -rf dist coverage artifacts .test-traces* .traces
	rm -rf node_modules/.cache

reset: clean ## Full reset: clean and reinstall
	uv sync

# === CI ===

ci: check audit ## Run CI checks (check + audit)

# === Diagrams ===

diagrams: ## Generate architecture diagrams
	@echo "Skipping diagrams (no diagram command contract documented for this repo)"

# === Environment ===

env-check: ## Check environment with ralph-gold
	@./scripts/check-environment.sh

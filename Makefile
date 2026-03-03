# Harness Development Makefile
# Run `make help` to see available commands

.PHONY: help install dev build test lint fmt check clean hooks setup

# Default target
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# === Setup ===

install: ## Install dependencies
	npm install

setup: install hooks ## Full setup: install deps and configure git hooks

hooks: ## Setup git hooks
	npm exec simple-git-hooks

# === Development ===

dev: ## Start development server
	npm dev

build: ## Build for production
	npm build

# === Quality ===

lint: ## Run linter
	npm lint

fmt: ## Format code
	npm fmt

typecheck: ## Run TypeScript type checking
	npm typecheck

test: ## Run tests
	npm test

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
	npm install

# === CI ===

ci: check audit ## Run CI checks (check + audit)

# === Diagrams ===

diagrams: ## Generate architecture diagrams
	npm exec diagram all . --output-dir AI/diagrams

# === Environment ===

env-check: ## Check environment with ralph-gold
	@./scripts/check-environment.sh

# Makefile for Binance Trading Bot

.PHONY: help install test lint format clean docker-build docker-run docker-stop setup-db

# Default target
help:
	@echo "Available targets:"
	@echo "  install       - Install dependencies"
	@echo "  test          - Run tests"
	@echo "  lint          - Run linting"
	@echo "  format        - Format code"
	@echo "  clean         - Clean up temporary files"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run with Docker Compose"
	@echo "  docker-stop   - Stop Docker containers"
	@echo "  setup-db      - Setup database"
	@echo "  paper-trade   - Run in paper trading mode"
	@echo "  backtest      - Run backtest"
	@echo "  dashboard     - Start dashboard only"

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	pytest tests/ -v

# Run specific test categories
test-unit:
	pytest tests/ -m unit -v

test-integration:
	pytest tests/ -m integration -v

test-strategies:
	pytest tests/test_strategies.py -v

test-connectors:
	pytest tests/test_connectors.py -v

# Linting
lint:
	black --check bot/ tests/ run.py
	isort --check-only bot/ tests/ run.py
	mypy bot/

# Format code
format:
	black bot/ tests/ run.py
	isort bot/ tests/ run.py

# Clean up
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf logs/
	rm -rf data/

# Docker commands
docker-build:
	docker build -t trading-bot .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f trading_bot

# Database setup
setup-db:
	psql -h localhost -U postgres -f ops/init.sql

# Run modes
paper-trade:
	python run.py --mode paper

live-trade:
	python run.py --mode live

backtest:
	python run.py --mode backtest

backtest-scalper:
	python run.py --mode backtest --strategy scalper --config examples/scalper_config.yaml

backtest-market-maker:
	python run.py --mode backtest --strategy market_maker --config examples/market_maker_config.yaml

backtest-pairs-arbitrage:
	python run.py --mode backtest --strategy pairs_arbitrage --config examples/pairs_arbitrage_config.yaml

# Dashboard
dashboard:
	python -m dashboard.api

# Development
dev-install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

dev-setup: dev-install
	mkdir -p logs data
	cp config.yaml config_local.yaml

# Security
security-check:
	safety check
	bandit -r bot/
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image trading-bot:latest

# Documentation
docs:
	@echo "Documentation is available in README.md and SECURITY.md"

# All-in-one setup
setup: install dev-setup
	@echo "Setup complete! Edit config_local.yaml and run 'make paper-trade' to start."

# Production deployment
deploy: docker-build docker-run
	@echo "Deployment complete! Check http://localhost:8000 for dashboard."

# Quick test
quick-test:
	pytest tests/test_strategies.py::TestScalperStrategy::test_initialization -v

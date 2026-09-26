.PHONY: help install run dev test test-cov lint doctor docker-up docker-down k8s-apply k8s-delete bench

help:
	@echo "ProdLLM Gateway — Makefile Commands"
	@echo "======================================"
	@echo "  make install       Install python project dependencies"
	@echo "  make run           Run Gateway in production mode"
	@echo "  make dev           Run Gateway in auto-reloading dev mode"
	@echo "  make doctor        Run diagnostic health checks"
	@echo "  make test          Run unit and integration test suite"
	@echo "  make test-cov      Run tests with coverage report"
	@echo "  make lint          Run linter (ruff)"
	@echo "  make docker-up     Start full stack with Docker Compose"
	@echo "  make docker-down   Stop Docker Compose stack"
	@echo "  make k8s-apply     Deploy all Kubernetes manifests"
	@echo "  make k8s-delete    Delete Kubernetes namespace"
	@echo "  make bench         Run k6 10k concurrency benchmark"

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

doctor:
	python cli.py doctor

stats:
	python cli.py stats

test:
	pytest tests/

test-cov:
	pytest --cov=app --cov-report=term-missing tests/

lint:
	ruff check .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

k8s-apply:
	kubectl apply -f k8s/

k8s-delete:
	kubectl delete namespace prodllm

bench:
	k6 run benchmarks/k6/load_test_10k.js

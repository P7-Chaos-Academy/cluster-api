.PHONY: help install dev run test lint format clean docker-build docker-run docker-push docker-push-dev

# Docker variables
IMAGE_NAME ?= cgamel/cluster-api
TIMESTAMP := $(shell date +%s)
GIT_HASH := $(shell git rev-parse --short HEAD 2>/dev/null || echo "dev")
DEV_TAG := $(shell git diff --quiet && git diff --cached --quiet && echo $(GIT_HASH) || echo $(GIT_HASH)-$(TIMESTAMP))

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt

dev:  ## Install package in development mode
	pip install -e .

run:  ## Run the application
	python run.py

test:  ## Run tests
	pytest

lint:  ## Run linting checks
	python -m py_compile app/**/*.py

format:  ## Format code with black (if installed)
	black app/ || echo "black not installed, skipping format"

clean:  ## Clean up cache files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true

docker-build:  ## Build Docker image locally
	docker build -t $(IMAGE_NAME):$(GIT_HASH) .

docker-push: docker-build
	docker push $(IMAGE_NAME):$(GIT_HASH)
	@echo "$(IMAGE_NAME):$(GIT_HASH)"

docker-push-dev:
	docker build -t $(IMAGE_NAME):$(DEV_TAG) .
	docker push $(IMAGE_NAME):$(DEV_TAG)
	sed -i "s|image: cgamel/cluster-api:.*|image: $(IMAGE_NAME):$(DEV_TAG)|g" ../gitops/cluster/cluster-deployment.yaml
	kubectl apply -f ../gitops/cluster/cluster-deployment.yaml
	@echo "$(IMAGE_NAME):$(DEV_TAG)"

docker-run:  ## Run Docker container locally
	docker run -p 5000:5000 $(IMAGE_NAME):latest

check:  ## Quick syntax check of all Python files
	@python -m py_compile app/app.py app/controllers/*.py app/services/*.py app/models/*.py app/config/*.py && echo "✓ All Python files have valid syntax"

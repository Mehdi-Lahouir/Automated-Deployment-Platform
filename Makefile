.PHONY: install lint test compose-up compose-down build k8s-validate

install:
	python -m pip install -r requirements-dev.txt

lint:
	ruff check .
	ruff format --check .

test:
	pytest

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down

build:
	docker build -t task-manager:local .

k8s-validate:
	kubectl kustomize k8s


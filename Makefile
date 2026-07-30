.PHONY: install lint test load-test migrate migration compose-up compose-down build backup-image backup-local backup-s3 restore-local demo-traffic alert-trigger alert-recover k8s-validate

install:
	python -m pip install -r requirements-dev.txt

lint:
	ruff check .
	ruff format --check .

test:
	pytest

load-test:
	k6 run scripts/load-test.js

migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(message)"

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down

build:
	docker build -t task-manager:local .

backup-image:
	docker build -t backup-agent:local -f backup/Dockerfile .

backup-local:
	docker compose --profile backup-local run --rm backup-local

backup-s3:
	docker compose --profile backup-s3 run --rm backup-s3

restore-local:
	docker compose --profile backup-local run --rm restore-local

demo-traffic:
	pwsh -File scripts/generate-demo-traffic.ps1

alert-trigger:
	pwsh -File scripts/alert-demo.ps1 -Environment compose -Action trigger

alert-recover:
	pwsh -File scripts/alert-demo.ps1 -Environment compose -Action recover

k8s-validate:
	kubectl kustomize k8s

DC := $(shell command -v docker-compose >/dev/null 2>&1 && echo docker-compose || echo docker compose)

.PHONY: help install run down clean test check

help:
	@echo "Available commands:"
	@echo "  make install   -> Build the API image and start Postgres/Redis"
	@echo "  make run       -> Start the full stack (API + infra) in dev mode"
	@echo "  make down      -> Stop all containers"
	@echo "  make clean     -> Remove containers and orphan volumes"
	@echo "  make test      -> Run tests inside the API container"
	@echo ""
	@echo "Suggested workflow:"
	@echo "  1) make install"
	@echo "  2) make run"
	@echo "  3) make test"

check:
	@command -v docker >/dev/null 2>&1 || { echo "Docker is not installed. Install it: https://docs.docker.com/get-docker/"; exit 1; }
	@$(DC) version >/dev/null 2>&1 || { echo "Docker Compose is not available. Install it: https://docs.docker.com/compose/"; exit 1; }

install: check
	# Build API image (pull newer base if available)
	$(DC) build --pull api
	# Ensure infra images are present
	$(DC) pull postgres redis || true
	# Start infra (detached): Postgres, Redis
	$(DC) up -d postgres redis
	@echo "Install complete. Next: run 'make run'"

run: check
	# Bring up the whole stack (API + infra already running)
	$(DC) up --build

down:
	$(DC) down

clean:
	$(DC) down -v --remove-orphans

test:
	# Run pytest inside a one-off API container (image must include dev deps)
	$(DC) run --rm -e PYTHONPATH=/app api pytest -q

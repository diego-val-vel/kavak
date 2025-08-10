DC := $(shell command -v docker-compose >/dev/null 2>&1 && echo docker-compose || echo docker compose)

.PHONY: help install run down clean test check

help:
	@echo "Available commands:"
	@echo "  make install   -> Build the image and install dependencies inside the container"
	@echo "  make run       -> Start the container in development mode (application not yet running)"
	@echo "  make down      -> Stop the container"
	@echo "  make clean     -> Remove containers and orphan volumes"
	@echo "  make test      -> Run tests inside the container (placeholder)"
	@echo ""
	@echo "Suggested initial workflow:"
	@echo "  1) make install"
	@echo "  2) make run"

check:
	@command -v docker >/dev/null 2>&1 || { echo "Docker is not installed. Install it from https://docs.docker.com/get-docker/"; exit 1; }
	@$(DC) version >/dev/null 2>&1 || { echo "Docker Compose is not available. Install it from https://docs.docker.com/compose/"; exit 1; }

install: check
	$(DC) build --pull api

run: check
	$(DC) up --build

down:
	$(DC) down

clean:
	$(DC) down -v --remove-orphans

test:
	@echo "Tests are not implemented yet. They will be added once the endpoint is available."
	# Example (when tests are available):
	# $(DC) exec api pytest -q

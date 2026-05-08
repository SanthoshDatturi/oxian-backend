# Variables
DOCKER_COMPOSE = docker-compose
BACKEND_SERVICE = backend

.PHONY: help build up down restart logs test lint clean

help:
	@echo "Usage:"
	@echo "  make build        Build or rebuild services"
	@echo "  make up           Create and start containers"
	@echo "  make down         Stop and remove containers, networks, images, and volumes"
	@echo "  make restart      Restart services"
	@echo "  make logs         View output from containers"
	@echo "  make test         Run tests inside the container"
	@echo "  make lint         Run linting (ruff) inside the container"
	@echo "  make clean        Remove temporary files and caches"

build:
	$(DOCKER_COMPOSE) build

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

restart:
	$(DOCKER_COMPOSE) restart

logs:
	$(DOCKER_COMPOSE) logs -f

test:
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) /app/.venv/bin/pytest

lint:
	$(DOCKER_COMPOSE) exec $(BACKEND_SERVICE) /app/.venv/bin/ruff check .

clean:
	uv run python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if p.is_dir()]"
	uv run python -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]')] "
	uv run python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('*.egg-info') if p.is_dir()]"
	uv run python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('.pytest_cache') if p.is_dir()]"
	uv run python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('.ruff_cache') if p.is_dir()]"
	uv run python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('.mypy_cache') if p.is_dir()]"
	uv run python -c "import pathlib, shutil; [shutil.rmtree(pathlib.Path(p)) for p in ['build', 'dist'] if pathlib.Path(p).is_dir()]"

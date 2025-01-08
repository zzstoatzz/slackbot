.PHONY: install clean lint format dev reset-db

install:
	uv sync --frozen

dev:
	PYTHONPATH=src uv run --with-editable '.[dev]' uvicorn slacky.api:app --reload --port 8000 --reload-dir src/slacky

lint:
	uv run --with-editable '.[dev]' ruff check . --fix
	uv run --with-editable '.[dev]' ruff format --check .

clean:
	find . -type d -name "*.venv" -exec rm -rf {} +
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} + 

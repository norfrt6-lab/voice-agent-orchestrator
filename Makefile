.PHONY: install dev test lint typecheck eval run console clean

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/

lint-fix:
	ruff check --fix src/ tests/

typecheck:
	mypy src/

eval:
	python -m src.evaluation.run_eval --transcripts sample_transcripts/ --verbose

run:
	python main.py dev

console:
	python main.py console

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

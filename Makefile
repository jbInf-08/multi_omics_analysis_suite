.PHONY: setup test train-smoke

setup:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"
	cd frontend && npm ci

test:
	pytest tests/unit -v
	cd frontend && npm test -- --passWithNoTests

train-smoke:
	pytest tests/integration/test_omics_analyze_api.py -v --no-cov

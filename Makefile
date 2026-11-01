.PHONY: install test lint format type imports check docker clean

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

type:
	mypy

imports:
	lint-imports

check: lint type imports test

docker:
	docker build -t yt2wa .

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .hypothesis

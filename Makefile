.PHONY: test test-unit test-integration

PYTHON := .venv/bin/python

test-unit:
	$(PYTHON) -m pytest tests/unit/ -v

test-integration:
	RUN_INTEGRATION_TESTS=1 $(PYTHON) -m pytest tests/integration/ -v

test: test-unit test-integration

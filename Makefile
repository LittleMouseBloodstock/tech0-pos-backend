.PHONY: help venv install dev run test clean

PY?=python
PIP?=pip
UVICORN?=uvicorn

help:
	@echo "Targets: venv, install, dev, run, test, clean"

venv:
	$(PY) -m venv .venv

install:
	. .venv/Scripts/activate 2>/dev/null || . .venv/bin/activate; \
	$(PIP) install -r requirements.txt

dev:
	. .venv/Scripts/activate 2>/dev/null || . .venv/bin/activate; \
	$(UVICORN) app.main:app --reload --host 127.0.0.1 --port 8000

run:
	. .venv/Scripts/activate 2>/dev/null || . .venv/bin/activate; \
	$(UVICORN) app.main:app --host 127.0.0.1 --port 8000

test:
	@echo "(no tests in pos-lv2 yet)"

clean:
	rm -rf .venv __pycache__ */__pycache__ *.pyc *.pyo


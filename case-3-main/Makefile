.DEFAULT_GOAL := help

PYTHON ?= python3
FILE ?= fixtures/smoke/01_temp_shares.txt

.PHONY: help setup run dry-run push-debug clean

help:
	@echo "  make setup | make run FILE=fixtures/smoke/01_temp_shares.txt | make dry-run | make push-debug"

setup:
	$(PYTHON) -m pip install -e .
	docker compose build

run:
	$(PYTHON) -m case3.cli run $(FILE) --format both

dry-run:
	$(PYTHON) -m case3.cli run $(FILE) --format both --dry-run

push-debug:
	@stamp=$$(date -u +%Y%m%dT%H%M%SZ); \
	dest=debug-bundle/$$stamp; \
	mkdir -p $$dest/out $$dest/logs; \
	find runs/out -type f \( -name '*.tex' -o -name '*.json' -o -name '*.txt' \) -exec cp -n {} $$dest/out/ \; 2>/dev/null || true; \
	find runs/logs -type f \( -name '*.log' -o -name '*.json' -o -name '*.txt' \) -exec cp -n {} $$dest/logs/ \; 2>/dev/null || true; \
	git checkout -B debug/runs; \
	git add -f $$dest; \
	git commit -m "debug: $$stamp (tex+logs)" || true; \
	git push -u origin debug/runs

clean:
	rm -rf runs/work/* runs/out/* runs/logs/* debug-bundle
	mkdir -p runs/out runs/logs runs/work
	touch runs/out/.gitkeep runs/logs/.gitkeep runs/work/.gitkeep

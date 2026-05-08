.PHONY: help dev sidecar app dmg release test test-sidecar test-engine test-app clean

help:
	@echo "SuperMD for macOS — build targets"
	@echo
	@echo "  make dev           — run the app in dev mode (sidecar via python -m)"
	@echo "  make sidecar       — build dist/macos/supermd-sidecar (PyInstaller)"
	@echo "  make app           — build dist/macos/SuperMD.app"
	@echo "  make dmg           — wrap the .app into a DMG installer"
	@echo "  make release       — sidecar + app + dmg (codesigns if APPLE_TEAM_ID set)"
	@echo
	@echo "  make test          — run all test suites (engine, sidecar, app)"
	@echo "  make test-engine   — pytest (existing CLI/engine tests)"
	@echo "  make test-sidecar  — pytest sidecar/tests/"
	@echo "  make test-app      — swift test (Swift unit tests)"
	@echo
	@echo "  make clean         — remove dist/ and Swift build artifacts"

dev:
	./scripts/macos/dev.sh

sidecar:
	./scripts/macos/build-sidecar.sh

app: sidecar
	./scripts/macos/build-app.sh

dmg: app
	./scripts/macos/package-dmg.sh

release: sidecar app dmg

test: test-engine test-sidecar test-app

test-engine:
	uv run pytest tests/ -v

test-sidecar:
	uv run pytest sidecar/tests/ -v

test-app:
	cd app && swift test

clean:
	rm -rf dist/
	cd app && swift package clean

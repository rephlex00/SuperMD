---
description: Development environment setup and package management for sn2md
---

# sn2md Development Environment

## Package Manager: uv

**Always use `uv` for this project. Never use `pip` directly.**

This project uses [uv](https://docs.astral.sh/uv/) as its package manager. Mixing `pip` and `uv` in the same venv causes stale `.pth` files and broken imports.

## Common Commands

// turbo-all

1. Install/sync dependencies:
```bash
uv sync
```

2. Install with test extras:
```bash
uv sync --extra test
```

3. Run the CLI:
```bash
uv run sn2md-cli <command>
```

4. Run tests:
```bash
uv run python -m pytest tests/ -v
```

5. If you ever see `ModuleNotFoundError: No module named 'sn2md'`:
```bash
rm -rf .venv && uv sync
```

## Rules

- **Never** run `pip install` in this project
- **Always** use `uv sync` to install dependencies
- **Always** use `uv run` to execute commands
- **Always** use `uv pip list` (not `pip list`) to inspect packages

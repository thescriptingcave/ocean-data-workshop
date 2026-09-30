# Contributing to Ocean Data Workshop

Thank you for your interest in contributing! This document explains how to contribute to the project.

## Notebook Format

The notebooks are **generated from Python**, not written directly as `.ipynb` files. This ensures:
- Clean diffs for code reviews
- Reliable rebuilding with `make` or `uv run python scripts/build_notebooks.py`
- Consistent formatting across all notebooks

## How to Contribute

1. **Create an issue** describing the bug or feature first
2. **Fork the repository**
3. **Create a branch** for your changes
4. **Make your changes** to the Python source files in `scripts/`
5. **Run the build** to verify your changes:
   ```bash
   make
   make check  # runs notebooks with network forbidden
   ```
6. **Submit a pull request**

## The Build Process

```bash
# Build all notebooks (without executing)
uv run python scripts/build_notebooks.py

# Build and execute notebooks (saves output)
uv run python scripts/build_notebooks.py --execute

# Build specific notebook
uv run python scripts/build_notebooks.py --execute --only 01_request_three_ways
```

## Testing

```bash
make test       # run all tests
make check      # run notebooks with network forbidden
```

## Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings to functions
- Keep notebooks focused on one concept per file

## Questions?

Open an issue or contact the maintainers.
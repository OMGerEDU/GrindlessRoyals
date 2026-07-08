"""Compile source files without writing .pyc files."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATHS = [ROOT / "main.py", ROOT / "maplebot", ROOT / "tests"]


def iter_python_files():
    for path in PATHS:
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.py"))


def main() -> None:
    for path in iter_python_files():
        source = path.read_text(encoding="utf-8-sig")
        compile(source, str(path), "exec")
        print(f"ok {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

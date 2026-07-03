"""Minimal py:percent -> .ipynb converter (no jupytext dependency).

Usage: python -m sppdptw.nb_convert notebooks/src/01_foo.py notebooks/01_foo.ipynb

Cell markers:
    # %% [markdown]   -> markdown cell (leading '# ' is stripped from each line)
    # %%              -> code cell
Anything before the first marker is ignored (module docstring, imports for linting).
"""

import json
import sys
from pathlib import Path


def parse_cells(text: str) -> list[dict]:
    cells: list[dict] = []
    current: list[str] | None = None
    kind = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# %%"):
            if current is not None:
                cells.append({"kind": kind, "lines": current})
            kind = "markdown" if "[markdown]" in stripped else "code"
            current = []
        elif current is not None:
            current.append(line)

    if current is not None:
        cells.append({"kind": kind, "lines": current})

    out = []
    for cell in cells:
        lines = cell["lines"]
        # trim leading/trailing blank lines
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            continue
        if cell["kind"] == "markdown":
            lines = [
                line[2:] if line.startswith("# ") else ("" if line == "#" else line)
                for line in lines
            ]
            out.append(
                {"cell_type": "markdown", "metadata": {}, "source": _src(lines)}
            )
        else:
            out.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": _src(lines),
                }
            )
    return out


def _src(lines: list[str]) -> list[str]:
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def convert(src: Path, dst: Path) -> None:
    nb = {
        "cells": parse_cells(src.read_text()),
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {dst} ({len(nb['cells'])} cells)")


if __name__ == "__main__":
    convert(Path(sys.argv[1]), Path(sys.argv[2]))

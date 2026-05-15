#!/usr/bin/env python3
from pathlib import Path

p = Path(__file__).parent / "main.py"
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
p.write_text(
    "".join(lines[:809]) + "\nif __name__ == \"__main__\":\n    app()\n",
    encoding="utf-8",
)
print("ok", len(lines), "-> 812")

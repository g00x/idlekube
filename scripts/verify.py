#!/usr/bin/env python3
"""Offline smoke tests (no cluster required)."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"


def _reexec_in_venv() -> None:
    if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])


_reexec_in_venv()
sys.path.insert(0, str(ROOT))

from idlekube.compute import build_output_dict  # noqa: E402
from idlekube.formatters.csv_ import write_csv  # noqa: E402
from idlekube.formatters.html_ import write_html  # noqa: E402
from idlekube.formatters.json_ import write_json  # noqa: E402
from idlekube.models import NamespaceSummary, WorkloadRow  # noqa: E402
from idlekube.recommendations import compute_recommendation  # noqa: E402

OUT = ROOT / "scripts" / "verify-last.txt"
errors: list[str] = []


def check(label: str, fn) -> None:
    try:
        fn()
    except Exception as exc:
        errors.append(f"{label}: {exc}")


def test_imports() -> None:
    import main  # noqa: F401


def test_recommendations() -> None:
    row = WorkloadRow(
        "ns", "dep", "s", "o", "e", 1, 500, 45, 0, 256, 42, 0,
        9.0, 16.0, 10.0, "HIGH", [], False, False,
    )
    rec = compute_recommendation(row)
    if rec is None:
        raise AssertionError("expected recommendation")
    row.recommendation = rec
    data = build_output_dict(
        [row],
        {"ns": NamespaceSummary("ns", 500, 45, 256, 42, 10.0, 1, 0, 0, 1, {"o"})},
        500, 45, 256, 42, 10.0, 25, 4, None,
    )
    if data["workloads"][0]["recommendation"] is None:
        raise AssertionError("missing recommendation in output dict")

    tmpdir = Path(tempfile.mkdtemp())
    write_json(data, str(tmpdir / "t.json"))
    write_csv(data, str(tmpdir / "t.csv"))
    write_html(data, str(tmpdir / "t.html"))
    html = (tmpdir / "t.html").read_text(encoding="utf-8")
    if "Suggested" not in html:
        raise AssertionError("html missing Suggested column")
    header = (tmpdir / "t.csv").read_text(encoding="utf-8").splitlines()[0]
    if "suggested_cpu_request_m" not in header:
        raise AssertionError("csv missing suggestion columns")


check("imports", test_imports)
check("recommendations", test_recommendations)

if errors:
    OUT.write_text("FAIL\n" + "\n".join(errors), encoding="utf-8")
    print("FAIL")
    for err in errors:
        print(err)
    sys.exit(1)

OUT.write_text("OK — all offline checks passed\n", encoding="utf-8")
print("OK — all offline checks passed")

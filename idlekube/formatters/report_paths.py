from datetime import datetime, timezone
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"


def resolve_report_path(
    output_format: str,
    namespace_filter: str | None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    scope = namespace_filter if namespace_filter else "cluster"
    extensions = {"json": "json", "csv": "csv", "html": "html"}
    ext = extensions[output_format]
    return REPORTS_DIR / f"report-{scope}-{ts}.{ext}"

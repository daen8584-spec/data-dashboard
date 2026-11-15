"""climate-pipeline: download, validate, transform and write the dashboard data."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .extract import DownloadError, Snapshot, download, load_snapshot, save_snapshot
from .sources import CO2, SOURCES, TEMPERATURE, SourceFormatError, parse_co2, parse_temperature
from .transform import build_tables
from .validate import validate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="climate-pipeline", description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"), help="where raw downloads are kept")
    parser.add_argument(
        "--out", type=Path, default=Path("site/data"), help="where the dashboard data is written"
    )
    parser.add_argument("--offline", action="store_true", help="use the files already in --raw")
    parser.add_argument("--min-months", type=int, default=600, help="smallest series accepted (for tests)")
    return parser


def run(raw_dir: Path, out_dir: Path, offline: bool, min_months: int) -> int:
    snapshots: dict[str, Snapshot] = {}
    texts: dict[str, str] = {}
    for source in SOURCES:
        if offline:
            data, snapshot = load_snapshot(source, raw_dir)
        else:
            print(f"Downloading {source.title}")
            snapshot = save_snapshot(source, download(source.url), raw_dir)
            data = (raw_dir / snapshot.path).read_bytes()
        snapshots[source.name] = snapshot
        texts[source.name] = data.decode("utf-8")

    co2 = parse_co2(texts[CO2.name])
    temperature = parse_temperature(texts[TEMPERATURE.name])
    report = validate(co2, temperature, min_points=min_months)
    for check in report.checks:
        print(f"  ok       {check}")
    for warning in report.warnings:
        print(f"  warning  {warning}")
    for error in report.errors:
        print(f"  error    {error}", file=sys.stderr)
    if not report.ok:
        print("Validation failed; the dashboard data was not updated.", file=sys.stderr)
        return 1

    tables = build_tables(co2, temperature)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": [{**asdict(snapshots[s.name]), "title": s.title, "page": s.page} for s in SOURCES],
        "quality": {"checks": report.checks, "warnings": report.warnings},
    }
    # Written to a temporary file and renamed, so a reader never sees a half-written file.
    target = out_dir / "dashboard.json"
    temporary = out_dir / "dashboard.json.tmp"
    temporary.write_text(json.dumps({"meta": meta, **tables}, separators=(",", ":")), encoding="utf-8")
    temporary.replace(target)
    for name in ("co2_annual", "temperature_annual"):
        rows = tables[name]
        lines = [",".join(rows[0].keys())] + [
            ",".join("" if v is None else str(v) for v in r.values()) for r in rows
        ]
        (out_dir / f"{name}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {target} ({target.stat().st_size // 1024} KB)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run(args.raw, args.out, args.offline, args.min_months)
    except (DownloadError, SourceFormatError, FileNotFoundError) as error:
        print(f"climate-pipeline: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

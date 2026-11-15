"""Data quality checks. Errors stop the pipeline, so a bad download never replaces a good
dashboard; warnings are reported on the dashboard's data quality section."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import pairwise

from .sources import Co2Month, TemperatureMonth


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _month_index(year: int, month: int) -> int:
    return year * 12 + month - 1


def _check_series(
    report: Report,
    label: str,
    points: list[tuple[int, int, float]],
    low: float,
    high: float,
    first_year: int,
    max_age_months: int,
    today: date,
    min_points: int,
) -> None:
    if len(points) < min_points:
        report.errors.append(f"{label}: only {len(points)} months, expected at least {min_points}")
        return
    seen: set[tuple[int, int]] = set()
    for year, month, value in points:
        if not 1 <= month <= 12:
            report.errors.append(f"{label}: invalid month {year}-{month}")
        if (year, month) in seen:
            report.errors.append(f"{label}: {year}-{month:02d} appears twice")
        seen.add((year, month))
        if not low <= value <= high:
            report.errors.append(f"{label}: {year}-{month:02d} value {value} is outside {low} to {high}")
    if min(y for y, _, _ in points) > first_year:
        report.errors.append(f"{label}: starts after {first_year}, the record is incomplete")

    indexes = sorted(_month_index(y, m) for y, m, _ in points)
    gaps = [(a, b) for a, b in pairwise(indexes) if b - a > 1]
    for a, b in gaps:
        missing = b - a - 1
        start = divmod(a + 1, 12)
        report.warnings.append(f"{label}: {missing} missing month(s) from {start[0]}-{start[1] + 1:02d}")

    latest = indexes[-1]
    age = _month_index(today.year, today.month) - latest
    if age > max_age_months:
        y, m = divmod(latest, 12)
        report.errors.append(
            f"{label}: the latest month is {y}-{m + 1:02d}, more than {max_age_months} months old"
        )
    report.checks.append(
        f"{label}: {len(points)} months, values within {low} to {high}, no duplicates, {len(gaps)} gap(s)"
    )


def validate(
    co2: list[Co2Month],
    temperature: list[TemperatureMonth],
    today: date | None = None,
    min_points: int = 600,
) -> Report:
    """Checks both series. min_points can be lowered for small test files."""
    today = today or date.today()
    report = Report()
    _check_series(
        report, "CO2", [(m.year, m.month, m.ppm) for m in co2], 300, 600, 1959, 6, today, min_points
    )
    _check_series(
        report,
        "Temperature",
        [(m.year, m.month, m.anomaly_c) for m in temperature],
        -2.5,
        3.0,
        1880,
        6,
        today,
        min_points,
    )
    # Monthly CO2 should not jump: the seasonal swing is about 6 ppm a year.
    ordered = sorted(co2, key=lambda m: (m.year, m.month))
    for previous, current in pairwise(ordered):
        if (
            abs(current.ppm - previous.ppm) > 8
            and _month_index(current.year, current.month) - _month_index(previous.year, previous.month) == 1
        ):
            report.errors.append(
                f"CO2: jump of {current.ppm - previous.ppm:+.2f} ppm from "
                f"{previous.year}-{previous.month:02d} to {current.year}-{current.month:02d}"
            )
    return report

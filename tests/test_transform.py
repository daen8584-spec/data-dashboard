from __future__ import annotations

import pytest

from pipeline.sources import parse_co2, parse_temperature
from pipeline.transform import build_tables

from .conftest import LAST_YEAR, co2_file, co2_value, temperature_file, temperature_value


@pytest.fixture(scope="module")
def tables() -> dict:  # type: ignore[type-arg]
    return build_tables(parse_co2(co2_file()), parse_temperature(temperature_file()))


def test_annual_figures_use_complete_years_only(tables: dict) -> None:  # type: ignore[type-arg]
    co2_years = [row["year"] for row in tables["co2_annual"]]
    # 1958 starts in March and the last year stops in September.
    assert co2_years[0] == 1959 and co2_years[-1] == LAST_YEAR - 1
    temperature_years = [row["year"] for row in tables["temperature_annual"]]
    assert temperature_years[0] == 1880 and temperature_years[-1] == LAST_YEAR - 1


def test_annual_mean_and_growth(tables: dict) -> None:  # type: ignore[type-arg]
    by_year = {row["year"]: row for row in tables["co2_annual"]}
    expected_2000 = sum(co2_value(2000, m)[0] for m in range(1, 13)) / 12
    expected_1999 = sum(co2_value(1999, m)[0] for m in range(1, 13)) / 12
    assert by_year[2000]["ppm"] == pytest.approx(expected_2000, abs=0.001)
    assert by_year[2000]["growth_ppm"] == pytest.approx(expected_2000 - expected_1999, abs=0.002)
    assert by_year[1959]["growth_ppm"] is None


def test_rolling_mean_needs_ten_years(tables: dict) -> None:  # type: ignore[type-arg]
    rows = tables["temperature_annual"]
    assert all(row["rolling_10y"] is None for row in rows[:9])
    annual = {row["year"]: sum(temperature_value(row["year"], m) for m in range(1, 13)) / 12 for row in rows}
    expected = sum(annual[y] for y in range(1880, 1890)) / 10
    assert rows[9]["rolling_10y"] == pytest.approx(expected, abs=0.001)


def test_seasonal_cycle_peaks_in_spring(tables: dict) -> None:  # type: ignore[type-arg]
    offsets = {row["month"]: row["offset_ppm"] for row in tables["co2_seasonal"]}
    assert len(offsets) == 12
    # The synthetic cycle is 3 sin(2 pi (month - 2) / 12): highest in May, lowest in November.
    assert max(offsets, key=offsets.__getitem__) == 5
    assert min(offsets, key=offsets.__getitem__) == 11
    assert offsets[5] == pytest.approx(3.0, abs=0.01)


def test_decades_and_summary(tables: dict) -> None:  # type: ignore[type-arg]
    decades = {row["decade"]: row for row in tables["decades"]}
    assert 1880 in decades and LAST_YEAR // 10 * 10 not in decades  # incomplete decade left out
    assert decades[1880]["growth_ppm_per_year"] is None  # before CO2 measurements
    assert decades[2010]["growth_ppm_per_year"] > decades[1960]["growth_ppm_per_year"]

    summary = tables["summary"]
    assert summary["latest_co2"] == {"year": LAST_YEAR, "month": 9, "ppm": co2_value(LAST_YEAR, 9)[0]}
    assert summary["co2_change"]["from_year"] == 1959
    assert summary["warmest_year"]["year"] >= 2015
    assert summary["correlation"]["r"] > 0.9
    assert summary["correlation"]["years"] == LAST_YEAR - 1959
    # Published figures are rounded, not long binary fractions.
    assert summary["co2_change"]["from_ppm"] == round(summary["co2_change"]["from_ppm"], 3)

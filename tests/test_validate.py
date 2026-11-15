from __future__ import annotations

from datetime import date

from pipeline.sources import Co2Month, TemperatureMonth, parse_co2, parse_temperature
from pipeline.validate import validate

from .conftest import co2_file, temperature_file

TODAY = date(2026, 11, 15)


def series() -> tuple[list[Co2Month], list[TemperatureMonth]]:
    return parse_co2(co2_file()), parse_temperature(temperature_file())


def test_good_data_passes() -> None:
    report = validate(*series(), today=TODAY)
    assert report.ok, report.errors
    assert report.warnings == []
    assert len(report.checks) == 2


def test_out_of_range_and_duplicate_values_fail() -> None:
    co2, temperature = series()
    co2.append(Co2Month(1990, 5, 9999.0, None))
    temperature.append(TemperatureMonth(1880, 1, -0.1))
    report = validate(co2, temperature, today=TODAY)
    assert not report.ok
    assert any("1990-05 value 9999.0 is outside 300 to 600" in e for e in report.errors)
    assert any("Temperature: 1880-01 appears twice" in e for e in report.errors)


def test_stale_data_fails() -> None:
    report = validate(*series(), today=date(2027, 6, 1))
    assert any("the latest month is 2026-09, more than 6 months old" in e for e in report.errors)


def test_a_truncated_download_fails() -> None:
    co2, temperature = series()
    report = validate(co2[-100:], temperature, today=TODAY)
    assert any("CO2: only 100 months" in e for e in report.errors)


def test_a_sudden_jump_fails() -> None:
    co2, temperature = series()
    index = next(i for i, m in enumerate(co2) if (m.year, m.month) == (2000, 6))
    co2[index] = Co2Month(2000, 6, co2[index].ppm + 15, co2[index].deseasonalized_ppm)
    report = validate(co2, temperature, today=TODAY)
    assert any("CO2: jump of" in e and "2000-05 to 2000-06" in e for e in report.errors)


def test_gaps_are_warnings() -> None:
    co2 = parse_co2(co2_file(skip=frozenset({(1964, 2), (1964, 3), (1964, 4)})))
    report = validate(co2, parse_temperature(temperature_file()), today=TODAY)
    assert report.ok
    assert report.warnings == ["CO2: 3 missing month(s) from 1964-02"]

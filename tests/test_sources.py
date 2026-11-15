from __future__ import annotations

import pytest

from pipeline.sources import Co2Month, SourceFormatError, TemperatureMonth, parse_co2, parse_temperature

from .conftest import CO2_EXCERPT, TEMPERATURE_EXCERPT


def test_co2_skips_comments_and_missing_values() -> None:
    assert parse_co2(CO2_EXCERPT) == [
        Co2Month(1958, 3, 315.71, 314.44),
        Co2Month(1958, 4, 317.45, 315.16),
        # May has no monthly average (-99.99), so it is left out.
        Co2Month(1958, 6, 317.24, None),
    ]


def test_co2_finds_columns_by_name() -> None:
    text = "month,year,trend,average\n3,1958,314.44,315.71\n"
    assert parse_co2(text) == [Co2Month(1958, 3, 315.71, 314.44)]


def test_co2_reports_a_changed_format() -> None:
    with pytest.raises(SourceFormatError, match="missing column 'average'"):
        parse_co2("year,month,value\n1958,3,315.71\n")
    with pytest.raises(SourceFormatError, match="no data"):
        parse_co2("# only comments\n")


def test_temperature_reads_months_and_skips_unpublished_ones() -> None:
    months = parse_temperature(TEMPERATURE_EXCERPT)
    assert months[:2] == [TemperatureMonth(1880, 1, -0.18), TemperatureMonth(1880, 2, -0.24)]
    assert len(months) == 12 + 12 + 3
    assert months[-1] == TemperatureMonth(2026, 3, 1.25)


def test_temperature_converts_hundredths_of_a_degree() -> None:
    text = (
        "Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec\n"
        "1880,-18,-24,-9,-16,-10,-21,-18,-10,-15,-23,-22,-18\n"
    )
    assert parse_temperature(text)[0] == TemperatureMonth(1880, 1, -0.18)


def test_temperature_reports_a_changed_format() -> None:
    with pytest.raises(SourceFormatError, match="header row"):
        parse_temperature("Land-Ocean: Global Means\nYYYY,Jan\n")
    with pytest.raises(SourceFormatError, match="not a number"):
        parse_temperature("Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec\n1880,cold,,,,,,,,,,,\n")

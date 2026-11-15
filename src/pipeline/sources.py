"""The two public sources and how to read their own file formats.

Both are U.S. government works in the public domain:

- NOAA Global Monitoring Laboratory, monthly mean CO2 at Mauna Loa Observatory
  (https://gml.noaa.gov/ccgg/trends/data.html), measured since 1958 and started by
  C. David Keeling of Scripps Institution of Oceanography.
- NASA GISS Surface Temperature Analysis, GISTEMP v4 global land-ocean temperature
  index (https://data.giss.nasa.gov/gistemp/): monthly anomalies in degrees Celsius
  relative to the 1951-1980 average.

The parsers find columns by name rather than position and treat the sources' own
missing-value markers as missing, so small format changes either keep working or fail
with a clear message instead of producing wrong numbers.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass


class SourceFormatError(ValueError):
    """A downloaded file does not have the expected format."""


@dataclass(frozen=True)
class Source:
    name: str
    title: str
    url: str
    page: str


CO2 = Source(
    name="co2",
    title="NOAA GML, monthly mean CO2 at Mauna Loa",
    url="https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv",
    page="https://gml.noaa.gov/ccgg/trends/data.html",
)
TEMPERATURE = Source(
    name="temperature",
    title="NASA GISS, GISTEMP v4 global land-ocean temperature index",
    url="https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv",
    page="https://data.giss.nasa.gov/gistemp/",
)
SOURCES = (CO2, TEMPERATURE)


@dataclass(frozen=True)
class Co2Month:
    year: int
    month: int
    ppm: float
    deseasonalized_ppm: float | None


@dataclass(frozen=True)
class TemperatureMonth:
    year: int
    month: int
    anomaly_c: float


def _number(text: str) -> float | None:
    value = text.strip()
    if not value or value.startswith("*"):
        return None
    try:
        return float(value)
    except ValueError as error:
        raise SourceFormatError(f"not a number: {text!r}") from error


def _column(header: list[str], *names: str) -> int:
    normalized = [h.strip().lower() for h in header]
    for name in names:
        if name in normalized:
            return normalized.index(name)
    raise SourceFormatError(f"missing column {names[0]!r}; found {', '.join(header)}")


def parse_co2(text: str) -> list[Co2Month]:
    """Reads NOAA's co2_mm_mlo.csv: comment lines start with #, then a header row.

    NOAA marks missing values with negative numbers such as -9.99 or -99.99.
    """
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise SourceFormatError("the CO2 file has no data")
    rows = list(csv.reader(io.StringIO("\n".join(lines))))
    header, body = rows[0], rows[1:]
    year = _column(header, "year")
    month = _column(header, "month")
    average = _column(header, "average", "monthly average")
    deseasonalized = _column(header, "deseasonalized", "de-seasonalized", "trend")

    months: list[Co2Month] = []
    for row in body:
        ppm = _number(row[average])
        if ppm is None or ppm < 0:
            continue
        trend = _number(row[deseasonalized])
        months.append(
            Co2Month(int(row[year]), int(row[month]), ppm, trend if trend is not None and trend > 0 else None)
        )
    return months


MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def parse_temperature(text: str) -> list[TemperatureMonth]:
    """Reads GISTEMP's GLB.Ts+dSST.csv: a title line, then a header starting with "Year".

    Months not yet published are "***". Values are degrees Celsius; older files used
    hundredths of a degree, which is detected and converted.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().lower().startswith("year,")), None)
    if start is None:
        raise SourceFormatError("the temperature file has no header row starting with 'Year'")
    rows = list(csv.reader(io.StringIO("\n".join(lines[start:]))))
    header, body = rows[0], rows[1:]
    year = _column(header, "year")
    columns = [_column(header, m) for m in MONTHS]

    months: list[TemperatureMonth] = []
    for row in body:
        if not row or not row[year].strip().isdigit():
            continue
        for number, column in enumerate(columns, start=1):
            value = _number(row[column]) if column < len(row) else None
            if value is not None:
                months.append(TemperatureMonth(int(row[year]), number, value))
    if months and max(abs(m.anomaly_c) for m in months) > 10:
        months = [TemperatureMonth(m.year, m.month, m.anomaly_c / 100) for m in months]
    return months

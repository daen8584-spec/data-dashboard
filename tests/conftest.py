"""Test data in the sources' own file formats.

The excerpts below copy each format's layout (comment block, header, missing-value
markers). The full series are synthetic and deterministic: a quadratic CO2 trend with a
seasonal cycle, and a warming trend, so expected results can be computed exactly. They
are not real measurements.
"""

from __future__ import annotations

import math

CO2_EXCERPT = """\
# --------------------------------------------------------------------
# USE OF NOAA GML DATA
#
# These data are made freely available to the public.
# --------------------------------------------------------------------
#
# CO2 expressed as a mole fraction in dry air, micromol/mol, abbreviated as ppm
#
year,month,decimal date,average,deseasonalized,ndays,sdev,unc
1958,3,1958.2027,315.71,314.44,-1,-9.99,-0.99
1958,4,1958.2877,317.45,315.16,-1,-9.99,-0.99
1958,5,1958.3699,-99.99,314.69,-1,-9.99,-0.99
1958,6,1958.4548,317.24,-9.99,-1,-9.99,-0.99
"""

TEMPERATURE_EXCERPT = """\
Land-Ocean: Global Means
Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec,J-D,D-N,DJF,MAM,JJA,SON
1880,-.18,-.24,-.09,-.16,-.10,-.21,-.18,-.10,-.15,-.23,-.22,-.18,-.17,***,***,-.12,-.17,-.20
1881,-.19,-.14,.04,.05,.07,-.18,.01,-.03,-.15,-.22,-.18,-.07,-.08,-.09,-.17,.05,-.07,-.18
2026,1.28,1.32,1.25,***,***,***,***,***,***,***,***,***,***,***,1.27,***,***,***
"""

LAST_YEAR = 2026
LAST_MONTH = 9


def co2_value(year: int, month: int) -> tuple[float, float]:
    """(monthly average, deseasonalized) for a synthetic month."""
    t = year - 1958 + (month - 1) / 12
    trend = 315.0 + 0.8 * t + 0.012 * t * t
    return round(trend + 3.0 * math.sin(2 * math.pi * (month - 2) / 12), 2), round(trend, 2)


def temperature_value(year: int, month: int) -> float:
    t = year - 1880
    return round(-0.3 + 0.00007 * t * t + 0.05 * math.sin(year * 1.3 + month), 2)


def co2_file(skip: frozenset[tuple[int, int]] = frozenset()) -> str:
    lines = ["# synthetic test data", "year,month,decimal date,average,deseasonalized,ndays,sdev,unc"]
    for year in range(1958, LAST_YEAR + 1):
        for month in range(1, 13):
            if (year == 1958 and month < 3) or (year == LAST_YEAR and month > LAST_MONTH):
                continue
            if (year, month) in skip:
                continue
            average, trend = co2_value(year, month)
            lines.append(f"{year},{month},{year + (month - 0.5) / 12:.4f},{average},{trend},-1,-9.99,-0.99")
    return "\n".join(lines) + "\n"


def temperature_file() -> str:
    lines = ["Land-Ocean: Global Means", "Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec,J-D"]
    for year in range(1880, LAST_YEAR + 1):
        cells = []
        for month in range(1, 13):
            if year == LAST_YEAR and month > LAST_MONTH:
                cells.append("***")
            else:
                cells.append(f"{temperature_value(year, month):.2f}")
        lines.append(f"{year}," + ",".join(cells) + ",***")
    return "\n".join(lines) + "\n"

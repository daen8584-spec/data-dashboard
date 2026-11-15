"""Turns the monthly series into the tables the dashboard shows, with SQL in DuckDB."""

from __future__ import annotations

from typing import Any

import duckdb

from .sources import Co2Month, TemperatureMonth

Table = list[dict[str, Any]]


def _rows(connection: duckdb.DuckDBPyConnection, sql: str) -> Table:
    cursor = connection.execute(sql)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _round(table: Table, digits: int = 3) -> Table:
    return [{k: round(v, digits) if isinstance(v, float) else v for k, v in row.items()} for row in table]


def build_tables(co2: list[Co2Month], temperature: list[TemperatureMonth]) -> dict[str, Any]:
    connection = duckdb.connect()
    connection.execute("create table co2 (year int, month int, ppm double, deseasonalized double)")
    connection.executemany(
        "insert into co2 values (?, ?, ?, ?)", [(m.year, m.month, m.ppm, m.deseasonalized_ppm) for m in co2]
    )
    connection.execute("create table temperature (year int, month int, anomaly double)")
    connection.executemany(
        "insert into temperature values (?, ?, ?)", [(m.year, m.month, m.anomaly_c) for m in temperature]
    )

    # Only complete years count for annual figures, so a partial current year does not
    # look like a sudden change.
    connection.execute(
        """
        create view co2_annual as
        select year, avg(ppm) as ppm
        from co2 group by year having count(*) = 12
        """
    )
    connection.execute(
        """
        create view temperature_annual as
        select year, avg(anomaly) as anomaly
        from temperature group by year having count(*) = 12
        """
    )

    tables: dict[str, Any] = {
        "co2_monthly": _rows(
            connection,
            """
            select year, month, ppm, deseasonalized from co2 order by year, month
            """,
        ),
        "co2_annual": _rows(
            connection,
            """
            select year, ppm, ppm - lag(ppm) over (order by year) as growth_ppm
            from co2_annual order by year
            """,
        ),
        # The yearly cycle: how far each month sits from the deseasonalized trend,
        # averaged over the last ten complete years.
        "co2_seasonal": _rows(
            connection,
            """
            select month, avg(ppm - deseasonalized) as offset_ppm
            from co2
            where deseasonalized is not null
              and year > (select max(year) from co2_annual) - 10
              and year <= (select max(year) from co2_annual)
            group by month order by month
            """,
        ),
        "temperature_annual": _rows(
            connection,
            """
            select year, anomaly,
                   case when count(*) over w = 10 then avg(anomaly) over w end as rolling_10y
            from temperature_annual
            window w as (order by year rows between 9 preceding and current row)
            order by year
            """,
        ),
        "decades": _rows(
            connection,
            """
            select t.decade, t.anomaly, c.growth_ppm_per_year
            from (
                select year // 10 * 10 as decade, avg(anomaly) as anomaly, count(*) as years
                from temperature_annual group by 1
            ) t
            left join (
                select year // 10 * 10 as decade,
                       (max(ppm) - min(ppm)) / (max(year) - min(year)) as growth_ppm_per_year
                from co2_annual group by 1 having count(*) >= 2
            ) c using (decade)
            where t.years = 10
            order by t.decade
            """,
        ),
    }

    # Pearson correlation of annual CO2 and temperature, over the years both cover.
    correlation = connection.execute(
        "select corr(c.ppm, t.anomaly), count(*) from co2_annual c join temperature_annual t using (year)"
    ).fetchone()
    latest_co2 = connection.execute(
        "select year, month, ppm from co2 order by year desc, month desc limit 1"
    ).fetchone()
    first_co2 = connection.execute("select year, ppm from co2_annual order by year limit 1").fetchone()
    last_co2 = connection.execute("select year, ppm from co2_annual order by year desc limit 1").fetchone()
    warmest = connection.execute(
        "select year, anomaly from temperature_annual order by anomaly desc limit 1"
    ).fetchone()
    recent_warmest = connection.execute(
        """
        select count(*) from (select year from temperature_annual order by anomaly desc limit 10)
        where year > (select max(year) from temperature_annual) - 10
        """
    ).fetchone()

    tables["summary"] = {
        "latest_co2": {"year": latest_co2[0], "month": latest_co2[1], "ppm": latest_co2[2]}
        if latest_co2
        else None,
        "co2_change": (
            {
                "from_year": first_co2[0],
                "to_year": last_co2[0],
                "from_ppm": first_co2[1],
                "to_ppm": last_co2[1],
            }
            if first_co2 and last_co2
            else None
        ),
        "warmest_year": {"year": warmest[0], "anomaly": warmest[1]} if warmest else None,
        "warmest_ten_in_last_ten": recent_warmest[0] if recent_warmest else None,
        "correlation": (
            {"r": correlation[0], "years": correlation[1]}
            if correlation and correlation[0] is not None
            else None
        ),
    }
    for name in ("co2_monthly", "co2_annual", "co2_seasonal", "temperature_annual", "decades"):
        tables[name] = _round(tables[name])
    return tables

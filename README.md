# CO₂ and global temperature dashboard

[![CI](https://github.com/daen8584-spec/data-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/daen8584-spec/data-dashboard/actions/workflows/ci.yml)
[![Update dashboard](https://github.com/daen8584-spec/data-dashboard/actions/workflows/pages.yml/badge.svg)](https://github.com/daen8584-spec/data-dashboard/actions/workflows/pages.yml)

A data pipeline that downloads atmospheric CO₂ and global temperature data from NOAA and NASA every week, checks it, turns it into summary tables with SQL, and publishes an interactive dashboard.

**See it:** [daen8584-spec.github.io/data-dashboard](https://daen8584-spec.github.io/data-dashboard/)

## The data

| Series | Source | Coverage |
| --- | --- | --- |
| Monthly mean CO₂ at Mauna Loa Observatory, Hawaii | [NOAA Global Monitoring Laboratory](https://gml.noaa.gov/ccgg/trends/data.html) | 1958 to now |
| Global land-ocean temperature, difference from the 1951 to 1980 average | [NASA GISS, GISTEMP v4](https://data.giss.nasa.gov/gistemp/) | 1880 to now |

Both are U.S. government works in the public domain. The Mauna Loa record was started by C. David Keeling of Scripps Institution of Oceanography.

## What the dashboard shows

- Headline figures: the latest CO₂ reading, how much it has risen, the warmest year, and how many of the ten warmest years were recent
- The Keeling curve: monthly CO₂ with its yearly cycle and the trend underneath
- How much CO₂ rose each year, and the average yearly cycle
- Global temperature each year with a ten-year average
- CO₂ against temperature year by year, with the correlation
- A table by decade, CSV and JSON downloads, and the checks run on the latest update

The charts are plain SVG with no libraries, show values on hover, and each has a text description for screen readers.

## How the pipeline works

```
download ──> check ──> transform (DuckDB SQL) ──> dashboard.json + CSV ──> GitHub Pages
 NOAA, NASA   ranges, duplicates,    annual means, growth,
 retries,     gaps, freshness,       seasonal cycle, rolling
 checksums    sudden jumps           mean, decades, correlation
```

1. **Download.** Both files are fetched with retries and backoff on network and server errors, but not on errors like 404 that won't fix themselves. Each raw file is kept with its SHA-256 checksum and download time, which the dashboard shows, so every number can be traced to the exact file it came from.
2. **Parse.** Each source has its own format: NOAA's starts with a block of `#` comments and marks missing values with negative numbers, and NASA's has a title line and marks unpublished months with `***`. Columns are found by name, so a reordered file still works, and a file with a changed format fails with a clear message instead of producing wrong numbers.
3. **Check.** Values must be in plausible ranges, months must be valid and appear once, the record must start where it should and be no more than six months old, and monthly CO₂ must not jump by more than its seasonal swing allows. A failed check stops the pipeline **before** anything is published, so a bad download never replaces a good dashboard. Gaps are reported as warnings.
4. **Transform.** SQL in DuckDB builds the tables. Annual figures use complete years only, so a partial current year doesn't look like a sudden change. The ten-year average starts once there are ten years of data.
5. **Publish.** The output is written to a temporary file and renamed, so a reader never sees half of it. GitHub Actions publishes the site.

## Updates

[`pages.yml`](.github/workflows/pages.yml) runs every Monday, on every push to `main`, and on demand from the Actions tab. If NOAA or NASA is down or sends something unexpected, the run fails, the previous dashboard stays up, and GitHub emails the repository owner. CI also runs the pipeline against the live sources on every pull request.

GitHub pauses scheduled workflows in repositories with no activity for 60 days. Re-enable it from the Actions tab if that happens.

## Running it

Requires Python 3.11 or later.

```bash
pip install -e ".[dev]"
climate-pipeline                         # downloads into data/raw, writes site/data
python -m http.server --directory site   # then open http://localhost:8000
```

`climate-pipeline --offline` rebuilds from the files already in `data/raw`, after checking them against their saved checksums.

## Tests

```bash
pytest     # 22 tests
ruff check .
mypy       # strict
```

The parsers are tested on excerpts in each source's real format, including comment blocks, missing-value markers and unpublished months. The checks, transformations and the full pipeline are tested on synthetic, deterministic series in the same formats, so the expected results are known exactly: annual means, growth, the rolling average, the seasonal peak, and the correlation. Other tests cover a truncated download (which must leave the previous dashboard in place), stale data, duplicates, sudden jumps, tampered raw files, and download retries.

## License

MIT for the code. The data belongs to the public domain; please credit NOAA GML and NASA GISS when you use it.

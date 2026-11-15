from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pipeline import cli
from pipeline.extract import DownloadError, load_snapshot, save_snapshot
from pipeline.sources import CO2, TEMPERATURE

from .conftest import co2_file, temperature_file


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    directory = tmp_path / "raw"
    save_snapshot(CO2, co2_file().encode(), directory)
    save_snapshot(TEMPERATURE, temperature_file().encode(), directory)
    return directory


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    real_validate = cli.validate

    def validate(co2, temperature, today=None, min_points=600):  # type: ignore[no-untyped-def]
        return real_validate(co2, temperature, today=date(2026, 11, 15), min_points=min_points)

    monkeypatch.setattr(cli, "validate", validate)


def test_offline_run_writes_the_dashboard_data(
    raw: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "site"
    assert cli.main(["--raw", str(raw), "--out", str(out), "--offline"]) == 0
    data = json.loads((out / "dashboard.json").read_text())
    assert set(data) >= {
        "meta",
        "summary",
        "co2_monthly",
        "co2_annual",
        "co2_seasonal",
        "temperature_annual",
        "decades",
    }
    assert [s["source"] for s in data["meta"]["sources"]] == ["co2", "temperature"]
    assert all(len(s["sha256"]) == 64 for s in data["meta"]["sources"])
    assert (out / "co2_annual.csv").read_text().startswith("year,ppm,growth_ppm\n")
    assert "ok       CO2:" in capsys.readouterr().out


def test_bad_data_leaves_the_previous_dashboard_in_place(raw: Path, tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert cli.main(["--raw", str(raw), "--out", str(out), "--offline"]) == 0
    before = (out / "dashboard.json").read_bytes()

    truncated = "\n".join(co2_file().splitlines()[:50]) + "\n"
    save_snapshot(CO2, truncated.encode(), raw)
    assert cli.main(["--raw", str(raw), "--out", str(out), "--offline"]) == 1
    assert (out / "dashboard.json").read_bytes() == before


def test_a_changed_raw_file_is_detected(raw: Path) -> None:
    (raw / "co2.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(DownloadError, match="does not match its checksum"):
        load_snapshot(CO2, raw)


def test_download_retries_server_errors_then_gives_up(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    from pipeline import extract

    calls: list[str] = []

    def failing(request, timeout):  # type: ignore[no-untyped-def]
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 503, "Service Unavailable", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(extract.urllib.request, "urlopen", failing)
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)
    with pytest.raises(DownloadError, match="failed after 3 attempts"):
        extract.download("https://example.test/data.csv", attempts=3)
    assert len(calls) == 3


def test_download_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    from pipeline import extract

    calls: list[str] = []

    def missing(request, timeout):  # type: ignore[no-untyped-def]
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(extract.urllib.request, "urlopen", missing)
    with pytest.raises(DownloadError, match="HTTP 404"):
        extract.download("https://example.test/moved.csv")
    assert len(calls) == 1

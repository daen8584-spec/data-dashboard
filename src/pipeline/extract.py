"""Downloads the sources and keeps each raw file with its checksum, so every number on the
dashboard can be traced to the exact file it came from."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .sources import Source

USER_AGENT = "climate-dashboard-pipeline/0.1 (+https://github.com/daen8584-spec/data-dashboard)"


class DownloadError(RuntimeError):
    """A source could not be downloaded after retrying."""


@dataclass(frozen=True)
class Snapshot:
    source: str
    url: str
    fetched_at: str
    sha256: str
    bytes: int
    path: str


def download(url: str, attempts: int = 4, timeout: float = 30) -> bytes:
    """Fetches a URL, retrying with backoff on network errors and server errors (5xx)."""
    last: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data: bytes = response.read()
                return data
        except urllib.error.HTTPError as error:
            if error.code < 500:
                raise DownloadError(f"{url}: HTTP {error.code}") from error
            last = error
        except (urllib.error.URLError, TimeoutError) as error:
            last = error
        time.sleep(2**attempt)
    raise DownloadError(f"{url}: failed after {attempts} attempts: {last}")


def save_snapshot(source: Source, data: bytes, raw_dir: Path) -> Snapshot:
    raw_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    path = raw_dir / f"{source.name}.csv"
    path.write_bytes(data)
    snapshot = Snapshot(
        source=source.name,
        url=source.url,
        fetched_at=now.isoformat(timespec="seconds"),
        sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data),
        path=path.name,
    )
    (raw_dir / f"{source.name}.json").write_text(json.dumps(asdict(snapshot), indent=2), encoding="utf-8")
    return snapshot


def load_snapshot(source: Source, raw_dir: Path) -> tuple[bytes, Snapshot]:
    """Reads a previously saved file and checks it still matches its recorded checksum."""
    data = (raw_dir / f"{source.name}.csv").read_bytes()
    meta = json.loads((raw_dir / f"{source.name}.json").read_text(encoding="utf-8"))
    snapshot = Snapshot(**meta)
    if hashlib.sha256(data).hexdigest() != snapshot.sha256:
        raise DownloadError(f"{source.name}: the saved file does not match its checksum")
    return data, snapshot

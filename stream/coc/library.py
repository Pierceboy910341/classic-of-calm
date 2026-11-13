"""Read-only view of the music library on disk.

Layout (under $COC_HOME/library):
  batches/<batch_id>/manifest.json      written last by sync -> batch is complete
  batches/<batch_id>/tracks/*.m4a
  batches/<batch_id>/stream_loop.mp4    optional
  batches/<batch_id>/youtube.txt        optional, for reference
  current_loop.mp4 -> batches/<id>/stream_loop.mp4   (symlink, managed by sync)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .common import Config, read_json


@dataclass(frozen=True)
class Track:
    path: Path
    title: str
    duration: float
    batch_id: str
    series: str
    imported_ts: float


@dataclass
class Batch:
    batch_id: str
    path: Path
    manifest: dict

    @property
    def imported_ts(self) -> float:
        return float(self.manifest.get("imported_ts", 0))

    @property
    def series(self) -> str:
        return self.manifest.get("series", "unknown")

    @property
    def loop_path(self) -> Path | None:
        name = self.manifest.get("loop")
        if not name:
            return None
        p = self.path / name
        return p if p.exists() else None


def list_batches(cfg: Config) -> list[Batch]:
    """Complete batches, oldest first."""
    out = []
    if not cfg.batches.is_dir():
        return out
    for d in cfg.batches.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        m = read_json(d / "manifest.json")
        if not isinstance(m, dict):
            continue
        out.append(Batch(d.name, d, m))
    out.sort(key=lambda b: (b.imported_ts, b.batch_id))
    return out


def series_matches(cfg: Config, series: str) -> bool:
    if cfg.series in ("", "all"):
        return True
    return series in (cfg.series, "unknown")


def list_tracks(cfg: Config, batches: list[Batch] | None = None) -> list[Track]:
    if batches is None:
        batches = list_batches(cfg)
    tracks = []
    for b in batches:
        if not series_matches(cfg, b.series):
            continue
        for t in b.manifest.get("tracks", []):
            p = b.path / t.get("file", "")
            if not p.is_file():
                continue
            tracks.append(Track(p, t.get("title") or p.stem, float(t.get("duration") or 0),
                                b.batch_id, b.series, b.imported_ts))
    return tracks


def library_signature(cfg: Config) -> tuple:
    """Cheap change detector: names + mtimes of batch dirs."""
    try:
        entries = sorted((d.name, d.stat().st_mtime_ns) for d in cfg.batches.iterdir())
    except OSError:
        entries = []
    return tuple(entries)


def resolve_loop(cfg: Config) -> Path | None:
    """Which loop video the streamer should use right now."""
    if cfg.loop_file_override:
        p = Path(cfg.loop_file_override)
        if p.is_file():
            return p.resolve()
    if cfg.current_loop.exists():
        return cfg.current_loop.resolve()
    if cfg.placeholder_loop.is_file():
        return cfg.placeholder_loop.resolve()
    return None


def dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            pass
    return total

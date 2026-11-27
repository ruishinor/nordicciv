"""The contract every data source implements (pattern from usaciv, MIT).

A source declares its downloads (`files()`), and turns the cached raw files into a
tidy JSON-able dict (`process()`), saved as data/interim/<id>.json. Sources know
nothing about hexes, cities or the UI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import fetch
from .paths import RAW


@dataclass(frozen=True)
class SourceInfo:
    id: str
    title: str
    publisher: str
    homepage: str
    license: str
    description: str
    used_for: list[str] = field(default_factory=list)
    country: str = "ALL"  # NO | SE | DK | ALL

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class File:
    rel_path: str
    url: str
    method: str = "GET"
    body: str | None = None
    headers: dict | None = None


class Source:
    info: SourceInfo

    @property
    def id(self) -> str:
        return self.info.id

    @property
    def raw_dir(self) -> Path:
        return RAW / self.id

    def files(self) -> list[File]:
        return []

    def fetch(self, force: bool = False) -> list[str]:
        """Download every declared file; return the keys queued for the relay."""
        queued = []
        for f in self.files():
            try:
                fetch.download(self.id, f.url, f.rel_path, method=f.method, body=f.body, headers=f.headers, force=force)
            except fetch.Pending:
                queued.append(f"{self.id}/{f.rel_path}")
        return queued

    def path(self, rel_path: str) -> Path:
        p = self.raw_dir / rel_path
        if not p.exists():
            raise FileNotFoundError(f"{self.id}: {rel_path} not cached; run `python -m pipeline fetch {self.id}`")
        return p

    def process(self) -> dict:
        raise NotImplementedError

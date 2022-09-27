"""Manifest parser for the relevant bits and pieces."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import tomli
import tomli_w


@dataclass
class Bin:
    name: str
    path: str

    def to_json(self) -> dict[str, str]:
        return {"name": self.name, "path": self.path}


@dataclass
class Package:
    name: str
    version: str | None
    edition: str | None
    unhandled: dict[str, Any] | None

    @classmethod
    def from_json(cls, json: dict[str, str]) -> Package:
        cloned = dict(json)
        name = cloned.pop("name")
        version = cloned.pop("version", None)
        edition = cloned.pop("edition", None)
        return Package(name, version, edition, cloned)

    def to_json(self) -> dict[str, str]:
        values = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "unhandled"}
        if self.unhandled is not None:
            values.update({k: v for k, v in self.unhandled.items() if v is not None})
        return {k: v for k, v in values.items() if v is not None}


@dataclass
class CargoManifest:
    _path: Path
    _data: dict[str, Any]

    package: Package
    bin: list[Bin]

    @classmethod
    def read(cls, path: Path) -> CargoManifest:
        with path.open("rb") as fp:
            return cls.of(path, tomli.load(fp))

    @classmethod
    def of(cls, path: Path, data: dict[str, Any]) -> CargoManifest:
        return cls(
            path,
            data,
            Package.from_json(data["package"]),
            [Bin(**x) for x in data.get("bin", [])],
        )

    def to_json(self) -> dict[str, Any]:
        result = self._data.copy()
        if self.bin:
            result["bin"] = [x.to_json() for x in self.bin]
        else:
            result.pop("bin", None)
        result["package"] = self.package.to_json()
        return result

    def to_toml_string(self) -> str:
        return tomli_w.dumps(self.to_json())

    def save(self, path: Path | None = None) -> None:
        path = path or self._path
        with path.open("wb") as fp:
            tomli_w.dump(self.to_json(), fp)

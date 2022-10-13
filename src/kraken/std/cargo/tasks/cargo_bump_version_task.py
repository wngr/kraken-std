from __future__ import annotations

import contextlib
from pathlib import Path

from kraken.core import BackgroundTask, Property, TaskStatus
from kraken.core.util.fs import atomic_file_swap

from kraken.std.cargo.manifest import CargoManifest


class CargoBumpVersionTask(BackgroundTask):
    """This task bumps the version number in `Cargo.toml`. The change can be reverted afterwards if the
    :attr:`revert` option is enabled."""

    description = 'Bump the version in "%(cargo_toml_file)s" to "%(version)s" [temporary: %(revert)s]'
    version: Property[str]
    revert: Property[bool] = Property.default(False)
    cargo_toml_file: Property[Path] = Property.default("Cargo.toml")

    def _get_updated_cargo_toml(self) -> str:
        manifest = CargoManifest.read(self.cargo_toml_file.get())
        manifest.package.version = self.version.get()
        if manifest.workspace and manifest.workspace.package:
            manifest.workspace.package.version = self.version.get()
        return manifest.to_toml_string()

    # BackgroundTask

    def start_background_task(self, exit_stack: contextlib.ExitStack) -> TaskStatus | None:
        content = self._get_updated_cargo_toml()
        revert = self.revert.get()
        fp = exit_stack.enter_context(atomic_file_swap(self.cargo_toml_file.get(), "w", always_revert=revert))
        fp.write(content)
        fp.close()
        version = self.version.get()
        return (
            TaskStatus.started(f"temporary bump to {version}")
            if revert
            else TaskStatus.succeeded(f"permanent bump to {version}")
        )

    # Task

    def finalize(self) -> None:
        self.cargo_toml_file.set(self.cargo_toml_file.value.map(lambda path: self.project.directory / path))

from __future__ import annotations

import contextlib
from pathlib import Path

from kraken.core import BackgroundTask, Property, TaskStatus
from kraken.core.util.fs import atomic_file_swap

from kraken.std.cargo import CargoProject
from kraken.std.cargo.manifest import CargoManifest


class CargoBumpVersionTask(BackgroundTask):
    """This task bumps the version numbers in `Cargo.toml`, and if a registry is specified, updates the registry and
    version of 'path' dependencies. The change can be reverted afterwards if the :attr:`revert` option is enabled."""

    description = 'Bump the version in "%(cargo_toml_file)s" to "%(version)s" [temporary: %(revert)s]'
    version: Property[str]
    registry: Property[str]
    revert: Property[bool] = Property.default(False)
    cargo_toml_file: Property[Path] = Property.default("Cargo.toml")

    def _get_updated_cargo_toml(self) -> str:
        manifest = CargoManifest.read(self.cargo_toml_file.get())
        if manifest.package is None:
            return manifest.to_toml_string()

        manifest.package.version = self.version.get()
        if manifest.workspace and manifest.workspace.package:
            manifest.workspace.package.version = self.version.get()

        if self.registry.is_filled():
            cargo = CargoProject.get_or_create(self.project)
            registry = cargo.registries[self.registry.get()]
            self._push_version_to_path_deps(manifest, registry.alias)
        return manifest.to_toml_string()

    def _push_version_to_path_deps(self, manifest: CargoManifest, registry_alias: str) -> None:
        """For each dependency in the given manifest, if the dependency is a `path` dependency, injects the current
        version and registry (required for publishing - path dependencies cannot be published alone)."""
        if manifest.dependencies:
            dependencies = manifest.dependencies.data
            for dep_name in dependencies:
                dependency = dependencies[dep_name]
                if isinstance(dependency, dict):
                    if "path" in dependency:
                        dependency["version"] = self.version.get()
                        dependency["registry"] = registry_alias

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

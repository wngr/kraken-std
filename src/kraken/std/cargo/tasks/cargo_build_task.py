from __future__ import annotations

import os
import shlex
import subprocess as sp
from dataclasses import dataclass
from typing import Dict, List, Optional

from kraken.core import Project, Property, Task, TaskStatus

from kraken.std.descriptors.resource import BinaryArtifact

from ..manifest import CargoManifest


@dataclass
class CargoBinaryArtifact(BinaryArtifact):
    pass


class CargoBuildTask(Task):
    """This task runs `cargo build` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    #: The build target (debug or release). If this is anything else, the :attr:`out_binaries` will be set
    #: to an empty list instead of parsed from the Cargo manifest.
    target: Property[str]

    #: Additional arguments to pass to the Cargo command-line.
    additional_args: Property[List[str]] = Property.default_factory(list)

    #: Whether to build incrementally or not.
    incremental: Property[Optional[bool]] = Property.default(None)

    #: Environment variables for the Cargo command.
    env: Property[Dict[str, str]] = Property.default_factory(dict)

    #: An output property for the Cargo binaries that are being produced by this build.
    out_binaries: Property[List[CargoBinaryArtifact]] = Property.output()

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)

    def get_description(self) -> str | None:
        command = self.get_cargo_command({})
        self.make_safe(command, {})
        return f"Run `{' '.join(command)}`."

    def get_cargo_command_additional_flags(self) -> List[str]:
        return shlex.split(os.environ.get("KRAKEN_CARGO_BUILD_FLAGS", ""))

    def get_cargo_command(self, env: Dict[str, str]) -> List[str]:
        incremental = self.incremental.get()
        if incremental is not None:
            env["CARGO_INCREMENTAL"] = "1" if incremental else "0"
        return ["cargo", "build"] + self.additional_args.get()

    def make_safe(self, args: List[str], env: Dict[str, str]) -> None:
        pass

    def execute(self) -> TaskStatus:
        env = self.env.get()
        command = self.get_cargo_command(env) + self.get_cargo_command_additional_flags()

        safe_command = command[:]
        safe_env = env.copy()
        self.make_safe(safe_command, safe_env)
        self.logger.info("%s [env: %s]", safe_command, safe_env)

        out_binaries = []
        if self.target.get_or(None) in ("debug", "release"):
            # Expose the output binaries that are produced by this task.
            # We only expect a binary to be built if the target is debug or release.
            manifest = CargoManifest.read(self.project.directory / "Cargo.toml")
            target_dir = self.project.directory / os.getenv("CARGO_TARGET_DIR", "target")
            for bin in manifest.bin:
                out_binaries.append(CargoBinaryArtifact(bin.name, target_dir / self.target.get() / bin.name))
        self.out_binaries.set(out_binaries)

        result = sp.call(command, cwd=self.project.directory, env={**os.environ, **env})

        if result == 0:
            for out_bin in out_binaries:
                assert out_bin.path.is_file(), out_bin

        return TaskStatus.from_exit_code(safe_command, result)

""" Provides tasks for Rust projects that build using Cargo. """

from __future__ import annotations

from typing import Sequence

from kraken.core import Project, Supplier
from typing_extensions import Literal

from .config import CargoProject, CargoRegistry
from .tasks.cargo_auth_proxy_task import CargoAuthProxyTask
from .tasks.cargo_build_task import CargoBuildTask
from .tasks.cargo_bump_version_task import CargoBumpVersionTask
from .tasks.cargo_clippy_task import CargoClippyTask
from .tasks.cargo_fmt_task import CargoFmtTask
from .tasks.cargo_publish_task import CargoPublishTask
from .tasks.cargo_sync_config_task import CargoSyncConfigTask
from .tasks.cargo_test_task import CargoTestTask

__all__ = [
    "cargo_auth_proxy",
    "cargo_build",
    "cargo_bump_version",
    "cargo_clippy",
    "cargo_fmt",
    "cargo_publish",
    "cargo_registry",
    "cargo_sync_config",
    "CargoAuthProxyTask",
    "CargoBuildTask",
    "CargoBumpVersionTask",
    "CargoClippyTask",
    "CargoProject",
    "CargoPublishTask",
    "CargoRegistry",
    "CargoSyncConfigTask",
    "CargoTestTask",
]

#: This is the name of a group in every project that contains Cargo tasks to contain the tasks that either support
#: or establish pre-requisites for a Cargo build to be executed. This includes ensuring certain configuration is
#: is up to date and the Cargo auth proxy if it is being used.
CARGO_BUILD_SUPPORT_GROUP_NAME = "cargoBuildSupport"


def cargo_registry(
    alias: str,
    index: str,
    read_credentials: tuple[str, str] | None = None,
    publish_token: str | None = None,
    project: Project | None = None,
) -> None:
    """Adds a Cargo registry to the project. The registry must be synced to disk into the `.cargo/config.toml`
    configuration file. You need to make sure to add a sync task using :func:`cargo_sync_config` if you manage
    your Cargo registries with this function. Can be called multiple times.

    :param alias: The registry alias.
    :param index: The registry index URL (usually an HTTPS URL that ends in `.git`).
    :param read_credentials: Username/password to read from the registry (only for private registries).
    :param publish_token: The token to use with `cargo publish`.

    !!! note Artifactory

        It appears that for Artifactory, the *publish_token* must be of the form `Bearer <TOKEN>` where the token
        is a token generated manually via the JFrog UI. It cannot be an API key.
    """

    cargo = CargoProject.get_or_create(project)
    cargo.add_registry(alias, index, read_credentials, publish_token)


def cargo_auth_proxy(*, project: Project | None = None) -> CargoAuthProxyTask:
    """Creates a background task that the :func:`cargo_build` and :func:`cargo_publish` tasks will depend on to
    inject the read credentials for private registries into HTTPS requests made by Cargo. This is only needed when
    private registries are used."""

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        "cargoAuthProxy",
        CargoAuthProxyTask,
        False,
        group=CARGO_BUILD_SUPPORT_GROUP_NAME,
        registries=Supplier.of_callable(lambda: list(cargo.registries.values())),
    )
    # The auth proxy injects values into the cargo config, the cargoSyncConfig.check ensures that it reflects
    # the temporary changes that should be made to the config. The check has to run before the auth proxy,
    # otheerwise it is garuanteed to fail.
    task.add_relationship(":cargoSyncConfig.check?", strict=False)
    return task


def cargo_sync_config(
    *,
    replace: bool = False,
    project: Project | None = None,
) -> CargoSyncConfigTask:
    """Creates a task that the :func:`cargo_build` and :func:`cargo_publish` tasks will depend on to synchronize
    the `.cargo/config.toml` configuration file, ensuring that the Cargo registries configured with the
    :func:`cargo_registry` function are present and up to date."""

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        "cargoSyncConfig",
        CargoSyncConfigTask,
        group="apply",
        registries=Supplier.of_callable(lambda: list(cargo.registries.values())),
        replace=replace,
    )
    check_task = task.create_check()
    project.group(CARGO_BUILD_SUPPORT_GROUP_NAME).add(check_task)
    return task


def cargo_clippy(
    *,
    allow: str = "staged",
    fix: bool = False,
    name: str | None = None,
    group: str | None = "_auto_",
    project: Project | None = None,
) -> CargoClippyTask:
    project = project or Project.current()
    name = "cargoClippyFix" if fix else "cargoClippy"
    group = ("fmt" if fix else "lint") if group == "_auto_" else group
    task = project.do(name, CargoClippyTask, False, group=group, fix=fix, allow=allow)

    # Clippy builds your code.
    task.add_relationship(f":{CARGO_BUILD_SUPPORT_GROUP_NAME}?")

    return task


def cargo_fmt(*, project: Project | None = None) -> None:
    project = project or Project.current()
    project.do("cargoFmt", CargoFmtTask, group="fmt")
    project.do("cargoFmtCheck", CargoFmtTask, group="lint", check=True)


def cargo_bump_version(
    *,
    version: str,
    revert: bool = True,
    name: str = "cargoBumpVersion",
    group: str | None = CARGO_BUILD_SUPPORT_GROUP_NAME,
    registry: str | None = None,
    project: Project | None = None,
) -> CargoBumpVersionTask:
    """Get or create a task that bumps the version in `Cargo.toml`.

    :param version: The version number to bump to.
    :param revert: Revert the version number after all direct dependants have run.
    :param name: The task name. Note that if another task with the same configuration but different name exists,
        it will not change the name of the task and that task will still be reused.
    :param group: The group to assign the task to (even if the task is reused)."""

    project = project or Project.current()

    return project.do(
        name,
        CargoBumpVersionTask,
        group=group,
        version=version,
        revert=revert,
        registry=registry,
    )


def cargo_build(
    mode: Literal["debug", "release"],
    incremental: bool | None = None,
    env: dict[str, str] | None = None,
    *,
    group: str | None = "build",
    name: str | None = None,
    project: Project | None = None,
) -> CargoBuildTask:
    """Creates a task that runs `cargo build`.

    :param mode: Whether to create a task that runs the debug or release build.
    :param incremental: Whether to build incrementally or not (with the `--incremental=` option). If not
        specified, the option is not specified and the default behaviour is used.
    :param env: Override variables for the build environment variables. Values in this dictionary override
        variables in :attr:`CargoProject.build_env`.
    :param name: The name of the task. If not specified, defaults to `:cargoBuild{mode.capitalied()}`.
    :param version: Bump the Cargo.toml version temporarily while building to the given version."""

    assert mode in ("debug", "release"), repr(mode)
    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        f"cargoBuild{mode.capitalize()}" if name is None else name,
        CargoBuildTask,
        default=False,
        group=group,
        incremental=incremental,
        target=mode,
        additional_args=["--release"] if mode == "release" else [],
        env=Supplier.of_callable(lambda: {**cargo.build_env, **(env or {})}),
    )
    task.add_relationship(f":{CARGO_BUILD_SUPPORT_GROUP_NAME}?")
    return task


def cargo_test(
    incremental: bool | None = None,
    env: dict[str, str] | None = None,
    *,
    group: str | None = "test",
    project: Project | None = None,
) -> CargoTestTask:
    """Creates a task that runs `cargo test`.

    :param incremental: Whether to build the tests incrementally or not (with the `--incremental=` option). If not
        specified, the option is not specified and the default behaviour is used.
    :param env: Override variables for the build environment variables. Values in this dictionary override
        variables in :attr:`CargoProject.build_env`."""

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        "cargoTest",
        CargoTestTask,
        default=False,
        group=group,
        incremental=incremental,
        env=Supplier.of_callable(lambda: {**cargo.build_env, **(env or {})}),
    )
    task.add_relationship(f":{CARGO_BUILD_SUPPORT_GROUP_NAME}?")
    return task


def cargo_publish(
    registry: str,
    incremental: bool | None = None,
    env: dict[str, str] | None = None,
    *,
    verify: bool = True,
    additional_args: Sequence[str] = (),
    name: str = "cargoPublish",
    project: Project | None = None,
) -> CargoPublishTask:
    """Creates a task that publishes the create to the specified *registry*.

    :param registry: The alias of the registry to publish to.
    :param incremental: Incremental builds on or off.
    :param env: Environment variables (overrides :attr:`CargoProject.build_env`).
    :param verify: If this is enabled, the `cargo publish` task will build the crate after it is packaged.
        Disabling this just packages the crate and publishes it. Only if this is enabled will the created
        task depend on the auth proxy.
    """

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)

    task = project.do(
        name,
        CargoPublishTask,
        False,
        group="publish",
        registry=Supplier.of_callable(lambda: cargo.registries[registry]),
        additional_args=list(additional_args),
        allow_dirty=True,
        incremental=incremental,
        verify=verify,
        env=Supplier.of_callable(lambda: {**cargo.build_env, **(env or {})}),
    )

    task.add_relationship(f":{CARGO_BUILD_SUPPORT_GROUP_NAME}?")

    return task

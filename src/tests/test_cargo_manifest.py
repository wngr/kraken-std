from pathlib import Path

from kraken.std.cargo.manifest import CargoManifest


def test_cargo_manifest_handles_unknown_fields_correctly() -> None:
    manifest = CargoManifest.of(
        Path(""),
        {
            "package": {
                "name": "test",
                "version": "0.1.2",
                "edition": "2021",
                "include": ["test1", "test2"],
                "authors": ["author1", "author2"],
            },
            "bin": [{"name": "bin1", "path": "path"}],
        },
    )

    assert manifest.package is not None
    assert manifest.package.name == "test"
    assert manifest.package.version == "0.1.2"
    assert manifest.package.edition == "2021"

    assert manifest.package.unhandled is not None
    assert len(manifest.package.unhandled) == 2
    assert len(manifest.package.unhandled["include"]) == 2
    assert manifest.package.unhandled["authors"] == ["author1", "author2"]


def test_cargo_manifest_writes_json_correctly() -> None:
    input_json = {
        "package": {
            "name": "test",
            "version": "0.1.2",
            "edition": "2021",
            "include": ["test1", "test2"],
            "authors": ["author1", "author2"],
        },
        "bin": [{"name": "bin1", "path": "path"}],
    }

    manifest = CargoManifest.of(Path(""), input_json)
    output_json = manifest.to_json()

    assert input_json == output_json


def test_cargo_manifest_complex_file() -> None:
    """
    This test wants to ensure that when reading a complex file (like that found in the rand cargo crate)
    it correctly handles all of the unknown fields, and maintains their type (generally).
    """

    cargo_file = Path(__file__).parent / "data" / "complex_manifest.toml"
    manifest = CargoManifest.read(cargo_file)

    assert manifest is not None
    assert manifest.package is not None
    assert manifest.package.unhandled is not None
    assert len(manifest.package.unhandled) > 0
    assert manifest.package.name == "rand"
    assert manifest.package.edition == "2018"
    assert manifest.package.version == "0.8.5"
    assert manifest.package.unhandled["include"] == ["src/", "LICENSE-*", "README.md", "CHANGELOG.md", "COPYRIGHT"]
    assert manifest.package.unhandled["autobenches"]

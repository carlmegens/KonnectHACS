"""A candidate must exactly match the source allowlist and stay reproducible."""

import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prepare_ouderapp", ROOT / "scripts/prepare_repository.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_exact_source_inventory_and_reproducibility(tmp_path):
    first = MODULE.build(ROOT, tmp_path)
    second = MODULE.build(ROOT, tmp_path)
    assert first == second
    with ZipFile(tmp_path / first[0]["archive"]) as archive:
        assert all(name.startswith(MODULE.COMPONENT) for name in archive.namelist())
        assert not any(
            part in name
            for name in archive.namelist()
            for part in ("tests/", "__pycache__", ".storage", "STATUS", "node_modules")
        )
        for name in MODULE.MODULES:
            assert (
                archive.read(MODULE.COMPONENT + name)
                == (ROOT / MODULE.COMPONENT / name).read_bytes()
            )
    manifest = json.loads((ROOT / MODULE.COMPONENT / "manifest.json").read_text())
    assert manifest["documentation"] == "https://github.com/carlmegens/KonnectHACS"
    assert manifest["codeowners"] == ["@carlmegens"]


def test_unlisted_private_file_never_enters_archive(tmp_path):
    from shutil import copytree

    copy = tmp_path / "source"
    copytree(
        ROOT / "custom_components",
        copy / "custom_components",
        ignore=lambda path, names: [n for n in names if n == "__pycache__"],
    )
    for name in (*MODULE.PUBLIC_DOCS, *MODULE.DEVELOPMENT_FILES):
        (copy / name).parent.mkdir(parents=True, exist_ok=True)
        (copy / name).write_bytes((ROOT / name).read_bytes())
    secret = b"SYNTHETIC-" + b"UNLISTED-PRIVATE-FILE"
    (copy / MODULE.COMPONENT / "private-token.txt").write_bytes(secret)
    (copy / "STATUS.md").write_text("SYNTHETIC-PRIVATE-NOTES")
    built = MODULE.build(copy, tmp_path / "output")
    for result in built:
        with ZipFile(tmp_path / "output" / result["archive"]) as archive:
            assert all(secret not in archive.read(name) for name in archive.namelist())
            assert "STATUS.md" not in archive.namelist()
    target = copy / MODULE.COMPONENT / "api.py"
    target.unlink()
    target.symlink_to(ROOT / MODULE.COMPONENT / "api.py")
    with pytest.raises(ValueError, match="unavailable"):
        MODULE.collect(copy)

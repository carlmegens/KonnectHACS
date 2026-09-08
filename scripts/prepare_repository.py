"""Build a deterministic local candidate and clean repository archive, never publish."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

COMPONENT = "custom_components/ouderapp/"
MODULES = (
    "__init__.py",
    "api.py",
    "binary_sensor.py",
    "config_flow.py",
    "const.py",
    "content.py",
    "coordinator.py",
    "dashboard.py",
    "diagnostics.py",
    "entity.py",
    "frontend.py",
    "runtime.py",
    "sensor.py",
    "services.py",
    "manifest.json",
    "services.yaml",
    "strings.json",
    "translations/en.json",
    "translations/nl.json",
    "frontend/ouderapp-card.js",
    "brand/icon.png",
)
PUBLIC_DOCS = ("README.md", "LICENSE", "CHANGELOG.md", "hacs.json")

DEVELOPMENT_FILES = (
    "requirements-test.txt",
    "pyproject.toml",
    ".gitignore",
    "scripts/prepare_repository.py",
    "tests/conftest.py",
    "tests/test_api.py",
    "tests/test_content.py",
    "tests/test_dashboard.py",
    "tests/test_distribution.py",
    "tests/test_end_to_end.py",
    "tests/test_frontend.py",
    "tests/test_ha.py",
    "tests/test_media.py",
    "tests/frontend/README.md",
    "tests/frontend/harness.js",
    "tests/frontend/index.html",
    "tests/frontend/package.json",
    "tests/frontend/serve.mjs",
    "tests/frontend/test-card.mjs",
)


def collect(root: Path) -> tuple[str, dict[str, bytes]]:
    manifest = json.loads((root / COMPONENT / "manifest.json").read_text())
    if manifest["domain"] != "ouderapp" or not manifest["config_flow"]:
        raise ValueError("Invalid integration manifest")
    files = {}
    for name in MODULES:
        source = root / COMPONENT / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Required source unavailable: {name}")
        value = source.read_bytes()
        if source.suffix == ".py":
            compile(value, name, "exec")
        elif source.suffix == ".json":
            json.loads(value)
        files[COMPONENT + name] = value
    # Preserve copyright notices inside the installed integration too.
    files[COMPONENT + "LICENSE"] = (root / "LICENSE").read_bytes()
    return manifest["version"], files


def archive(path: Path, files: dict[str, bytes]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as target:
        for name, data in sorted(files.items()):
            member = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            member.compress_type = ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            target.writestr(member, data)
    with ZipFile(path) as check:
        if check.testzip() is not None or set(check.namelist()) != set(files):
            raise ValueError("Archive validation failed")
        for name, data in files.items():
            if check.read(name) != data:
                raise ValueError("Archive differs from source")
    inventory = {
        "archive": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    path.with_suffix(path.suffix + ".inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n"
    )
    return inventory


def build(root: Path, output: Path) -> list[dict]:
    version, files = collect(root)
    install = archive(output / f"ouderapp-{version}-candidate-install.zip", files)
    public = dict(files)
    for name in (*PUBLIC_DOCS, *DEVELOPMENT_FILES):
        source = root / name
        if source.is_symlink():
            raise ValueError("Symlink document refused")
        public[name] = source.read_bytes()
    repository = archive(output / f"KonnectHACS-{version}-candidate-repository.zip", public)
    return [install, repository]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "dist")
    args = parser.parse_args()
    for result in build(Path(__file__).resolve().parents[1], args.output):
        print(result["archive"], result["sha256"])

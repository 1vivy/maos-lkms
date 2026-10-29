# SPDX-License-Identifier: GPL-2.0-only
"""Canonical inventories for the source bytes supplied to module builds."""
from __future__ import annotations
import fnmatch
import hashlib
import os
from pathlib import Path

EXCLUDED = (
    '.git', 'out', '__pycache__', '.tmp_versions',
    '*.o', '*.ko', '*.ko.debug', '*.ko.build.json', '*.cmd', '*.mod', '*.mod.c',
    '*.a', '*.d', '*.order', '*.dtb', '*.dtbo', '*.symvers', '*.build.log',
    'Module.symvers', 'Module.markers', 'modules.builtin', 'modules.builtin.modinfo',
    '.depend', '.cache.mk',
)


def ignored(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in EXCLUDED)


def ignore_names(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if ignored(name)}


def inventory(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise ValueError(f'source directory is missing: {root}')
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not ignored(name))
        for name in dirs + sorted(name for name in files if not ignored(name)):
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f'source symlink is not permitted: {path}')
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f'non-regular source input: {path}')
            with path.open('rb') as stream:
                result[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(sorted(result.items()))


def verify(root: Path, expected: object) -> None:
    if not isinstance(expected, dict) or not expected or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in expected.items()):
        raise ValueError(f'missing build-time source inventory for {root}; rebuild required')
    actual = inventory(root)
    if actual != expected:
        added = sorted(actual.keys() - expected.keys())
        removed = sorted(expected.keys() - actual.keys())
        changed = sorted(key for key in actual.keys() & expected.keys() if actual[key] != expected[key])
        raise ValueError(f'source bytes changed: {root}: added={added}, removed={removed}, changed={changed}')

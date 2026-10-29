# SPDX-License-Identifier: GPL-2.0-only
"""Tamper tests for the canonical source inventory."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from . import source_manifest


class SourceManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="source-manifest-")
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_inventory_is_stable_and_excludes_generated_objects(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src/code.c").write_text("int x;\n")
        (self.root / "Kbuild").write_text("obj-m := x.o\n")
        (self.root / "x.o").write_bytes(b"object")
        (self.root / "x.ko").write_bytes(b"module")
        (self.root / "x.ko.build.json").write_text("{}\n")
        expected = source_manifest.inventory(self.root)
        self.assertEqual(expected, source_manifest.inventory(self.root))
        self.assertEqual(set(expected), {"Kbuild", "src/code.c"})

    def test_changed_added_and_deleted_source_is_rejected(self) -> None:
        (self.root / "code.c").write_text("one\n")
        expected = source_manifest.inventory(self.root)
        (self.root / "code.c").write_text("two\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            source_manifest.verify(self.root, expected)
        (self.root / "code.c").write_text("one\n")
        (self.root / "extra.c").write_text("extra\n")
        with self.assertRaisesRegex(ValueError, "added"):
            source_manifest.verify(self.root, expected)
        (self.root / "extra.c").unlink()
        (self.root / "code.c").unlink()
        with self.assertRaisesRegex(ValueError, "removed"):
            source_manifest.verify(self.root, expected)

    def test_symlinked_source_is_rejected(self) -> None:
        target = self.root / "target.c"
        target.write_text("int y;\n")
        (self.root / "link.c").symlink_to(target.name)
        with self.assertRaisesRegex(ValueError, "symlink"):
            source_manifest.inventory(self.root)


if __name__ == "__main__":
    unittest.main()

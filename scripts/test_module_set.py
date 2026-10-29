# SPDX-License-Identifier: GPL-2.0-only
"""Host-only tests for complete module-set and candidate packaging gates."""
from __future__ import annotations
import hashlib
import json
import tarfile
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from . import module_set
from . import source_manifest

ROOT = Path(__file__).resolve().parents[1]
KMI = {"branch": "android16-6.12", "generation": 6}
ARCH = "aarch64"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ModuleSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.out_root = ROOT / "out"
        self.out_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="module-set-test-", dir=self.out_root)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "modules" / "android16-6.12-6" / ARCH

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_modules(self, names: tuple[str, ...], include_thin_provenance: bool = False,
                       source_evidence: dict[str, dict[str, dict[str, str]]] | None = None) -> dict[str, bytes]:
        payloads = {}
        for name in names:
            module_dir = self.directory / name
            module_dir.mkdir(parents=True)
            payload = f"final bytes for {name}\n".encode()
            payloads[name] = payload
            (module_dir / f"{name}.ko").write_bytes(payload)
            info = {"kmi": KMI, "module_sha256": digest(payload),
                    "compiler": {"sha256": "c" * 64}}
            if source_evidence is not None:
                info["source_evidence"] = source_evidence[name]
            if name == "dm-thin-pool" and include_thin_provenance:
                provenance = {"module": name, "profile": "verified",
                              "kmi": {**KMI, "arch": ARCH},
                              "kernel": {"release": "6.12.76-test"}}
                provenance_bytes = (json.dumps(provenance, sort_keys=True) + "\n").encode()
                provenance_path = (self.root / "prepared" / "android16-6.12-6" / ARCH / name / "PROVENANCE.json")
                provenance_path.parent.mkdir(parents=True)
                provenance_path.write_bytes(provenance_bytes)
                info["module_provenance"] = {"sha256": digest(provenance_bytes),
                                             "profile": "verified",
                                             "kernel_release": "6.12.76-test"}
            (module_dir / f"{name}.ko.build.json").write_text(json.dumps(info, sort_keys=True) + "\n")
        return payloads

    def create_source_evidence(self, names: tuple[str, ...]) -> dict[str, dict[str, dict[str, str]]]:
        include = source_manifest.inventory(ROOT / "include")
        tools = source_manifest.inventory(ROOT / "scripts")
        evidence = {}
        for name in names:
            tree = self.root / "prepared" / "android16-6.12-6" / ARCH / name
            tree.mkdir(parents=True)
            (tree / "Kbuild").write_text(f"obj-m := {name}.o\n")
            (tree / f"{name}.c").write_text("int x;\n")
            evidence[name] = {"module": source_manifest.inventory(tree),
                              "include": include, "tools": tools}
        return evidence

    def record(self, names: tuple[str, ...], failed: str = "") -> int:
        return module_set.record(Namespace(directory=self.directory, requested=",".join(names),
                                           failed=failed, branch=KMI["branch"],
                                           generation=KMI["generation"], arch=ARCH,
                                           image="ghcr.io/example/ddk@sha256:" + "a" * 64))

    def test_partial_set_cannot_be_packaged(self) -> None:
        self.create_modules(("dm-thin-pool",))
        self.assertEqual(self.record(("dm-thin-pool",)), 0)
        manifest = json.loads((self.directory / "set.json").read_text())
        self.assertFalse(manifest["complete"])
        with self.assertRaisesRegex(ValueError, "partial"):
            module_set.package(Namespace(directory=self.directory,
                                         out=self.root / "release" / "candidate"))

    def test_complete_candidate_keeps_admitted_bytes_and_provenance(self) -> None:
        names = module_set.REQUIRED
        payloads = self.create_modules(names, include_thin_provenance=True)
        self.assertEqual(self.record(names), 0)
        out = self.root / "release" / "candidate"
        self.assertEqual(module_set.package(Namespace(directory=self.directory, out=out)), 0)
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["qualification"], "build-and-admission-only")
        self.assertFalse(manifest["device_qualified"])
        for name, payload in payloads.items():
            self.assertEqual((out / "egysk/kmod" / f"{name}.ko").read_bytes(), payload)
        provenance = out / "provenance/dm-thin-pool.PROVENANCE.json"
        self.assertTrue(provenance.is_file())
        thin_entry = next(item for item in manifest["artifacts"] if item["name"] == "dm-thin-pool")
        self.assertEqual(thin_entry["source_provenance_sha256"], digest(provenance.read_bytes()))
        with self.assertRaises(FileExistsError):
            module_set.package(Namespace(directory=self.directory, out=out))

    def test_package_refuses_changed_final_bytes(self) -> None:
        self.create_modules(module_set.REQUIRED)
        self.assertEqual(self.record(module_set.REQUIRED), 0)
        (self.directory / "dm-thin-pool/dm-thin-pool.ko").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed after admission"):
            module_set.package(Namespace(directory=self.directory,
                                         out=self.root / "release" / "candidate"))

    def test_release_refuses_metadata_without_source_evidence(self) -> None:
        self.create_modules(module_set.REQUIRED)
        self.assertEqual(self.record(module_set.REQUIRED), 0)
        with self.assertRaisesRegex(ValueError, "source inventory"):
            module_set.package(Namespace(directory=self.directory,
                                         out=self.root / "release" / "candidate",
                                         release=True))

    def test_release_archive_is_deterministic(self) -> None:
        bundle = self.root / "bundle"
        (bundle / "egysk/kmod").mkdir(parents=True)
        (bundle / "egysk/kmod/gpt.ko").write_bytes(b"module bytes\n")
        (bundle / "manifest.json").write_text('{"schema_version": 1}\n')
        module_set.write_sha256sums(bundle)
        first = self.root / "first.tar.gz"
        second = self.root / "second.tar.gz"
        module_set.write_archive(bundle, first, "maos-lkms-test")
        module_set.write_archive(bundle, second, "maos-lkms-test")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with tarfile.open(first, "r:gz") as archive:
            self.assertEqual(sorted(archive.getnames()), [
                "maos-lkms-test/SHA256SUMS",
                "maos-lkms-test/egysk",
                "maos-lkms-test/egysk/kmod",
                "maos-lkms-test/egysk/kmod/gpt.ko",
                "maos-lkms-test/manifest.json",
            ])

    def test_release_packages_both_gpl_modules_without_efvs_notice(self) -> None:
        evidence = self.create_source_evidence(module_set.REQUIRED)
        payloads = self.create_modules(module_set.REQUIRED, source_evidence=evidence)
        self.assertEqual(self.record(module_set.REQUIRED), 0)
        out = self.root / "release" / "release-candidate"
        self.assertEqual(module_set.package(Namespace(directory=self.directory, out=out, release=True)), 0)
        notice = (out / "SOURCE-NOTICE.md").read_text()
        self.assertIn("`dm-thin-pool` and `part-projection` are distributed under GPL-2.0-only", notice)
        self.assertNotIn("Apache", notice)
        self.assertNotIn("efivar", notice)
        self.assertTrue((out / "LICENSES/GPL-2.0-only.txt").is_file())
        self.assertFalse((out / "LICENSES/Apache-2.0.txt").exists())
        self.assertEqual(sorted(path.name for path in (out / "sources/kernel").iterdir()),
                         ["dm-thin-pool", "part-projection"])
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertNotIn("license_review", manifest)
        for name, payload in payloads.items():
            self.assertEqual((out / "egysk/kmod" / f"{name}.ko").read_bytes(), payload)
        with tarfile.open(out.with_name(out.name + ".tar.gz"), "r:gz") as archive:
            names = archive.getnames()
        self.assertIn("maos-lkms-android16-6.12-6-aarch64/sources/kernel/part-projection/Kbuild", names)

    def test_retired_module_requests_are_refused(self) -> None:
        self.directory.mkdir(parents=True)
        for requested in ("efivarfs", "dm-thin-pool,efivar_store"):
            with self.subTest(requested=requested), self.assertRaisesRegex(ValueError, "required module set"):
                self.record(tuple(requested.split(",")))

    def test_candidate_listing_a_retired_module_is_refused(self) -> None:
        self.create_modules(module_set.REQUIRED)
        self.assertEqual(self.record(module_set.REQUIRED), 0)
        manifest = json.loads((self.directory / "set.json").read_text())
        manifest["modules"].append({"name": "efivar_store", "status": "accepted",
                                    "module_sha256": None, "build_info_sha256": None})
        (self.directory / "set.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "admitted maOS module set"):
            module_set.package(Namespace(directory=self.directory,
                                         out=self.root / "release" / "forged"))

    def test_output_paths_outside_ignored_tree_are_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="module-set-outside-") as outside:
            with self.assertRaisesRegex(ValueError, "inside"):
                module_set.checked_out(Path(outside) / "candidate", strict=False)


if __name__ == "__main__":
    unittest.main()

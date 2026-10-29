#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Record build-set completeness and create maOS bootstrap module bundles."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

try:
    from . import source_manifest
except ImportError:
    import source_manifest

REQUIRED = ("dm-thin-pool", "part-projection")
REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_IGNORES = shutil.ignore_patterns(
    ".git", "out", "__pycache__", "*.o", "*.ko",
    "*.cmd", "*.mod", "*.mod.c", "*.mod.o", "*.a", "*.d", "*.order",
    "*.dtb", "*.dtbo", "*.symvers", "*.build.log", "*.ko.debug",
    "*.ko.build.json", "Module.symvers",
    "modules.order", "modules.builtin", "modules.builtin.modinfo",
    ".depend", ".cache.mk", ".tmp_versions")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy_source(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, ignore=SOURCE_IGNORES)


def source_tree(out_root: Path, identity: dict[str, object], architecture: str, name: str) -> Path:
    base = f"{identity['branch']}-{identity['generation']}"
    for parent in ("prepared", "module-src"):
        candidate = out_root / parent / base / architecture / name
        if (candidate / "Kbuild").is_file():
            return candidate
    raise ValueError(f"release refused: source tree for {name} is unavailable under {out_root}")


def write_sha256sums(stage: Path) -> None:
    lines = [f"{sha256(path)}  {path.relative_to(stage).as_posix()}"
             for path in sorted(stage.rglob("*"))
             if path.is_file() and path.name != "SHA256SUMS"]
    (stage / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def write_archive(stage: Path, archive: Path, prefix: str) -> None:
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in sorted(stage.rglob("*")):
                    name = f"{prefix}/{path.relative_to(stage).as_posix()}"
                    info = tar.gettarinfo(str(path), arcname=name)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    info.pax_headers = {}
                    if info.isdir():
                        info.mode = 0o755
                    elif info.isfile():
                        info.mode = 0o755 if os.access(path, os.X_OK) else 0o644
                    if info.issym() and os.path.isabs(info.linkname):
                        raise ValueError(f"release refused: absolute symlink in source bundle: {path}")
                    if info.isfile():
                        with path.open("rb") as stream:
                            tar.addfile(info, stream)
                    else:
                        tar.addfile(info)


def checked_out(path: Path, strict: bool) -> Path:
    root = Path(__file__).resolve().parents[1]
    out_root = root / "out"
    if out_root.is_symlink():
        raise ValueError("repository out/ must not be a symlink")
    allowed = out_root.resolve()
    resolved = path.resolve(strict=strict)
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"path must stay inside {out_root}: {path}")
    return resolved


def record(args: argparse.Namespace) -> int:
    requested = args.requested.split(",")
    if not requested or len(set(requested)) != len(requested) or any(name not in REQUIRED for name in requested):
        raise ValueError("requested modules must be a non-empty unique subset of the required module set")
    failures = set(filter(None, args.failed.split(",")))
    if not failures <= set(requested):
        raise ValueError("failed modules must belong to the requested module set")
    directory = checked_out(args.directory, strict=True)
    modules = []
    for name in requested:
        artifact = directory / name / f"{name}.ko"
        build_info = directory / name / f"{name}.ko.build.json"
        status = "failed" if name in failures else "accepted"
        artifact_hash = None
        build_info_hash = None
        if status == "accepted":
            if not artifact.is_file() or not build_info.is_file():
                status = "failed"
            else:
                info = json.loads(build_info.read_text())
                identity = {"branch": args.branch, "generation": args.generation}
                artifact_hash = sha256(artifact)
                compiler_info = info.get("compiler") if isinstance(info, dict) else None
                if (not isinstance(info, dict) or info.get("kmi") != identity
                        or info.get("module_sha256") != artifact_hash
                        or not isinstance(compiler_info, dict)
                        or not compiler_info.get("sha256")):
                    status = "failed"
                    artifact_hash = None
                else:
                    build_info_hash = sha256(build_info)
        modules.append({"name": name, "status": status,
                        "module_sha256": artifact_hash,
                        "build_info_sha256": build_info_hash})
    complete = set(requested) == set(REQUIRED) and all(item["status"] == "accepted" for item in modules)
    manifest = {"schema_version": 1, "kmi": {"branch": args.branch, "generation": args.generation},
                "arch": args.arch, "image": args.image, "complete": complete,
                "requested_modules": requested, "modules": modules}
    path = directory / "set.json"
    if path.exists():
        raise FileExistsError(f"module set record already exists: {path}")
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if all(item["status"] == "accepted" for item in modules) else 1


def package(args: argparse.Namespace) -> int:
    source = checked_out(args.directory, strict=True)
    if len(source.parents) < 3 or source.parents[1].name != "modules":
        raise ValueError("module set directory must be inside OUT_DIR/modules/<branch>-<generation>/<arch>")
    out_path = checked_out(args.out, strict=False)
    release = bool(getattr(args, "release", False))
    manifest_path = source / "set.json"
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict) or manifest.get("complete") is not True:
        raise ValueError("candidate refused: module set is partial, invalid, or contains failed modules")
    module_items = manifest.get("modules", [])
    if (not isinstance(module_items, list)
            or any(not isinstance(item, dict) for item in module_items)
            or {item.get("name") for item in module_items} != set(REQUIRED)
            or len(module_items) != len(REQUIRED)
            or any(item.get("status") != "accepted" for item in module_items)):
        raise ValueError("candidate refused: module set does not match the admitted maOS module set")
    if out_path.exists():
        raise FileExistsError(f"release output already exists: {out_path}")
    archive_path = out_path.with_name(out_path.name + ".tar.gz")
    archive_sha_path = out_path.with_name(out_path.name + ".tar.gz.sha256")
    if release and (archive_path.exists() or archive_sha_path.exists()):
        raise FileExistsError(f"release archive already exists: {archive_path}")
    parent = out_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".maos-lkms-", dir=parent) as temporary:
        stage = Path(temporary) / "release"
        kmod = stage / "egysk/kmod"
        provenance = stage / "provenance"
        kmod.mkdir(parents=True)
        provenance.mkdir()
        artifacts = []
        source_evidence_by_module = {}
        identity = manifest["kmi"]
        out_root = source.parents[2]
        architecture = manifest["arch"]
        for item in manifest["modules"]:
            name = item["name"]
            module = source / name / f"{name}.ko"
            info_path = source / name / f"{name}.ko.build.json"
            info = json.loads(info_path.read_text())
            evidence = info.get("source_evidence")
            if release and not isinstance(evidence, dict):
                raise ValueError(f"release refused: {name} has no build-time source inventory; rebuild required")
            source_evidence_by_module[name] = evidence
            expected_identity = {"branch": identity["branch"], "generation": identity["generation"]}
            compiler_info = info.get("compiler") if isinstance(info, dict) else None
            if not isinstance(info, dict) or info.get("kmi") != expected_identity:
                raise ValueError(f"candidate refused: {name} build metadata KMI mismatch")
            if not isinstance(compiler_info, dict) or not compiler_info.get("sha256"):
                raise ValueError(f"candidate refused: {name} has no compiler provenance")
            module_hash = sha256(module)
            info_hash = sha256(info_path)
            if module_hash != item.get("module_sha256") or info_hash != item.get("build_info_sha256"):
                raise ValueError(f"candidate refused: {name} bytes changed after admission")
            shutil.copyfile(module, kmod / module.name)
            shutil.copyfile(info_path, provenance / info_path.name)
            artifact = {"name": name, "path": f"egysk/kmod/{module.name}",
                        "sha256": module_hash,
                        "build_info": f"provenance/{info_path.name}",
                        "build_info_sha256": info_hash}
            debug_info = info.get("debug_artifact")
            if debug_info is not None:
                if not isinstance(debug_info, dict):
                    raise ValueError(f"candidate refused: {name} debug artifact metadata is invalid")
                debug_path = source / name / debug_info.get("name", "")
                if (not debug_path.is_file() or sha256(debug_path) != debug_info.get("sha256")):
                    raise ValueError(f"candidate refused: {name} debug artifact is missing or changed")
                debug_name = f"{name}.ko.debug"
                shutil.copyfile(debug_path, provenance / debug_name)
                artifact["debug_artifact"] = f"provenance/{debug_name}"
                artifact["debug_artifact_sha256"] = debug_info["sha256"]
            module_provenance = info.get("module_provenance")
            if module_provenance is not None:
                provenance_candidates = (
                    out_root / "prepared" / f"{identity['branch']}-{identity['generation']}" /
                    architecture / name / "PROVENANCE.json",
                    out_root / "module-src" / f"{identity['branch']}-{identity['generation']}" /
                    architecture / name / "PROVENANCE.json",
                )
                source_provenance = next((path for path in provenance_candidates if path.is_file()), None)
                if (not isinstance(module_provenance, dict) or source_provenance is None
                        or sha256(source_provenance) != module_provenance.get("sha256")):
                    raise ValueError(f"candidate refused: {name} preparation provenance is missing or changed")
                provenance_name = f"{name}.PROVENANCE.json"
                shutil.copyfile(source_provenance, provenance / provenance_name)
                artifact["source_provenance"] = f"provenance/{provenance_name}"
                artifact["source_provenance_sha256"] = module_provenance["sha256"]
                artifact["profile"] = module_provenance["profile"]
                artifact["kernel_release"] = module_provenance["kernel_release"]
            artifacts.append(artifact)
        if release:
            sources = stage / "sources"
            source_kernel = sources / "kernel"
            source_kernel.mkdir(parents=True)
            source_notice = []
            for name in REQUIRED:
                module_source = source_tree(out_root, identity, architecture, name)
                evidence = source_evidence_by_module.get(name)
                if not isinstance(evidence, dict) or "module" not in evidence:
                    raise ValueError(f"release refused: {name} source evidence is missing")
                source_manifest.verify(module_source, evidence["module"])
                copy_source(module_source, source_kernel / name)
                source_manifest.verify(source_kernel / name, evidence["module"])
                source_notice.append(f"- `{name}`: `sources/kernel/{name}`")
            include_evidence = next(
                (evidence.get("include") for evidence in source_evidence_by_module.values()
                 if isinstance(evidence, dict) and isinstance(evidence.get("include"), dict)),
                None)
            if include_evidence is None:
                raise ValueError("release refused: build-time shared-header inventory is missing")
            source_manifest.verify(REPO_ROOT / "include", include_evidence)
            copy_source(REPO_ROOT / "include", sources / "include")
            source_manifest.verify(sources / "include", include_evidence)
            tools_evidence = next(
                (evidence.get("tools") for evidence in source_evidence_by_module.values()
                 if isinstance(evidence, dict) and isinstance(evidence.get("tools"), dict)),
                None)
            if tools_evidence is None:
                raise ValueError("release refused: build-time tool inventory is missing")
            source_manifest.verify(REPO_ROOT / "scripts", tools_evidence)
            copy_source(REPO_ROOT / "scripts", sources / "scripts")
            source_manifest.verify(sources / "scripts", tools_evidence)
            licenses = stage / "LICENSES"
            licenses.mkdir()
            gpl = REPO_ROOT / "kernel/dm-thin-pool/LICENSE"
            if not gpl.is_file():
                raise ValueError(f"release refused: GPL-2.0-only text is missing at {gpl}")
            shutil.copyfile(gpl, licenses / "GPL-2.0-only.txt")
            notice = (
                "# maOS LKM source and license notice\n\n"
                "This archive contains build-and-admission candidates and their corresponding module sources.\n"
                "It is not a device-qualified release.\n\n"
                "## Sources\n\n" + "\n".join(source_notice) + "\n\n"
                "The module sources use the `sources/kernel/` layout. "
                "`sources/include/` supplies the shared header. `sources/scripts/` supplies the build tools.\n\n"
                "`dm-thin-pool` and `part-projection` are distributed under GPL-2.0-only.\n"
                "The license text is in `LICENSES/GPL-2.0-only.txt`.\n\n"
                "The top-level repository GPL-3.0 text does not cover these module subtrees.\n"
            )
            (stage / "SOURCE-NOTICE.md").write_text(notice)
        shutil.copyfile(manifest_path, stage / "set.json")
        release_manifest = {
            "schema_version": 1,
            "artifact_kind": (
                "maos-lkms-source-and-binary-candidate" if release
                else "maos-lkms-bootstrap-module-candidate"),
            "qualification": (
                "build-admission-and-source-candidate" if release
                else "build-and-admission-only"),
            "device_qualified": False,
            "target": {"kmi": identity, "arch": manifest["arch"],
                       "image": manifest.get("image")},
            "artifacts": artifacts,
        }
        if release:
            release_manifest.update({
                "source_bundle": "sources",
                "license_bundle": "LICENSES",
                "source_notice": "SOURCE-NOTICE.md",
                "checksums": "SHA256SUMS",
                "archive": archive_path.name,
            })
        (stage / "manifest.json").write_text(json.dumps(release_manifest, indent=2, sort_keys=True) + "\n")
        if release:
            write_sha256sums(stage)
            write_archive(stage, archive_path,
                          f"maos-lkms-{identity['branch']}-{identity['generation']}-{manifest['arch']}")
            archive_sha_path.write_text(
                f"{sha256(archive_path)}  {archive_path.name}\n")
        stage.rename(out_path)
    print(f"maOS bootstrap module bundle: {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--directory", type=Path, required=True)
    record_parser.add_argument("--branch", required=True)
    record_parser.add_argument("--generation", type=int, required=True)
    record_parser.add_argument("--arch", choices=("aarch64", "x86_64"), required=True)
    record_parser.add_argument("--image", default=os.environ.get("DDK_IMAGE"))
    record_parser.add_argument("--requested", required=True)
    record_parser.add_argument("--failed", default="")
    release_parser = subparsers.add_parser("package")
    release_parser.add_argument("--directory", type=Path, required=True)
    release_parser.add_argument("--out", type=Path, required=True)
    release_parser.add_argument("--release", action="store_true",
                                help="include sources/licenses, deterministic SHA256SUMS, and a tar.gz archive")
    args = parser.parse_args()
    try:
        return record(args) if args.action == "record" else package(args)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"module-set: {error}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

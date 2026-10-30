# Build and KMI admission

This document describes pinned build targets, caller-supplied builds, admission, and build-only candidate bundles. A successful build does not qualify a module for a device.

## Pinned DDK targets

`scripts/ddk-targets.sh` selects an image only for an exact branch and generation. The images use immutable digests:

| Branch | Generation | Image digest | Compiler | ABI dump |
| --- | ---: | --- | --- | --- |
| `android12-5.10` | 9 | `272ada1e61c525116032246df2a790d1ccec1804b7a9e0b09203c5e650dcb78e` | `clang-r416183b` | No published `abi.stg` |
| `android13-5.15` | 8 | `9e68cd9fcab748584755d31ba88ef134efc938dbde17f258c2652315f6cd81cd` | `clang-r450784e` | No published `abi.stg` |
| `android14-6.1` | 11 | `1dd6ac340b627a90a4031d6d0df6b129d8cc949b139fb56032c898f023d3d5d3` | `clang-r487747c` | No published `abi.stg` |
| `android15-6.6` | 8 | `51159bc935c75a282fc65bc87e02f16bd098d1cdf55dc558c4fdd0fcf7a132e2` | `clang-r510928` | No published `abi.stg` |
| `android16-6.12` | 6 | `fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee` | `clang-r536225` | `gki/aarch64/abi.stg` |
| `android17-6.18` | 5 | `fb8b66200bf402cf65a751060fc1aa29524b9fa8840feef16c7b196a4f3f0e6e` | `clang-r584948c` | `gki/aarch64/abi.stg` |

The generation number is the value the pinned source declares: 5.10, 5.15, 6.1 and 6.6 declare it in `build.config.common` (9, 8, 11 and 8), and 6.12 and 6.18 declare it in `build.config.constants` (6 and 5, the latter through its `bazel/constants.scl` symlink). The 5.10 image has no `build.config.constants` and no `CLANG_VERSION` value, so `scripts/ddk-targets.sh` supplies `clang-r416183b`; the build still refuses a compiler whose version line does not contain that revision. The 5.10, 5.15 and 6.6 digests come from the community manifest at `Shikochin/Droidspaces-LKM` `build/gki-targets.json` revision `8c14b35`. Their kernel versions are 5.10.252, 5.15.202 and 6.6.127.

The 6.18 image also contains an x86_64 ABI dump. Its prepared DDK output is arm64, so the canonical DDK lane does not build x86_64 modules. Use caller-supplied matching output for x86_64.

The 5.10, 5.15, 6.1 and 6.6 images have no published ABI dump. Admission therefore uses that image's `Module.symvers` and `System.map`. A module-layout CRC from that output does not establish compatibility with another kernel. The image and its compiler are build inputs, not a device-support claim. The same rule applies to the other targets: no target is device-qualified by this build tooling.

These rows identify pinned inputs. They do not record completed builds. A per-module build can report an admitted result for an individual module. Candidate packaging needs both modules for the same branch, generation, and architecture.

Retained records under `out/final6-510`, `out/final6-515`, `out/final6-61`, `out/final6-66`, `out/final6-612` and `out/final6-618` report complete accepted two-module sets for the six pinned targets on `aarch64`. Each set records its image digest and compiler, and the ABI hash where the image publishes one. Each release manifest labels the bundle `build-admission-and-source-candidate` and sets `device_qualified` to false. Their archives carry `provenance/<module>.ko.debug`, so the candidate modules had only debug sections stripped. The workspace inventory `artifacts/maos/2026-10-29-userspace-efvs-six-gki/package.sha256.json` records the packaged bytes. These records establish build and admission of the recorded candidate bytes against the recorded image inputs. They do not name a source commit. They do not establish module loading, runtime behavior, or device support.

Build one module:

```sh
OUT_DIR=out/build-matrix-6.12-dm sh scripts/build-ddk-lkms.sh android16-6.12 6 dm-thin-pool
```

Build the complete arm64 set for one pinned target:

```sh
OUT_DIR=out/build-matrix-5.10 sh scripts/build-ddk-lkms.sh android12-5.10 9
OUT_DIR=out/build-matrix-5.15 sh scripts/build-ddk-lkms.sh android13-5.15 8
OUT_DIR=out/build-matrix-6.1 sh scripts/build-ddk-lkms.sh android14-6.1 11
OUT_DIR=out/build-matrix-6.6 sh scripts/build-ddk-lkms.sh android15-6.6 8
OUT_DIR=out/build-matrix-6.12 sh scripts/build-ddk-lkms.sh android16-6.12 6
OUT_DIR=out/build-matrix-6.18 sh scripts/build-ddk-lkms.sh android17-6.18 5
```

The canonical lane runs Kbuild inside the selected image. The image has absolute source and output paths under `/opt/ddk`, so the script does not extract or copy the kernel tree. Docker pulls the pinned digest only when it is not present locally. The container has no privileged mode. It mounts only this repository at the same absolute path. It does not load a module or access a device. The lane records the image digest, compiler, and ABI hash in `OUT_DIR/ddk/kmi-ddk-<branch>-<generation>.json`.

The build needs Docker. The image supplies the compiler and matching kernel source and output. The DDK container runs with the invoking UID and GID and sets `HOME=/tmp`.

The canonical lane mounts only the repository, so both modules build from this checkout and the pinned image. The build does not clone or reuse any other repository.

The clang bootstrap extracts only the selected compiler files, not the kernel image or source tree:

```sh
OUT_DIR=out/build-matrix-6.18 sh scripts/bootstrap-ddk-clang.sh android17-6.18 5
```

The bootstrap accepts only targets in the pinned table. It records the image digest, compiler version, and executable hashes under `OUT_DIR/ddk/clang/`. `build-lkms.sh` reads `CLANG_VERSION` from the matching kernel source and refuses a compiler whose version line does not match it. `DDK_CLANG_DIR` can select a compiler directory, but the same version check still applies.

## Kernel-line ports

Both modules support the six pinned lines and keep the line interfaces out of the shared functional core. The 5.10 ports are real pre-rework adapters, not aliases: `part-projection` retains a `bdget_disk()` reference to the whole block device (a reference, not an opener), locks that device's `bd_mutex`, reads its `bd_openers`, treats `GENHD_FL_UP` as the dead flag, iterates partitions with `disk_part_iter_*`, and enables scanning through `GENHD_FL_EXT_DEVT` with `GENHD_FL_NO_PART_SCAN` cleared; `dm-thin-pool` declares its 5.10 metadata mode, status mapping, wait test, bioset allocator and kcopyd declaration. See the module provenance files for the source citations.

| Module | Per-line inputs | Shared core |
| --- | --- | --- |
| `dm-thin-pool` | `abi/<line>/port.py` applies the line's own source edits (bio, crypto, errno and status mapping). `abi/6.12/port.py` records the verified branch that selects the vendored tree. | `prepare.py` validation, staging, shared transformations, and provenance |
| `part-projection` | `abi/<line>/bdev.h` owns the open, close, handle type, read-only mechanism and open count. `abi/file-bdev.h` holds the file-based implementation that 6.12 and 6.18 share. | `configfs.c`, `target.c` |

`prepare.py` selects the port from the kernel line of the supplied source. `part-projection/bdev.h` selects the port from `LINUX_VERSION_CODE` of the build and stops with an error on a line that has no port. A line port is never used for a different line. `PROVENANCE.json` for `dm-thin-pool` and the `.modinfo` entry `part_projection_bdev_abi` name the port that produced a build.

## Output isolation and build selection

`OUT_DIR` must resolve to a directory inside this repository's ignored `out/` tree. The default is `out/build-matrix`. Use a fresh child for each build attempt to preserve existing outputs. Build scripts refuse existing set records, requested module directories, and compiler records rather than replace them.

The scripts stage each module under `OUT_DIR` before Kbuild. Unchanged module directories are copied to `OUT_DIR/module-src/`, with prior build objects excluded. When the module tree provides `prepare.py`, the prepared directory under `OUT_DIR/prepared/` is the build source. Kbuild and source preparation do not write into the checked-out module directories.

For caller-supplied exact source and output, use:

```sh
OUT_DIR=out/ack-android16-6.12 \
  sh scripts/build-lkms.sh android16-6.12 6 aarch64 \
  /path/to/matching/source /path/to/complete/output
```

The command accepts optional module names after the five required inputs:

```sh
OUT_DIR=out/ack-dm-thin \
  sh scripts/build-lkms.sh android16-6.12 6 aarch64 \
  /path/to/matching/source /path/to/complete/output dm-thin-pool
```

Supported architecture names are `aarch64` and `x86_64`. The output tree must contain `.config`, `Module.symvers`, `System.map`, and `include/generated/utsrelease.h`. Source identity must match the exact branch and generation. The source must declare one `CLANG_VERSION`. The selected compiler must match it. A private import requires `CONFIG_KALLSYMS_ALL=y` and presence in the target `System.map`.

Caller-supplied builds use `Module.symvers` unless `KMI_ABI` names the published ABI dump for the same branch, generation, and architecture. Do not use an ABI dump from another target. The pinned DDK lane selects its mapped ABI automatically when the image provides one.

A one-module request builds and admits that module. It writes `set.json` with `complete: false`. A full-set request builds `dm-thin-pool` and `part-projection`. The script continues after a module failure, records each result, and exits nonzero if any requested module fails. `complete` is true only when both modules have admitted final bytes. The manifest hashes the final `.ko` and its build metadata. The script does not strip or rewrite an admitted module unless `STRIP_DEBUG=1` is set.

`STRIP_DEBUG=1` runs the matching `llvm-strip --strip-debug` before final admission and hashing. It removes debug sections only. The original bytes remain in `<module>.ko.debug`, whose hash is recorded in the build metadata. The option refuses a module with a module-signature section or appended signature. The default is off.

Build outputs use these paths:

```text
OUT_DIR/modules/<branch>-<generation>/<arch>/<module>/<module>.ko
OUT_DIR/modules/<branch>-<generation>/<arch>/<module>/<module>.ko.build.json
OUT_DIR/modules/<branch>-<generation>/<arch>/set.json
```

The build metadata records the KMI, compiler version and hash, kernel-input hashes, module hash, imports, and `.modinfo` name and vermagic. For a staged module with `PROVENANCE.json`, it records that file's hash, profile, and kernel release. It also records canonical SHA-256 inventories for the staged module source, shared include, and build tools. The build verifies those inventories after compilation. `set.json` records completeness and final-byte hashes. These records do not prove successful runtime loading.

The source inventory is captured after the initial Kbuild clean and before compilation. Generated objects, logs, caches, `.git`, and build-output directories are excluded. A changed, added, deleted, or symlinked source input fails the build or release. Old build metadata without source evidence is refused by `package --release` and requires a rebuild.

## Build-only candidate bundle

The workflows create a candidate bundle only after the full build command succeeds. `scripts/module_set.py package` also checks that the set manifest lists both admitted modules, that each metadata record matches the exact module bytes and KMI, and that each record has compiler provenance. It refuses a partial set, an extra module, and an existing output directory.

To package a locally built complete set:

```sh
OUT_DIR=out/build-matrix-6.12
python3 scripts/module_set.py package \
  --directory "$OUT_DIR/modules/android16-6.12-6/aarch64" \
  --out "$OUT_DIR/release/android16-6.12-6/aarch64"
```

The package contains the exact final module bytes under `egysk/kmod/`, build metadata and any module `PROVENANCE.json` files under `provenance/`, plus `set.json` and `manifest.json`. When `STRIP_DEBUG=1` produced a `.ko.debug` file, the package also copies it under `provenance/` and records its hash. The candidate manifest records hashes for the module bytes, metadata, preparation provenance, and debug artifacts. The `egysk/kmod/` directory is an overlay for the existing maOS `--bootstrap EXACT_KMI=DIR` seed. It is not a complete seed. The product seed still supplies its own `egysk.toml`, module order, and module parameters.

The manifest labels the bundle `build-and-admission-only` and sets `device_qualified` to false. Workflows upload candidate artifacts. They do not publish GitHub releases or deploy artifacts.

## Source-and-binary candidate archive

Add `--release` to include corresponding module sources, licenses, notices, deterministic `SHA256SUMS`, and a deterministic `.tar.gz`:

```sh
OUT_DIR=out/build-matrix-6.12
python3 scripts/module_set.py package --release \
  --directory "$OUT_DIR/modules/android16-6.12-6/aarch64" \
  --out "$OUT_DIR/release/android16-6.12-6/aarch64"
```

The directory still contains the maOS `egysk/kmod/` overlay. It also contains `sources/`, `LICENSES/`, `SOURCE-NOTICE.md`, and `SHA256SUMS`. The archive is written beside the directory as `<name>.tar.gz`; its hash is written to `<name>.tar.gz.sha256`. Archive timestamps, owner fields, and ordering are fixed.

The source bundle uses `sources/kernel/<module>/`, with `sources/include/` and `sources/scripts/` for the shared header and build tools. `dm-thin-pool` sources come from its prepared tree, so the bundle carries the staged device-mapper sources and the per-line port scripts that produced them.

Release packaging requires those build-time inventories, verifies each staged source tree before copying, and verifies the copied tree against the same inventory. A source change, addition, deletion, or symlink refuses the archive.

All module sources in the archive are GPL-2.0-only. The archive copies the GPL v2 text to `LICENSES/GPL-2.0-only.txt`. The archive contains no other licensed component.

## Admission contract

The configured loader is `egysk/modules/lkm-loader`, a KernelSU `ksuinit` derivative. It prebinds undefined imports to addresses from the running kernel before `init_module`. Admission checks every import against the target ABI export list or `Module.symvers`, and then against `System.map` for private imports. Private imports need `CONFIG_KALLSYMS_ALL=y` for the loader's kallsyms resolver.

The kernel independently checks `module_layout`. A present version record must match the target ABI CRC when an ABI dump exists, or the target `Module.symvers` CRC when it does not. Admission does not compare CRCs for other imports because the loader prebinds them. An absent or empty version table is refused when the target sets `CONFIG_MODULE_FORCE_LOAD=y`.

Admission checks ELF type and architecture, normalized module name, vermagic flags, imports, and x86_64 relocation kinds. Successful compilation and admission do not prove that the module loads or behaves safely. Symbol lookup cannot repair a different data layout, CFI policy, signature policy, or KMI.

## Verification commands and limits

Run host contract checks:

```sh
python3 -m unittest scripts.test_kmi_modules scripts.test_module_set scripts.test_source_manifest
```

Run shell checks for the build entry points:

```sh
shellcheck scripts/build-lkms.sh scripts/build-ddk-lkms.sh \
  scripts/bootstrap-ddk-clang.sh scripts/ddk-targets.sh scripts/out-dir.sh \
  kernel/dm-thin-pool/build.sh
```

Run a pinned full arm64 build with one of the six branch-generation pairs in the table. Run a single-module command when only that module needs validation. The build needs the matching image or exact caller-supplied source and output and the selected clang.

To check a source-and-binary archive:

```sh
(cd out/build-matrix/release/android16-6.12-6/aarch64 && sha256sum --check SHA256SUMS)
sha256sum --check out/build-matrix/release/android16-6.12-6/aarch64.tar.gz.sha256
tar -tzf out/build-matrix/release/android16-6.12-6/aarch64.tar.gz | head
```

The candidate workflows set `STRIP_DEBUG=1` for their build step, so the modules they upload and package are stripped and each archive carries the original bytes in `provenance/<module>.ko.debug`. To reproduce that locally, set the same variable on a fresh `OUT_DIR`.

Set `STRIP_DEBUG=1` on a fresh build to strip debug sections before admission. Confirm the shipped `.ko` has no `.debug_*` sections, still has `.symtab`, relocations, and `.BTF` when the build produced BTF, and has a matching `provenance/<module>.ko.debug` hash. A signed module is refused rather than altered.

Host admission, image-based builds, and caller-supplied builds do not establish device boot, kernel acceptance on a phone, safe deployment, or physical-device qualification. Never load modules or write to a phone, physical disk, partition, or block device during build checks.

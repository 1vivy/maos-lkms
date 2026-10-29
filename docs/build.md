# Build and KMI admission

This document describes pinned build targets, caller-supplied builds, admission, and build-only candidate bundles. A successful build does not qualify a module for a device.

## Pinned DDK targets

`scripts/ddk-targets.sh` selects an image only for an exact branch and generation. The images use immutable digests:

| Branch | Generation | Image digest | Compiler | ABI dump |
| --- | ---: | --- | --- | --- |
| `android14-6.1` | 11 | `1dd6ac340b627a90a4031d6d0df6b129d8cc949b139fb56032c898f023d3d5d3` | `clang-r487747c` | No published `abi.stg` |
| `android16-6.12` | 6 | `fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee` | `clang-r536225` | `gki/aarch64/abi.stg` |
| `android17-6.18` | 5 | `fb8b66200bf402cf65a751060fc1aa29524b9fa8840feef16c7b196a4f3f0e6e` | `clang-r584948c` | `gki/aarch64/abi.stg` |

The 6.18 image also contains an x86_64 ABI dump. Its prepared DDK output is arm64, so the canonical DDK lane does not build x86_64 modules. Use caller-supplied matching output for x86_64.

The 6.1 image has no published ABI dump. Admission therefore uses that image's `Module.symvers` and `System.map`. A module-layout CRC from that output does not establish compatibility with another kernel. The image and its compiler are build inputs, not a device-support claim. The same rule applies to the other targets: no target is device-qualified by this build tooling.

These rows identify pinned inputs. They do not record completed builds. The 6.1 target does not currently have a complete module set for candidate packaging because `efivar_store` needs a backend adaptation and other module ports remain in progress. A per-module build may still report an admitted result for an individual module.

Build one module or the complete arm64 set:

```sh
OUT_DIR=out/build-matrix-6.12-dm sh scripts/build-ddk-lkms.sh android16-6.12 6 dm-thin-pool
OUT_DIR=out/build-matrix-6.12 sh scripts/build-ddk-lkms.sh android16-6.12 6
OUT_DIR=out/build-matrix-6.1 sh scripts/build-ddk-lkms.sh android14-6.1 11
OUT_DIR=out/build-matrix-6.18 sh scripts/build-ddk-lkms.sh android17-6.18 5
```

The canonical lane runs Kbuild inside the selected image. The image has absolute source and output paths under `/opt/ddk`, so the script does not extract or copy the kernel tree. Docker pulls the pinned digest only when it is not present locally. The container has no privileged mode. It mounts the repository and the configured Cargo and Rustup homes. It does not load a module or access a device. The lane records the image digest, compiler, and ABI hash in `OUT_DIR/ddk/kmi-ddk-<branch>-<generation>.json`.

The build needs Docker and pinned Rust `nightly-2026-08-08` with `rust-src` for `efivar_store`. `CARGO_HOME` and `RUSTUP_HOME` may select other installed toolchain directories. The DDK container runs with the invoking UID and GID, mounts those directories at `/cargo` and `/rustup`, sets `HOME=/tmp`, and uses `/cargo/bin/cargo` and `/cargo/bin/rustc`. The image supplies the compiler and matching kernel source and output.

`EFIVAR_STORE_REPO` may name the local `efivar-store` checkout. The DDK lane bind-mounts that checkout read-only at `/opt/maos/efivar-store` and passes the stable path to the build. The caller-supplied lane uses the local checkout directly. A reused checkout must be at the pinned `SOURCE_REVISION` with no tracked or untracked modifications; the build does not fetch or check out another revision in that tree. The standalone efivar_store Kbuild uses a small writable copy under `OUT_DIR/sources/`. A non-local `EFIVAR_STORE_REPO` URL is passed through and materialized under `OUT_DIR/sources/`. The build sets `EFVS_RUSTC` from the selected Cargo directory, so a kernel Kbuild cache cannot redirect it to `./rustc`.

The clang bootstrap extracts only the selected compiler files, not the kernel image or source tree:

```sh
OUT_DIR=out/build-matrix-6.18 sh scripts/bootstrap-ddk-clang.sh android17-6.18 5
```

The bootstrap accepts only targets in the pinned table. It records the image digest, compiler version, and executable hashes under `OUT_DIR/ddk/clang/`. `build-lkms.sh` reads `CLANG_VERSION` from the matching kernel source and refuses a compiler whose version line does not match it. `DDK_CLANG_DIR` can select a compiler directory, but the same version check still applies.

## Output isolation and build selection

`OUT_DIR` must resolve to a directory inside this repository's ignored `out/` tree. The default is `out/build-matrix`. Use a fresh child for each build attempt to preserve existing outputs. Build scripts refuse existing set records, requested module directories, and compiler records rather than replace them.

The scripts stage each module under `OUT_DIR` before Kbuild. Unchanged module directories are copied to `OUT_DIR/module-src/`, with prior build objects and the EFVS source checkout excluded. `efivar_store` materializes its pinned source under `OUT_DIR/sources/efivar_store/`. When the module tree provides `prepare.py`, the prepared directory under `OUT_DIR/prepared/` is the build source. Kbuild and source preparation do not write into the checked-out module directories.

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

A one-module request builds and admits that module. It writes `set.json` with `complete: false`. A full-set request builds `dm-thin-pool`, `part-projection`, `efivarfs`, and `efivar_store`. The standalone `efivar_store` build follows only after all four product modules succeed. The script continues after a module failure, records each result, and exits nonzero if any requested module fails. `complete` is true only when all four modules have admitted final bytes. The manifest hashes the final `.ko` and its build metadata. The script does not strip or rewrite an admitted module unless `STRIP_DEBUG=1` is set.

`STRIP_DEBUG=1` runs the matching `llvm-strip --strip-debug` before final admission and hashing. It removes debug sections only. The original bytes remain in `<module>.ko.debug`, whose hash is recorded in the build metadata. The option refuses a module with a module-signature section or appended signature. The default is off.

Build outputs use these paths:

```text
OUT_DIR/modules/<branch>-<generation>/<arch>/<module>/<module>.ko
OUT_DIR/modules/<branch>-<generation>/<arch>/<module>/<module>.ko.build.json
OUT_DIR/modules/<branch>-<generation>/<arch>/set.json
OUT_DIR/standalone/<branch>-<generation>/<arch>/efivar_store/  # full-set command
```

The build metadata records the KMI, source revision when pinned, compiler version and hash, kernel-input hashes, module hash, imports, and `.modinfo` name and vermagic. For a staged module with `PROVENANCE.json`, it records that file's hash, profile, and kernel release. It also records canonical SHA-256 inventories for the staged module source, shared include, build tools, and, for `efivar_store`, the EFVS source. The build verifies those inventories after compilation. `set.json` records completeness and final-byte hashes. These records do not prove successful runtime loading.

The source inventory is captured after the initial Kbuild clean and before compilation. Generated objects, logs, caches, `.git`, and build-output directories are excluded. A changed, added, deleted, or symlinked source input fails the build or release. Old build metadata without source evidence is refused by `package --release` and requires a rebuild. The standalone `efivar_store` lane records the materialized checkout root, not the wrapper directory, as its EFVS source evidence.

## Build-only candidate bundle

The workflows create a candidate bundle only after the full build command succeeds. `scripts/module_set.py package` also checks that the set manifest lists all four admitted modules, that each metadata record matches the exact module bytes and KMI, and that each record has compiler provenance. It refuses a partial set and an existing output directory.

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

The source bundle uses `sources/kernel/<module>/`, with `sources/include/` and `sources/scripts/` for the shared header and build tools. The pinned EFVS engine is under `sources/efivar-store-engine/`, linked from `sources/kernel/efivar_store/.source`. `EFIVAR_STORE_REPO` selects a local engine checkout. Without it, the package uses `OUT_DIR/sources/efivar_store` or its standalone staging copy.

Release packaging requires those build-time inventories, verifies each staged source tree before copying, and verifies the copied tree against the same inventory. A source change, addition, deletion, symlink, or wrong EFVS revision refuses the archive.

**License gap:** `efivar_store` combines GPL-2.0-only kernel wrapper code with the Apache-2.0 EFVS engine. The archive records this combination for review. It does not claim that distribution compatibility is cleared. Do not publish it as a product release until that review, source-offer obligations, and the exact target qualification are resolved.

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

Run a pinned full arm64 build with one of the three branch-generation pairs in the table. Run a single-module command when only that module needs validation. The build needs the matching image or exact caller-supplied source and output, the selected clang, and the pinned Rust toolchain for `efivar_store`.

To check a source-and-binary archive:

```sh
(cd out/build-matrix/release/android16-6.12-6/aarch64 && sha256sum --check SHA256SUMS)
sha256sum --check out/build-matrix/release/android16-6.12-6/aarch64.tar.gz.sha256
tar -tzf out/build-matrix/release/android16-6.12-6/aarch64.tar.gz | head
```

Set `STRIP_DEBUG=1` on a fresh build to strip debug sections before admission. Confirm the shipped `.ko` has no `.debug_*` sections, still has `.symtab`, relocations, and `.BTF` when the build produced BTF, and has a matching `provenance/<module>.ko.debug` hash. A signed module is refused rather than altered.

Host admission, image-based builds, and caller-supplied builds do not establish device boot, kernel acceptance on a phone, safe deployment, or physical-device qualification. Never load modules or write to a phone, physical disk, partition, or block device during build checks.

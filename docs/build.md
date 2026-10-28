# Build and KMI admission

This document records supported build inputs, commands, and admission rules.

## Build and admit arm64 modules (the canonical lane)

The canonical arm64 lane builds against a digest-pinned DDK image.
KernelSU's CI uses the same image family for its GKI modules.
See the pinned [`ddk-lkm.yml`](https://github.com/tiann/KernelSU/blob/10efe6648aa52e0497bbd686f940832ad05848cf/.github/workflows/ddk-lkm.yml) reference.
This arm64 lane requires no caller-supplied kernel source or output:

```sh
sh scripts/build-ddk-lkms.sh android16-6.12 6
```

The build requires Docker and pinned `nightly-2026-08-08` with `rust-src` for the freestanding store engine.
The default Cargo and Rustup homes are `~/.cargo` and `~/.rustup`.
`CARGO_HOME` and `RUSTUP_HOME` may select other paths.

The script pulls this image by digest if it is absent:
`ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee`.
It runs the entire build inside that container.
The image's `/opt/ddk/kdir/<branch>` output contains an absolute `source` symlink and an absolute-path Makefile.
Both reference `/opt/ddk/src/<branch>`.
An extracted copy on the host is therefore not relocatable.

The script bind-mounts the host's pinned Cargo and Rustup homes into the container.
The container's clang and Kbuild use the host's Rust toolchain to build the artifact.
`scripts/kmi_modules.py` admits every module against the image's published KMI ABI and its `Module.symvers` and `System.map`.
The ABI path is `gki/aarch64/abi.stg`.
The script records the image digest and ABI dump SHA-256 in `out/ddk/kmi-ddk-<branch>-<generation>.json`.
The pinned digest contains only `android16-6.12` generation `6`.
Another branch requires another image digest here and in `scripts/build-ddk-lkms.sh`.

Admission does not require matching `Module.symvers` CRCs.
The product loader is `egysk/modules/lkm-loader`, a KernelSU `ksuinit` derivative.
See the pinned upstream [`lib.rs`](https://github.com/tiann/KernelSU/blob/10efe6648aa52e0497bbd686f940832ad05848cf/userspace/ksuinit/src/lib.rs).
The loader prebinds every undefined symbol to its running-kernel address (`SHN_ABS`) before `init_module`.
The kernel therefore does not evaluate most version records.

Each undefined symbol must appear in the target KMI exports or the target `System.map`.
The exports come from `gki/aarch64/abi.stg` or the supplied `Module.symvers`.
Private imports through `System.map` require `CONFIG_KALLSYMS_ALL=y` for the loader's kallsyms resolver.
The kernel independently checks `module_layout` through `check_modstruct_version`.
A present version record for that symbol must match the target KMI's published CRC.

The image's patched `scripts/mod/modpost.c` disables export checking and emits an empty `__versions` table.
An absent or empty table loads with a taint warning when the target does not set `CONFIG_MODULE_FORCE_LOAD`.
The pinned image's `.config` uses this GKI default.
A nonempty `module_layout` record with a wrong CRC causes the kernel to refuse the module.

The pinned image's `gki/aarch64/abi.stg` can lag the branch tip.
It omits some exports from the image's own build:
`dm_disk`, `dm_get_md`, `dm_put`, `configfs_depend_item_unlocked`, and `configfs_undepend_item`.
Admission accepts these as private imports through the image's `System.map` and `CONFIG_KALLSYMS_ALL=y`.
The caller-supplied lane uses the same private-import path.

## Build and admit exact artifacts (caller-supplied source/output)

This lane builds x86_64 Cuttlefish modules.
It also builds arm64 modules against caller-owned exact kernel output instead of the pinned DDK image.
Supply the complete matching ACK/GKI source and output.
Kernel headers alone are insufficient.

The build needs these inputs:

1. A prepared ACK source tree. It must contain a readable `Makefile`.
2. The complete matching kernel output tree. It must contain `.config`, `Module.symvers`, `System.map` and `include/generated/utsrelease.h`.
3. The pinned DDK clang `clang-r536225`, extracted by this repository's bootstrap. The host `PATH` LLVM is not used.
4. The pinned `nightly-2026-08-08` Rust toolchain with `rust-src`, for the freestanding store engine.

The compiler is a repository-owned input, not the host one:

```sh
sh scripts/bootstrap-ddk-clang.sh
```

The bootstrap pulls `ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee` by digest.
It copies `clang-r536225` into ignored `out/ddk/clang/` and checks the reported version.
It compiles one file for each architecture.
It records the image digest, version line, and `clang` and `ld.lld` SHA-256 values in `out/ddk/clang/ddk-clang.json`.

`DDK_CLANG_DIR` may name another clang `bin` directory.
Without either compiler location, `scripts/build-lkms.sh` exits with status 2 and names the bootstrap.
The script removes `CROSS_COMPILE` so Kbuild derives the target from `ARCH` for both architectures.

Supported architecture names are `aarch64` and `x86_64`.
When an input is absent or incomplete, the script exits with status 2 and names the missing input.
It does not synthesize CRCs.
Optional `KMI_ABI` names a `gki/<arch>/abi.stg` dump.
The script passes that dump to every build and verification call.
It widens the admitted export/symbol list and supplies the `module_layout` CRC instead of `Module.symvers`.

This lane runs on the prepared self-hosted `egysk-kmi` runner.
It supports x86_64 Cuttlefish and arm64 builds with caller-supplied exact output.
An empty hosted runner cannot provide caller-owned complete outputs.

```sh
python3 -m unittest scripts.test_kmi_modules
sh scripts/build-lkms.sh android16-6.12 6 aarch64 \
    /path/to/source /path/to/complete-output
```

The gate builds all four projects and the pinned standalone source Kbuild. It then admits the exact shipped bytes against the supplied kernel output. All module output stays in the ignored `out/` tree:

```text
out/modules/<branch>-<generation>/<arch>/
  dm-thin-pool/dm-thin-pool.ko
  dm-thin-pool/dm-thin-pool.ko.build.json
  part-projection/part-projection.ko
  part-projection/part-projection.ko.build.json
  efivarfs/efivarfs.ko
  efivarfs/efivarfs.ko.build.json
  efivar_store/efivar_store.ko
  efivar_store/efivar_store.ko.build.json
out/standalone/<branch>-<generation>/<arch>/efivar_store/
  efivar_store.ko
  efivar_store.ko.build.json
out/linux-cargo/<Rust target>/release/
  libefivar_store_ffi.a
```

Each run replaces its own `out/` subtrees.
Kernels before 6.13 lack `MO=`, so compilation writes the module into its source directory.
The gate moves the shipped `.ko` into `out/` and removes intermediates.
The source tree therefore retains no build artifact.

Both store lanes share the engine archive in `out/linux-cargo/<Rust target>/release/`.
The gate exports `EFVS_CARGO_TARGET_DIR`.
That variable selects the archive's output directory.

For one project, pass an output directory. Without `--output-dir`, the module file stays in the module directory:

```sh
python3 scripts/kmi_modules.py build \
    --module-dir kernel/part-projection --module part-projection \
    --branch android16-6.12 --generation 6 --arch aarch64 \
    --kmi-src /path/to/source --kmi-out /path/to/complete-output \
    --output-dir out/modules/android16-6.12-6/aarch64/part-projection
```

Admission checks the ELF type and architecture. It checks the normalized module name and vermagic flags. It checks every import against the target KMI export list or `System.map`. A private import requires `CONFIG_KALLSYMS_ALL=y`. On x86_64, admission also checks loaded relocation kinds.

The kernel checks `module_layout` itself. A present version record for that symbol must match the target's published CRC. Admission does not compare CRCs for other imports. The loader prebinds other imports before `init_module`. Admission runs from the module plus `--kmi-out` and, on the canonical lane, `--kmi-abi`. It persists no state.

`just verify` and `scripts/build-lkms.sh` admit the exact shipped bytes. Each build writes `<module>.ko.build.json` beside the artifact. The file records the KMI branch and generation, pinned source revision, module hash, kernel-input hashes, imports, and `.modinfo` name and vermagic. Kernel-input hashes cover `Module.symvers`, `System.map`, `utsrelease.h`, and the ABI dump when supplied. The file is descriptive output. No consumer reads it, and no payload or seed includes it.

Private vmlinux imports require a compatible loader or suitable exports. Successful compilation alone does not guarantee module loading. Never strip or rewrite admitted bytes. Symbol lookup cannot repair a different layout, CFI scheme, signature policy, or KMI.

`efivar_store` materializes the revision in [`SOURCE_REVISION`](../kernel/efivar_store/SOURCE_REVISION). It checks that HEAD matches the pin and rejects tracked changes. `EFIVAR_STORE_REPO` may select a local clone of that revision. Its freestanding engine uses pinned `nightly-2026-08-08` and locked dependencies. It does not require `CONFIG_RUST`. The module Kbuild sets `EFVS_ROOT` and includes the pinned `linux/Kbuild`. That source owns the module rules, C glue, and engine build. Its `dkms.conf` does not autoload the module. Private imports still need exports or caller-owned prebinding.

CI host checks run on pushes and pull requests.
`ddk-lkm.yml` runs the canonical digest-pinned arm64 lane without caller inputs.
`build-lkm.yml` runs the caller-supplied lane for both architectures through `workflow_dispatch`.
Workflows upload artifacts, but do not deploy or publish releases.

Dependabot updates GitHub Actions only.
This repository has no root Cargo workspace.
The EFI engine's locked Rust dependencies belong to its pinned source revision, not a root-level Cargo updater.

## Verification boundary

The host contract tests exercise ELF parsing, module identity, and build-info handling. The canonical build command is `sh scripts/build-ddk-lkms.sh android16-6.12 6`. It requires Docker and the pinned Rust nightly with `rust-src` under the configured Cargo and Rustup homes. The script pulls the digest-pinned image if it is absent. Cached clang and KMI files under `out/ddk/` do not replace the image's in-container source and output trees.

The caller-supplied build command is `sh scripts/build-lkms.sh <branch> <generation> <aarch64|x86_64> <kernel-source> <complete-kernel-output>`. It requires matching prepared source and output trees, the pinned clang from `sh scripts/bootstrap-ddk-clang.sh` or `DDK_CLANG_DIR`, and the pinned Rust nightly with `rust-src`. The complete output contains `.config`, `Module.symvers`, `System.map`, and `include/generated/utsrelease.h`. Run `python3 -m unittest scripts.test_kmi_modules` for host contract tests.

Admission checks ELF architecture, module identity, vermagic flags, and every undefined import against the target KMI exports or `System.map`.
A private import requires `CONFIG_KALLSYMS_ALL=y`.
Admission checks a present `module_layout` version record against the published KMI CRC.
It does not require matching CRCs for other imports.
Admission rejects empty or absent version records when the target sets `CONFIG_MODULE_FORCE_LOAD=y`.
The configured loader prebinds imported symbols before `init_module`.
Admission alone does not prove successful runtime loading.

Repository-local generated outputs and cached inputs reside under ignored `out/`. The current workspace contains a clang bootstrap record and cached ABI/symbol files. These files do not establish that the canonical container image or a caller-owned matching kernel tree is available.

QEMU, host, and build results apply only to their recorded inputs and exercised behavior. They do not establish phone boot, enforcing policy acceptance, safe deployment, or physical-device qualification. Do not load modules or write to a phone or block device as part of documentation or build work.


# Build and KMI admission

This document records supported build inputs, commands, and admission rules.

## Build and admit arm64 modules (the canonical lane)

The canonical arm64 lane builds against the digest-pinned DDK image the way
KernelSU's CI builds its GKI modules against the same image family (reference:
[`tiann/KernelSU` `ddk-lkm.yml`](https://github.com/tiann/KernelSU/blob/10efe6648aa52e0497bbd686f940832ad05848cf/.github/workflows/ddk-lkm.yml)).
No caller-supplied kernel source or output is required for arm64:

```sh
sh scripts/build-ddk-lkms.sh android16-6.12 6
```

This needs docker and a pinned `nightly-2026-08-08` Rust toolchain with
`rust-src` at `~/.cargo`/`~/.rustup` (`CARGO_HOME`/`RUSTUP_HOME` may point
elsewhere), for the freestanding store engine. It pulls
`ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee`
by digest if absent, then runs the whole build *inside* that container: the
image's `/opt/ddk/kdir/<branch>` kbuild output has an absolute `source`
symlink and an absolute-path Makefile into `/opt/ddk/src/<branch>`, so an
extracted copy on the host would not be relocatable. The host's pinned
cargo/rustup are bind-mounted in so the container's clang/kbuild and the
host's Rust toolchain build the same artifact. `scripts/kmi_modules.py` admits
every built module against that same image's published KMI ABI
(`gki/aarch64/abi.stg`) and its own `Module.symvers`/`System.map`, and records
the image digest plus the ABI dump's sha256 in
`out/ddk/kmi-ddk-<branch>-<generation>.json`. The pinned digest holds one
branch (`android16-6.12` generation `6`); another branch requires pinning
another image digest here and in `scripts/build-ddk-lkms.sh`.

Admission does not require `Module.symvers` CRCs to match. The product's
loader (`egysk/modules/lkm-loader`, a KernelSU `ksuinit` derivative: see
[`lib.rs`](https://github.com/tiann/KernelSU/blob/10efe6648aa52e0497bbd686f940832ad05848cf/userspace/ksuinit/src/lib.rs))
prebinds every undefined symbol to its running-kernel address (`SHN_ABS`)
before `init_module`, so the kernel never evaluates most version records.
Admission instead checks that every undefined symbol is exported by the
target KMI (`gki/aarch64/abi.stg`'s symbols, or the supplied
`Module.symvers`) or present in the target `System.map` on a kernel that
makes every symbol visible to the loader's kallsyms resolver
(`CONFIG_KALLSYMS_ALL=y`). The one exception is `module_layout`: the kernel
checks that one itself (`check_modstruct_version`), independent of
prebinding, so a present record for it must match the target KMI's published
CRC. The DDK image's patched `scripts/mod/modpost.c` disables export
checking and ships an empty `__versions` for exactly this reason: an absent
or empty `__versions` table loads with a taint warning on a target that does
not set `CONFIG_MODULE_FORCE_LOAD` (the GKI default, confirmed in the pinned
image's own `.config`), while a nonempty, wrong-CRC `module_layout` record
would make the kernel refuse the module outright.

The pinned image's `gki/aarch64/abi.stg` can lag the branch tip: against it,
some real exports of the image's own build (for example `dm_disk`,
`dm_get_md`, `dm_put`, `configfs_depend_item_unlocked`,
`configfs_undepend_item`) are absent. Admission still accepts them as private
imports through the image's own `System.map`/`CONFIG_KALLSYMS_ALL=y`, the
same path a caller-supplied exact output already used for such imports.

## Build and admit exact artifacts (caller-supplied source/output)

x86_64 Cuttlefish modules, and any arm64 build against a caller-owned exact
kernel output instead of the pinned DDK image, use this lane. Supply the
complete matching ACK/GKI source and output; kernel headers alone are not
sufficient.

The build needs these inputs:

1. A prepared ACK source tree. It must contain a readable `Makefile`.
2. The complete matching kernel output tree. It must contain `.config`, `Module.symvers`, `System.map` and `include/generated/utsrelease.h`.
3. The pinned DDK clang `clang-r536225`, extracted by this repository's bootstrap. The host `PATH` LLVM is not used.
4. The pinned `nightly-2026-08-08` Rust toolchain with `rust-src`, for the freestanding store engine.

The compiler is a repository-owned input, not the host one:

```sh
sh scripts/bootstrap-ddk-clang.sh
```

The bootstrap pulls `ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee`
by digest, copies `clang-r536225` into the ignored `out/ddk/clang/` tree, checks the reported version, compiles one file for each architecture, and records the image digest, the version line and the `clang`/`ld.lld` sha256 in `out/ddk/clang/ddk-clang.json`. `DDK_CLANG_DIR` may name another clang `bin` directory. Without either, `scripts/build-lkms.sh` exits with status 2 and names the bootstrap. `scripts/build-lkms.sh` also drops `CROSS_COMPILE`, so kbuild derives the target from `ARCH` for both legs.

Supported architecture names are `aarch64` and `x86_64`. When an input is absent or incomplete, the script exits with status 2 and names the missing input. It does not synthesize CRCs. An optional `KMI_ABI` environment variable names a `gki/<arch>/abi.stg` KMI ABI dump; `scripts/build-lkms.sh` passes it through to every build/verify call, widening the admitted export/symbol list and anchoring the `module_layout` CRC to that dump instead of the supplied `Module.symvers`.

This lane runs on the prepared self-hosted `egysk-kmi` runner (x86_64 Cuttlefish always; arm64 when the caller supplies its own exact output instead of using the canonical DDK lane above). A hosted empty runner cannot provide caller-owned complete outputs.

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

Each run replaces its own `out/` subtrees. Kernels before 6.13 have no `MO=`, so a build writes the module into the module directory; the gate moves the shipped `.ko` into `out/` and then cleans the intermediates, so the source tree keeps no build artifact. The store engine archive compiles in `out/linux-cargo/<Rust target>/release/` and both store lanes share it; the gate exports `EFVS_CARGO_TARGET_DIR` and that variable selects another directory.

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

CI host checks run on pushes/PRs. `ddk-lkm.yml` runs the canonical digest-pinned arm64 lane with no caller inputs; `build-lkm.yml` runs the caller-supplied-source/output lane for both architectures on `workflow_dispatch`. Workflows upload artifacts, not deploy or publish releases.

Dependabot updates GitHub Actions only. This repository has no root Cargo
workspace; the EFI engine's locked Rust dependencies belong to its pinned source
revision, not an inherited root-level Cargo updater.

## Verification boundary

The host contract tests exercise ELF parsing, module identity, and build-info handling. The canonical build command is `sh scripts/build-ddk-lkms.sh android16-6.12 6`. It requires Docker and the pinned Rust nightly with `rust-src` under the configured Cargo and Rustup homes. The script pulls the digest-pinned image if it is absent. Cached clang and KMI files under `out/ddk/` do not replace the image's in-container source and output trees.

The caller-supplied build command is `sh scripts/build-lkms.sh <branch> <generation> <aarch64|x86_64> <kernel-source> <complete-kernel-output>`. It requires matching prepared source and output trees, the pinned clang from `sh scripts/bootstrap-ddk-clang.sh` or `DDK_CLANG_DIR`, and the pinned Rust nightly with `rust-src`. The complete output contains `.config`, `Module.symvers`, `System.map`, and `include/generated/utsrelease.h`. Run `python3 -m unittest scripts.test_kmi_modules` for host contract tests.

Admission checks ELF architecture and module identity, vermagic flags, and every undefined import against the target's KMI exports or `System.map`. A private import requires `CONFIG_KALLSYMS_ALL=y`. Admission checks a present `module_layout` version record against the published KMI CRC. It does not require matching CRCs for other imports. Empty or absent version records are rejected when the target sets `CONFIG_MODULE_FORCE_LOAD=y`. The configured loader prebinds imported symbols before `init_module`; admission alone does not prove that runtime loading succeeds.

Repository-local generated outputs and cached inputs reside under ignored `out/`. The current workspace contains a clang bootstrap record and cached ABI/symbol files. These files do not establish that the canonical container image or a caller-owned matching kernel tree is available.

QEMU, host, and build results apply only to their recorded inputs and exercised behavior. They do not establish phone boot, enforcing policy acceptance, safe deployment, or physical-device qualification. Do not load modules or write to a phone or block device as part of documentation or build work.


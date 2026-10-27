# maos-lkms

**Status (2026-10-12)** — Independent exact-KMI modules; projection uses ABI6.

Independent Linux modules, colocated for source and release management. No module depends on the Egysk helper, daemon, credential provider or root runtime. The preserved `legacy/esu-pre-magisk-20261009` tag records the pre-split tree; history is not rewritten.

| Project | Artifact / internal name | Interface |
| --- | --- | --- |
| [`dm-thin-pool`](kernel/dm-thin-pool/) | `dm-thin-pool.ko` / `dm_thin_pool` | Device-mapper thin-pool/thin targets; owned fork, private symbol renames and existing target behavior |
| [`part-projection`](kernel/part-projection/) | `part-projection.ko` / `part_projection` | Configfs ABI 6, named DM disks and pp-range/pp-meta/pp-hole at `/config/part-projection` |
| [`efivarfs`](kernel/efivarfs/) | `efivarfs.ko` / `efivarfs` | Upstream efivarfs plus the project-GUID patch |
| [`efivar_store`](kernel/efivar_store/) | `efivar_store.ko` / `efivar_store` | Block-backed EFI variable service; pinned Rust EFVS engine behind C glue |

Each directory has its own Kbuild/Makefile and provenance. Shared code is limited to [`include/egysk_lkm.h`](include/egysk_lkm.h): descriptive `egysk_*` name/version/ABI/criticality metadata and applicable readiness parameters. Metadata is not authorization. The core product owns rdinit and its ELF prebinding loader; the modules product owns `ppconf`, platform/storage helpers, Android lifecycle scripts and packaging.

## Build and admit exact artifacts

Supply the complete matching ACK source and output. Kernel headers alone are not sufficient.

The build needs these inputs:

1. A prepared ACK source tree. It must contain a readable `Makefile`.
2. The complete matching kernel output tree. It must contain `.config`, `Module.symvers`, `System.map` and `include/generated/utsrelease.h`.
3. The matching LLVM toolchain, through `PATH`.
4. The pinned `nightly-2026-08-08` Rust toolchain with `rust-src`, for the freestanding store engine.

Supported architecture names are `aarch64` and `x86_64`. When an input is absent or incomplete, the script exits with status 2 and names the missing input. It does not synthesize CRCs and does not skip exact admission.

Both real-build lanes run on the prepared self-hosted `egysk-kmi` runner. A hosted empty runner cannot provide caller-owned complete outputs. The DDK container lane binds each caller-supplied absolute path (`kmi_src`, `aarch64_out`, `x86_64_out`) into the job container at the identical path. Nothing is copied or synthesized inside the image, and an unbound path is absent there. ddk-min exports an arm64 `CROSS_COMPILE`, and kbuild turns that value into a `--target=` that contradicts the x86_64 leg. The workflow unsets it and lets kbuild derive the target from `ARCH`.

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

Each run replaces its own `out/` subtrees. The gate writes no artifact into a source directory and copies none from one. The store engine archive compiles in `out/linux-cargo/<Rust target>/release/`; `EFVS_CARGO_TARGET_DIR` selects another directory.

For one project, pass an output directory. Without `--output-dir`, the module file stays in the module directory:

```sh
python3 scripts/kmi_modules.py build \
    --module-dir kernel/part-projection --module part-projection \
    --branch android16-6.12 --generation 6 --arch aarch64 \
    --kmi-src /path/to/source --kmi-out /path/to/complete-output \
    --output-dir out/modules/android16-6.12-6/aarch64/part-projection
```

Admission checks ELF type/architecture, normalized internal module name, vermagic flags, exported CRCs and private imports against the supplied kernel map. It runs at build time from the module plus `--kmi-out` alone and persists nothing. `just verify` and `scripts/build-lkms.sh` re-run it on the exact shipped bytes. Each build also writes `<module>.ko.build.json` beside the artifact: the KMI branch/generation, the pinned source revision, the module hash, the kernel-input hashes (`Module.symvers`, `System.map`, `utsrelease.h`) keyed by basename, the private imports the loader must resolve and the `.modinfo` name/vermagic. That file is descriptive release output only — no consumer reads or re-checks it, and it is never packaged into a payload or seed. Private vmlinux imports require a compatible loader or suitable exports; successful compilation alone is not a loading guarantee. Never strip or rewrite admitted bytes afterward. A different layout, CFI scheme, signature policy or KMI cannot be repaired by symbol lookup.

`efivar_store` materializes exactly [`SOURCE_REVISION`](kernel/efivar_store/SOURCE_REVISION). `EFIVAR_STORE_REPO` may select a local repository containing that same commit; it does not change the pin. Its freestanding engine uses pinned `nightly-2026-08-08` with rust-src and locked dependencies; `CONFIG_RUST` is not required. The upstream source also ships standalone `linux/Kbuild` and non-autoloading `dkms.conf`; private imports still need exports or caller-owned prebinding.

CI host checks run on pushes/PRs. ACK and DDK gates require explicit complete prepared inputs and build both architectures. Incomplete header-only DDK images are rejected. Workflows upload artifacts, not deploy or publish releases.

Dependabot updates GitHub Actions only. This repository has no root Cargo
workspace; the EFI engine's locked Rust dependencies belong to its pinned source
revision, not an inherited root-level Cargo updater.

## Runtime contracts

Part projection exposes root `abi/state/commit/reset`, shared
`endpoints/NAME/{dev,hide,writable}` and per-disk
`disks/NAME/{dev,anchor,metadata}` under `/config/part-projection`. ABI6 preserves
512/1024/2048/4096-byte geometry independently for every disk; DM units stay 512
bytes. `pp-meta NAME OFFSET` freezes target-owned GPT snapshots. Shared commit
pins participants, validates every disk and anchor, owns physical hiding/sealing,
and enables partition scanning only after all moves succeed. Partial move
failure retains ownership until every mapping is ordinarily removed. Reset
refuses any live/registered/open publication, even after another disk was
removed. Userspace rereads each GPT. See the project ABI documentation.

Mount filesystem type `efivarfs` at `/sys/firmware/efi/efivars`. Mount/read success, not directory presence, establishes frontend readiness. The backend accepts mutually exclusive `partuuid=<unique-GPT-UUID>` or `dev=<major>:<minor>`, or the existing `/chosen/efivar-store,partuuid` DT property. No label or fixed unique GUID substitutes for that selector. Linux refuses blank stores without writing; firmware owns initialization and compaction.

Backing-file reads, writes, fsync and final fput run under the retained file opener credentials via `override_creds`/`revert_creds`. Load before Android policy, and permit the opener domain to access that block device. No `esp` credential or provider ABI is involved. EFI sysfs cleanup removes only objects the backend created, never a native EFI tree.

## Verification boundary

The historical build/runtime records below describe earlier source revisions.
ABI5 separately passed exact gen6 admission on both architectures and an
integrated permissive phone boot with stock init mounting projected `/metadata`
and encrypted `/data`. Anchored seal/reload/teardown and enforcing operation
remain separate qualifications.

The current arm64 `android16-6.12-6` builds passed exact artifact admission. The standalone backend and frontend additionally passed the QEMU immediate-read/update/delete/reboot/compaction/torn-tail/blank-refusal gate. That VM has no enforcing Android policy: it does not prove HAL-domain access, PIN unlock, native EFI replacement, or phone boot. The full platform/OTA and enforcing-device gates remain separate from these source/build checks.

Both architectures were also built and admitted inside the dated `ghcr.io/ylarod/ddk-min:android16-6.12-20260828` container (digest `sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee`): all four projects and the pinned standalone `linux/Kbuild` path, against the caller-supplied complete outputs bound into the container. Two independent runs produced byte-identical modules, and every per-module build record matched the shipped artifact bytes and kernel-input digests. That run loaded no module and touched no device, so it proves compilation and admission only. The arm64 lane recorded `warning: the compiler differs from the one used to build the kernel` (image clang build `14043575` versus the `12833971` that built the supplied arm64 output); the x86_64 Cuttlefish output carries a recorded stock `module_layout` CRC adjustment, so it is an admitted build against that supplied output, not a fully source-qualified self-built kernel.

Retain the per-project licenses and provenance. Root-level inherited tooling remains covered by [`LICENSE`](LICENSE); kernel projects carry their own license declarations.

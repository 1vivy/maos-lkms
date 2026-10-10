# KernelSU ESP LKMs

Independent Linux modules, colocated for source and release management. No module depends on the KernelSU ESP helper, daemon, credential provider or root runtime. The preserved `legacy/esu-pre-magisk-20261009` tag records the pre-split tree; history is not rewritten.

| Project | Artifact / internal name | Interface |
| --- | --- | --- |
| [`dm-thin-pool`](kernel/dm-thin-pool/) | `dm-thin-pool.ko` / `dm_thin_pool` | Device-mapper thin-pool/thin targets; owned fork, private symbol renames and existing target behavior |
| [`part-projection`](kernel/part-projection/) | `part-projection.ko` / `part_projection` | Configfs ABI 3 at `/config/part-projection` |
| [`efivarfs`](kernel/efivarfs/) | `efivarfs.ko` / `efivarfs` | Upstream efivarfs plus the project-GUID patch |
| [`efivar_store`](kernel/efivar_store/) | `efivar_store.ko` / `efivar_store` | Block-backed EFI variable service; pinned Rust EFVS engine behind C glue |

Each directory has its own Kbuild/Makefile and provenance. Shared code is limited to [`include/kernelsu_esp_lkm.h`](include/kernelsu_esp_lkm.h): descriptive name/version/ABI/criticality metadata and applicable readiness parameters. Metadata is not authorization. The core product owns rdinit and its ELF prebinding loader; the modules product owns `ppconf`, platform/storage helpers, Android lifecycle scripts and packaging.

## Build and admit exact artifacts

Supply the complete matching ACK source/output, not merely kernel headers. The output must contain `.config`, `Module.symvers`, `System.map` and `include/generated/utsrelease.h`. Supply the matching LLVM toolchain through PATH. Supported architecture names are `aarch64` and `x86_64`.

The DDK container lane binds each caller-supplied absolute path (`kmi_src`, `aarch64_out`, `x86_64_out`) into the job container at the identical path; nothing is copied or synthesized inside the image, and an unbound path is simply absent there. ddk-min exports an arm64 `CROSS_COMPILE`, which kbuild turns into a `--target=` that contradicts the x86_64 leg, so the workflow unsets it and lets kbuild derive the target from `ARCH`. The pinned `nightly-2026-08-08` toolchain with `rust-src` must be installed inside that container; the build fails closed without it.

```sh
python3 -m unittest scripts.test_kmi_modules
sh scripts/build-lkms.sh android16-6.12 6 aarch64 \
    /path/to/source /path/to/complete-output /path/to/artifacts
```

The gate builds all four projects, verifies the exact copied payload and writes:

```text
artifacts/<branch>-<generation>/<arch>/
  dm-thin-pool.ko
  dm-thin-pool.ko.compat.json
  part-projection.ko
  part-projection.ko.compat.json
  efivarfs.ko
  efivarfs.ko.compat.json
  efivar_store.ko
  efivar_store.ko.compat.json
```

For one project:

```sh
python3 scripts/kmi_modules.py build \
    --module-dir kernel/part-projection --module part-projection \
    --branch android16-6.12 --generation 6 --arch aarch64 \
    --kmi-src /path/to/source --kmi-out /path/to/complete-output
```

Admission checks ELF type/architecture, normalized internal module name, vermagic flags, exported CRCs, private imports against the supplied kernel map, and schema-2 receipt/input hashes. Private vmlinux imports require a compatible loader or suitable exports; successful compilation alone is not a loading guarantee. Never strip or rewrite admitted bytes afterward. A different layout, CFI scheme, signature policy or KMI cannot be repaired by symbol lookup.

`efivar_store` materializes exactly [`SOURCE_REVISION`](kernel/efivar_store/SOURCE_REVISION). `EFIVAR_STORE_REPO` may select a local repository containing that same commit; it does not change the pin. Its freestanding engine uses pinned `nightly-2026-08-08` with rust-src and locked dependencies; `CONFIG_RUST` is not required. The upstream source also ships standalone `linux/Kbuild` and non-autoloading `dkms.conf`; private imports still need exports or caller-owned prebinding.

CI host checks run on pushes/PRs. ACK and DDK gates require explicit complete prepared inputs and build both architectures. Incomplete header-only DDK images are rejected. Workflows upload artifacts, not deploy or publish releases.

## Runtime contracts

Part projection uses `/config/part-projection/{abi,format,state,last_error,commit,destroy,projections/,hide/}`. Each projection has `dev` and `ro`; hidden backends are canonical major:minor directory names. Commit accepts `1` or `seal`. Destroy accepts `1` only for an unsealed active view with no live openers/holders; busy or sealed views remain intact. Failed commits release acquired handles and permit correction. The old `/dev/gptctl` transport is removed. See the project ABI documentation for bounds and lifetime rules.

Mount filesystem type `efivarfs` at `/sys/firmware/efi/efivars`. Mount/read success, not directory presence, establishes frontend readiness. The backend accepts mutually exclusive `partuuid=<unique-GPT-UUID>` or `dev=<major>:<minor>`, or the existing `/chosen/efivar-store,partuuid` DT property. No label or fixed unique GUID substitutes for that selector. Linux refuses blank stores without writing; firmware owns initialization and compaction.

Backing-file reads, writes, fsync and final fput run under the retained file opener credentials via `override_creds`/`revert_creds`. Load before Android policy, and permit the opener domain to access that block device. No `esp` credential or provider ABI is involved. EFI sysfs cleanup removes only objects the backend created, never a native EFI tree.

## Verification boundary

The current arm64 `android16-6.12-6` builds passed exact artifact admission. The standalone backend and frontend additionally passed the QEMU immediate-read/update/delete/reboot/compaction/torn-tail/blank-refusal gate. That VM has no enforcing Android policy: it does not prove HAL-domain access, PIN unlock, native EFI replacement, or phone boot. The full platform/OTA and enforcing-device gates remain separate from these source/build checks.

Both architectures were also built and admitted inside the dated `ghcr.io/ylarod/ddk-min:android16-6.12-20260828` container (digest `sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee`): all four projects and the pinned standalone `linux/Kbuild` path, against the caller-supplied complete outputs bound into the container. Two independent runs produced byte-identical modules, and every schema-2 receipt matched the shipped artifact bytes and kernel-input digests. That run loaded no module and touched no device, so it proves compilation and admission only. The arm64 lane recorded `warning: the compiler differs from the one used to build the kernel` (image clang build `14043575` versus the `12833971` that built the supplied arm64 output); the x86_64 Cuttlefish output carries a recorded stock `module_layout` CRC adjustment, so it is an admitted build against that supplied output, not a fully source-qualified self-built kernel.

Retain the per-project licenses and provenance. Root-level inherited tooling remains covered by [`LICENSE`](LICENSE); kernel projects carry their own license declarations.

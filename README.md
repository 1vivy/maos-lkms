# maos-lkms

This repository builds independent Linux kernel modules. No module depends on the Egysk helper, daemon, credential provider, or root runtime. This repository does not provide early-boot orchestration.


| Project | Artifact / internal name | Interface |
| --- | --- | --- |
| [`dm-thin-pool`](kernel/dm-thin-pool/) | `dm-thin-pool.ko` / `dm_thin_pool` | Device-mapper thin-pool/thin targets. Owned fork with private symbol renames and existing target behavior |
| [`part-projection`](kernel/part-projection/) | `part-projection.ko` / `part_projection` | Configfs ABI 6, named DM disks and pp-range/pp-meta/pp-hole at `/config/part-projection` |
| [`efivarfs`](kernel/efivarfs/) | `efivarfs.ko` / `efivarfs` | Upstream efivarfs plus the project-GUID patch |
| [`efivar_store`](kernel/efivar_store/) | `efivar_store.ko` / `efivar_store` | Block-backed EFI variable service. Pinned Rust EFVS engine behind C glue |

Each module has its own Kbuild files and provenance. Shared code is in [`include/egysk_lkm.h`](include/egysk_lkm.h). The header defines descriptive names, versions, ABIs, criticality, and readiness metadata. This metadata does not authorize callers. This repository does not own PID 1 orchestration or module activation. It does not own product packaging or Android lifecycle scripts.


## Commands

Run the host contract checks:

```sh
python3 -m unittest scripts.test_kmi_modules scripts.test_module_set scripts.test_source_manifest
```

Build one pinned DDK module or the full arm64 set:

```sh
OUT_DIR=out/build-matrix-6.12 sh scripts/build-ddk-lkms.sh android16-6.12 6 dm-thin-pool
OUT_DIR=out/build-matrix-6.12-full sh scripts/build-ddk-lkms.sh android16-6.12 6
```

The pinned targets are android14-6.1 generation 11, android16-6.12 generation 6, and android17-6.18 generation 5. The DDK lane builds arm64 only. Set `OUT_DIR` to a fresh child of `out/` to preserve existing outputs. Set `EFIVAR_STORE_REPO` to a local `efivar-store` checkout to reuse it; the DDK lane bind-mounts that checkout read-only. Set `STRIP_DEBUG=1` to strip only debug sections before admission and retain `.ko.debug` bytes.

For matching caller-supplied kernel source and output, use:

```sh
OUT_DIR=out/build-ack sh scripts/build-lkms.sh <branch> <generation> <aarch64|x86_64> <kernel-source> <complete-kernel-output> [module ...]
```

Build-and-admission-only candidates require all four modules. They are not device-qualified and are not published as GitHub releases. Add `--release` to the package command to include corresponding sources, licenses, notices, deterministic checksums, and a deterministic archive; the existing `egysk/kmod/` overlay remains. The archive records the unresolved GPL-2.0-only/Apache-2.0 review for `efivar_store`. See [build and KMI admission](docs/build.md) for prerequisites, candidate packaging, and verification commands. Never load modules or write to a phone or block device.

## Design documents

- [Architecture](docs/architecture.md)
- [Design rationale](docs/design.md)
- [Runtime contracts](docs/runtime.md)
- [Build and KMI admission](docs/build.md)

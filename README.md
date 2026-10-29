# maos-lkms

This repository builds independent Linux kernel modules. No module depends on the Egysk helper, daemon, credential provider, or root runtime. This repository does not provide early-boot orchestration.


| Project | Artifact / internal name | Interface |
| --- | --- | --- |
| [`dm-thin-pool`](kernel/dm-thin-pool/) | `dm-thin-pool.ko` / `dm_thin_pool` | Device-mapper thin-pool/thin targets. Owned fork with private symbol renames and existing target behavior |
| [`part-projection`](kernel/part-projection/) | `part-projection.ko` / `part_projection` | Configfs ABI 6, named DM disks and pp-range/pp-meta/pp-hole at `/config/part-projection` |

These two modules are the complete product set. Each module has its own Kbuild files and provenance. Shared code is in [`include/egysk_lkm.h`](include/egysk_lkm.h). The header defines descriptive names, versions, ABIs, criticality, and readiness metadata. This metadata does not authorize callers. This repository does not own PID 1 orchestration or module activation. It does not own product packaging or Android lifecycle scripts.

Kernel-line dependencies are separated from the functional core. `dm-thin-pool` keeps its per-line port programme under `kernel/dm-thin-pool/abi/<line>/`. `part-projection` keeps one block-device port per line under `kernel/part-projection/abi/<line>/` and selects it from the kernel version. Both product modules build their `5.10`, `5.15`, `6.1`, `6.6`, `6.12`, and `6.18` artifacts from the same shared logic. The 5.10 ports are pre-rework adapters: the projection port retains a `bdget_disk()` reference (not an opener), reads openers under the device's `bd_mutex`, uses `GENHD_FL_UP` as the dead flag, iterates `hd_struct` partitions and enables scanning through `GENHD_FL_EXT_DEVT`.


## Commands

Run the host contract checks:

```sh
python3 -m unittest scripts.test_kmi_modules scripts.test_module_set scripts.test_source_manifest
```

Build one pinned DDK module or the complete arm64 set:

```sh
OUT_DIR=out/build-matrix-6.12-dm sh scripts/build-ddk-lkms.sh android16-6.12 6 dm-thin-pool
OUT_DIR=out/build-matrix-6.12-full sh scripts/build-ddk-lkms.sh android16-6.12 6
```

The pinned targets are android12-5.10 generation 9, android13-5.15 generation 8, android14-6.1 generation 11, android15-6.6 generation 8, android16-6.12 generation 6, and android17-6.18 generation 5. The DDK lane builds arm64 only. Set `OUT_DIR` to a fresh child of `out/` to preserve existing outputs. Set `STRIP_DEBUG=1` to strip only debug sections before admission and retain `.ko.debug` bytes.

For matching caller-supplied kernel source and output, use:

```sh
OUT_DIR=out/build-ack sh scripts/build-lkms.sh <branch> <generation> <aarch64|x86_64> <kernel-source> <complete-kernel-output> [module ...]
```

A complete set requires both modules. Build-and-admission-only candidates are not device-qualified and are not published as GitHub releases. Add `--release` to the package command to include corresponding sources, licenses, notices, deterministic checksums, and a deterministic archive; the existing `egysk/kmod/` overlay remains. See [build and KMI admission](docs/build.md) for prerequisites, candidate packaging, and verification commands. Never load modules or write to a phone or block device.

## Design documents

- [Architecture](docs/architecture.md)
- [Design rationale](docs/design.md)
- [Runtime contracts](docs/runtime.md)
- [Build and KMI admission](docs/build.md)

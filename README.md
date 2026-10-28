# maos-lkms

This repository builds independent Linux kernel modules. No module depends on the Egysk helper, daemon, credential provider, or root runtime. This repository does not provide early-boot orchestration.


| Project | Artifact / internal name | Interface |
| --- | --- | --- |
| [`dm-thin-pool`](kernel/dm-thin-pool/) | `dm-thin-pool.ko` / `dm_thin_pool` | Device-mapper thin-pool/thin targets; owned fork, private symbol renames and existing target behavior |
| [`part-projection`](kernel/part-projection/) | `part-projection.ko` / `part_projection` | Configfs ABI 6, named DM disks and pp-range/pp-meta/pp-hole at `/config/part-projection` |
| [`efivarfs`](kernel/efivarfs/) | `efivarfs.ko` / `efivarfs` | Upstream efivarfs plus the project-GUID patch |
| [`efivar_store`](kernel/efivar_store/) | `efivar_store.ko` / `efivar_store` | Block-backed EFI variable service; pinned Rust EFVS engine behind C glue |

Each module has its own Kbuild files and provenance. Shared code is in [`include/egysk_lkm.h`](include/egysk_lkm.h). The header defines descriptive names, versions, ABIs, criticality, and readiness metadata. This metadata does not authorize callers. This repository does not own PID 1 orchestration or module activation. It does not own product packaging or Android lifecycle scripts.


## Commands

Run host contract tests:

```sh
python3 -m unittest scripts.test_kmi_modules
```

Build and admit the canonical arm64 modules:

```sh
sh scripts/build-ddk-lkms.sh android16-6.12 6
```

For a caller-supplied exact kernel source and output, use:

```sh
sh scripts/build-lkms.sh <branch> <generation> <aarch64|x86_64> <kernel-source> <complete-kernel-output>
```

See [build and KMI admission](docs/build.md) for prerequisites and build details. Do not load modules or write to a phone or block device.

## Design documents

- [Architecture](docs/architecture.md)
- [Design rationale](docs/design.md)
- [Runtime contracts](docs/runtime.md)
- [Build and KMI admission](docs/build.md)

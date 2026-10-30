# Module architecture

`maos-lkms` builds two independent Linux kernel modules. Each module has its own Kbuild files and provenance.

| Module | Kernel interface | Boundary |
| --- | --- | --- |
| `dm-thin-pool.ko` | Device-mapper `thin-pool` and `thin` targets | Vendored thin-provisioning implementation with private symbol names |
| `part-projection.ko` | Configfs ABI 6 and `pp-range`, `pp-meta`, `pp-hole` targets | Device-mapper owns data BIO handling, queue stacking, and crypto |

The modules do not depend on the Egysk helper, daemon, credential provider, or root runtime. The shared header `include/egysk_lkm.h` defines descriptive module metadata and readiness parameters. This metadata does not authorize a caller.

## Kernel-line ports

Each module separates shared functional logic from the interfaces of the kernel lines it supports. Both modules support 5.10, 5.15, 6.1, 6.6, 6.12, and 6.18. No module applies one line's interface code to another line.

The 5.10 ports are pre-rework adapters, not aliases. `part-projection` keeps a `bdget_disk()` reference to the whole block device for the published disk. That reference is not an opener, so it cannot make the device busy or block DM teardown. The port locks that device's `bd_mutex`, reads `bd_openers` (which counts each open partition once), treats `GENHD_FL_UP` as the dead flag, iterates partitions with `disk_part_iter_*`, and enables scanning with `GENHD_FL_EXT_DEVT` while `GENHD_FL_NO_PART_SCAN` is clear. `dm-thin-pool` supplies its 5.10 metadata open mode, status mapping, wait test, bioset allocator and kcopyd declaration as ABI data.

| Module | Shared core | Per-line interfaces |
| --- | --- | --- |
| `dm-thin-pool` | `src/`, `thin-main.c`, `private-rename.h`; `prepare.py` stages a line's own device-mapper sources and applies the shared transformations | `abi/<line>/port.py` for each supported line |
| `part-projection` | `configfs.c`, `target.c` | `abi/<line>/bdev.h` for each supported line |

`part-projection/bdev.h` selects the port from the kernel version of the build. It stops the build for a line that has no port. `abi/file-bdev.h` holds the file-based open and read-only implementation that the 6.12 and 6.18 ports share. Each of those ports stays separate because it records its own line and provenance. The 5.15, 6.1, and 6.6 ports differ from each other: 5.15 and 6.1 open a plain `block_device`, and 6.6 opens a `bdev_handle` with `blk_mode_t` modes.

`dm-thin-pool` has no single per-line header. Its line differences are source transformations that `prepare.py` applies to that line's own kernel sources, so each port script lives beside the others and records its own edits. See [dm-thin-pool provenance](../kernel/dm-thin-pool/PROVENANCE.md).

This repository owns module source, build, and KMI admission. It does not own PID 1 orchestration, module activation, product packaging, or Android lifecycle scripts. Consumers load and configure modules through their own runtime contracts. A module's admission result does not establish runtime loading or device qualification.

## References

- [Build and KMI admission](build.md)
- [Design rationale](design.md)
- [Runtime contracts](runtime.md)
- [Verification boundaries](build.md#verification-commands-and-limits)
- [`dm-thin-pool`](../kernel/dm-thin-pool/README.md)
- [`part-projection`](../kernel/part-projection/README.md)

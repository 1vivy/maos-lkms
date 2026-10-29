# Provenance and licensing

The current `configfs.c` and `target.c` implement the configfs ABI 6 projection interface. Their base derives from the selected local `mockups/2026-10-09/partformer/kernel` source. Product changes add bounded geometry uploads, per-disk GPT metadata staging, device-mapper targets, and physical namespace ancestry through upstream `device_move`.

`pp-range` follows upstream dm-linear (Sistina Software 2001-2003); its provenance comment remains in source. Device-mapper owns data BIO, queue, and crypto stacking. This module does not provide a standalone gendisk, physical GPT writer, or crypto-profile engine.

The subtree is GPL-2.0-only. `LICENSE` supplies the full GPL v2 text. No binary, extracted firmware code, downstream patch, or third-party GPT module was imported.

Public Linux v6.12 interfaces consulted during implementation:

- [include/linux/blkdev.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/blkdev.h)
  — file-based bdev opens, dynamically allocated bio-based disks, initial disk
  registration/partition scan, partition metadata, atomic per-bdev flags,
  `blk_set_stacking_limits`, `queue_limits_stack_bdev` and exported `submit_bio`.
- [include/linux/blk_types.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/blk_types.h)
  — partition/whole-disk relationship, sector offsets and bio representation.
- [include/linux/blk-crypto-profile.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/blk-crypto-profile.h),
  [include/linux/blk-crypto.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/blk-crypto.h)
  and [block/blk-crypto-profile.c](https://github.com/torvalds/linux/blob/v6.12/block/blk-crypto-profile.c)
  — slotless stacking profile, lower capability intersection and key eviction.
- [block/bio-integrity.c](https://github.com/torvalds/linux/blob/v6.12/block/bio-integrity.c)
  — integrity payload allocation semantics for cloned bios.
- [drivers/block/brd.c](https://github.com/torvalds/linux/blob/v6.12/drivers/block/brd.c)
  — conventional bio-based disk operations and page mapping for RAM metadata.

`bdev.h` selects the block-device open, release, read-only and open-count
interface of the target tree. Each supported line has its own port with the same
small interface (`pp_bdev_handle`, `PP_OPEN_READ`, `pp_bdev_open_ro`,
`pp_bdev_close`, `pp_bdev`, `pp_bdev_ro`, `pp_disk_openers`):

| Port | Used for | Implementation |
| --- | --- | --- |
| `abi/5.15/bdev.h` | 5.15 | `blkdev_get_by_dev`, `blkdev_put`, `bd_read_only`, `part0->bd_openers` |
| `abi/6.1/bdev.h` | 6.1 | `blkdev_get_by_dev`, `blkdev_put`, `bd_read_only`, `disk_openers` |
| `abi/6.6/bdev.h` | 6.6 | `bdev_open_by_dev`/`bdev_release`, `bd_read_only`, `disk_openers` |
| `abi/6.12/bdev.h` | 6.12 | `abi/file-bdev.h` |
| `abi/6.18/bdev.h` | 6.18 | `abi/file-bdev.h` |

`abi/file-bdev.h` holds the file-based implementation that 6.12 and 6.18 share:
`bdev_file_open_by_dev`, `file_bdev`, `bdev_fput`, `bdev_set_flag`,
`bdev_clear_flag` and `BD_READ_ONLY`. The two lines have no difference in this
boundary, so they share one implementation and keep separate ports for their
own provenance. `bdev.h` selects a port from `LINUX_VERSION_CODE` and stops the
build with an error on any line that has no port. It does not apply one line's
code to another line. `configfs.c` exports the selected line as the
`part_projection_bdev_abi` `.modinfo` entry.

The pinned DDK trees define the supported generations:

- `ghcr.io/ylarod/ddk-min@sha256:9e68cd9fcab748584755d31ba88ef134efc938dbde17f258c2652315f6cd81cd`
  (`/opt/ddk/src/android13-5.15`, 5.15.202) supplies `blkdev_get_by_dev` and
  `blkdev_put` with an `fmode_t` mode, `bd_read_only`, `bd_meta_info`,
  `GENHD_FL_NO_PART`, `GD_DEAD`, `disk_to_dev`, `set_disk_ro`, `get_disk_ro`,
  `part_tbl`, `DPM_ORDER_DEV_AFTER_PARENT` and `DM_TARGET_PASSES_CRYPTO`. It has
  no `bdev_handle`, no `disk_openers()` and no `BD_*` flags.
- `ghcr.io/ylarod/ddk-min@sha256:1dd6ac340b627a90a4031d6d0df6b129d8cc949b139fb56032c898f023d3d5d3`
  (`/opt/ddk/src/android14-6.1`) supplies `blkdev_get_by_dev`, `blkdev_put`,
  `bd_read_only`, `bd_meta_info`, `disk_openers`, `set_disk_ro`,
  `GENHD_FL_NO_PART`, `GD_DEAD` and `DPM_ORDER_DEV_AFTER_PARENT`. It has no
  file-based open helper, no `BLK_OPEN_READ` and no `BD_*` flags.
- `ghcr.io/ylarod/ddk-min@sha256:51159bc935c75a282fc65bc87e02f16bd098d1cdf55dc558c4fdd0fcf7a132e2`
  (`/opt/ddk/src/android15-6.6`, 6.6.127) supplies `bdev_open_by_dev`,
  `bdev_release`, `blk_mode_t` open modes, `bd_read_only`, `bd_meta_info`,
  `disk_openers`, `set_disk_ro` and `GENHD_FL_NO_PART`. It has no
  `bdev_file_open_by_dev`, no `bdev_set_flag` and no `BD_*` flags.
- `ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee`
  (`android16-6.12`) and
  `ghcr.io/ylarod/ddk-min@sha256:fb8b66200bf402cf65a751060fc1aa29524b9fa8840feef16c7b196a4f3f0e6e`
  (`android17-6.18`) supply `bdev_file_open_by_dev`, `file_bdev`, `bdev_fput`,
  `bdev_set_flag`, `bdev_clear_flag` and `BD_READ_ONLY`.

Every port holds one open reference per handle and releases it once. No line
rejects a write open at open time. All five enforce read-only state in
`blkdev_write_iter()` and in mmap through `bdev_read_only()`. On 5.15, 6.1 and
6.6 the module assigns `bd_read_only`, which is the field that the same line's
`BLKROSET` handler writes with the same plain store (`block/ioctl.c`,
`blkdev_roset`). On 6.12 and 6.18 the module sets and clears `BD_READ_ONLY`.
5.15 exposes `bd_openers` as a plain `int`, so its port reads the count while the
caller holds `disk->open_mutex`, which guards that field there. That count
includes every open partition, because `blkdev_get_part()` takes one
whole-device open on a partition's first open and `blkdev_put_part()` drops it
only on the partition's final close (`block/bdev.c` in 5.15.202). Lines that have
no port are not claimed, and `bdev.h` stops their build with an error.

These are source and header comparisons only. They do not establish build,
load, runtime or device behavior.


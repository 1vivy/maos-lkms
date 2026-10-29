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

`bdev.h` selects the block-device open and read-only interface of the target
tree. The selection tests for `BLK_OPEN_READ`. These pinned DDK trees define the
two supported generations:

- `ghcr.io/ylarod/ddk-min@sha256:1dd6ac340b627a90a4031d6d0df6b129d8cc949b139fb56032c898f023d3d5d3`
  (`/opt/ddk/src/android14-6.1`) supplies `blkdev_get_by_dev`, `blkdev_put`,
  `bd_read_only`, `bd_meta_info`, `set_disk_ro`, `GENHD_FL_NO_PART`, `GD_DEAD`
  and `DPM_ORDER_DEV_AFTER_PARENT`. It has no file-based open helper, no
  `BLK_OPEN_READ` and no `BD_*` flags.
- `ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee`
  (`android16-6.12`) and
  `ghcr.io/ylarod/ddk-min@sha256:fb8b66200bf402cf65a751060fc1aa29524b9fa8840feef16c7b196a4f3f0e6e`
  (`android17-6.18`) supply `bdev_file_open_by_dev`, `file_bdev`, `bdev_fput`,
  `bdev_set_flag`, `bdev_clear_flag` and `BD_READ_ONLY`.

Both generations hold one open reference per handle, so ownership and release
are the same. Neither generation rejects a write open at open time. Both
enforce read-only state in `blkdev_write_iter()` and in mmap through
`bdev_read_only()`. On v6.1 the module assigns `bd_read_only`, which is the
field that the kernel `BLKROSET` handler writes with the same plain store. On
v6.12 and v6.18 the module sets and clears `BD_READ_ONLY`. Trees between these
generations are not claimed.

These are source and header comparisons only. They do not establish build,
load, runtime or device behavior.


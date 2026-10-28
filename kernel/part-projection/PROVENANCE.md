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


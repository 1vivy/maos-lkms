/* SPDX-License-Identifier: GPL-2.0-only */
/* v5.15 block-device port.
 *
 * v5.15 opens a plain struct block_device with blkdev_get_by_dev() and releases
 * it with blkdev_put(). It has no file-based open helper, no bdev_handle and no
 * BD_* flags. Read-only policy lives in bdev->bd_read_only, which
 * bdev_read_only() consults for writes and mmap. v5.15 has no exported per-bdev
 * setter: its BLKROSET handler assigns that field with the same plain store
 * (block/ioctl.c, blkdev_roset), so this port does the same. The handle owns one
 * open reference that the module releases once. A write open is not rejected
 * here; blkdev_write_iter() enforces the state.
 *
 * v5.15 has no disk_openers() helper. bd_openers is a plain int there, and the
 * caller of pp_disk_openers() already holds disk->open_mutex, which is the lock
 * that guards that count. In the pinned 5.15.202 block/bdev.c,
 * blkdev_get_part() acquires one whole-device open on a partition's first
 * open; blkdev_put_part() releases it only on the partition's final close.
 * Thus part0->bd_openers includes each open partition once, not once per
 * partition opener. The 6.1 disk_openers() helper documents the same counting
 * rule. Both counts are nonzero whenever any partition remains open. */
#ifndef PART_PROJECTION_ABI_5_15_BDEV_H
#define PART_PROJECTION_ABI_5_15_BDEV_H

#include <linux/fs.h>
#include <linux/blkdev.h>

#define PP_BDEV_ABI_LINE "5.15"

typedef struct block_device pp_bdev_handle;

#define PP_OPEN_READ FMODE_READ

static inline pp_bdev_handle *pp_bdev_open_ro(dev_t dev)
{
	return blkdev_get_by_dev(dev, FMODE_READ, NULL);
}

static inline void pp_bdev_close(pp_bdev_handle *h)
{
	blkdev_put(h, FMODE_READ);
}

static inline struct block_device *pp_bdev(pp_bdev_handle *h)
{
	return h;
}

static inline void pp_bdev_ro(struct block_device *bdev, bool ro)
{
	bdev->bd_read_only = ro;
}

static inline unsigned int pp_disk_openers(struct gendisk *disk)
{
	return disk->part0->bd_openers;
}

#endif /* PART_PROJECTION_ABI_5_15_BDEV_H */

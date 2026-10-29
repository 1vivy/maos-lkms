/* SPDX-License-Identifier: GPL-2.0-only */
/* v6.1 block-device port.
 *
 * v6.1 opens a plain struct block_device with blkdev_get_by_dev() and releases
 * it with blkdev_put(). It has no file-based open helper and no BD_* flags.
 * Read-only policy lives in bdev->bd_read_only, which bdev_read_only() consults
 * for writes and mmap. v6.1 has no exported per-bdev setter: its BLKROSET
 * handler assigns that field with the same plain store, so this port does the
 * same. The handle owns one open reference that the module releases once. A
 * write open is not rejected here; blkdev_write_iter() enforces the state. */
#ifndef PART_PROJECTION_ABI_6_1_BDEV_H
#define PART_PROJECTION_ABI_6_1_BDEV_H

#include <linux/fs.h>
#include <linux/blkdev.h>

#define PP_BDEV_ABI_LINE "6.1"

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
	return disk_openers(disk);
}

#endif /* PART_PROJECTION_ABI_6_1_BDEV_H */

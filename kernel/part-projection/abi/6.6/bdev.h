/* SPDX-License-Identifier: GPL-2.0-only */
/* android15-6.6 block-device port.
 *
 * 6.6 opens a block device with bdev_open_by_dev() into a struct bdev_handle
 * that owns the reference and the holder, and it releases that handle with
 * bdev_release(). It has no file-based open helper and no bdev_set_flag() or
 * bdev_clear_flag(). Open modes are blk_mode_t there, so dm_get_device() and
 * dm_table_get_mode() take and return blk_mode_t as well. Read-only policy is
 * the bool field bdev->bd_read_only, which bdev_read_only() consults for writes
 * and mmap; the 6.6 BLKROSET handler assigns that field with the same plain
 * store (block/ioctl.c, blkdev_roset). Trees between 6.1 and 6.12 are not
 * claimed. */
#ifndef PART_PROJECTION_ABI_6_6_BDEV_H
#define PART_PROJECTION_ABI_6_6_BDEV_H

#include <linux/fs.h>
#include <linux/blkdev.h>

#define PP_BDEV_ABI_LINE "6.6"

typedef struct bdev_handle pp_bdev_handle;

#define PP_OPEN_READ BLK_OPEN_READ

static inline pp_bdev_handle *pp_bdev_open_ro(dev_t dev)
{
	return bdev_open_by_dev(dev, BLK_OPEN_READ, NULL, NULL);
}

static inline void pp_bdev_close(pp_bdev_handle *h)
{
	bdev_release(h);
}

static inline struct block_device *pp_bdev(pp_bdev_handle *h)
{
	return h->bdev;
}

static inline void pp_bdev_ro(struct block_device *bdev, bool ro)
{
	bdev->bd_read_only = ro;
}

static inline unsigned int pp_disk_openers(struct gendisk *disk)
{
	return disk_openers(disk);
}

#endif /* PART_PROJECTION_ABI_6_6_BDEV_H */

/* SPDX-License-Identifier: GPL-2.0-only */
/* Shared file-based block-device port.
 *
 * v6.12 and v6.18 open block devices as files: bdev_file_open_by_dev(),
 * file_bdev() and bdev_fput(). Per-bdev read-only policy is the atomic
 * BD_READ_ONLY flag. Both lines give the same handle ownership: one open
 * reference that the module releases once. Neither line rejects a write open
 * early, so the read-only state is enforced by blkdev_write_iter() and by the
 * mmap path through bdev_read_only(). Both generation ports under
 * abi/6.12/bdev.h and abi/6.18/bdev.h include this file; the per-line policy
 * and provenance live in those ports, not here. */
#ifndef PART_PROJECTION_ABI_FILE_BDEV_H
#define PART_PROJECTION_ABI_FILE_BDEV_H

#include <linux/fs.h>
#include <linux/blkdev.h>

typedef struct file pp_bdev_handle;

#define PP_OPEN_READ BLK_OPEN_READ

static inline pp_bdev_handle *pp_bdev_open_ro(dev_t dev)
{
	return bdev_file_open_by_dev(dev, BLK_OPEN_READ, NULL, NULL);
}

static inline void pp_bdev_close(pp_bdev_handle *h)
{
	bdev_fput(h);
}

static inline struct block_device *pp_bdev(pp_bdev_handle *h)
{
	return file_bdev(h);
}

static inline void pp_bdev_ro(struct block_device *bdev, bool ro)
{
	if (ro)
		bdev_set_flag(bdev, BD_READ_ONLY);
	else
		bdev_clear_flag(bdev, BD_READ_ONLY);
}

static inline unsigned int pp_disk_openers(struct gendisk *disk)
{
	return disk_openers(disk);
}

#endif /* PART_PROJECTION_ABI_FILE_BDEV_H */

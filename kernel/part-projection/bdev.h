/* SPDX-License-Identifier: GPL-2.0-only */
/* Block-device handle portability for the pinned DDK trees.
 *
 * v6.12 and v6.18 open block devices as files: bdev_file_open_by_dev(),
 * file_bdev() and bdev_fput(). Per-bdev read-only policy is the atomic
 * BD_READ_ONLY flag. v6.1 opens a plain struct block_device with
 * blkdev_get_by_dev()/blkdev_put() and stores read-only policy in
 * bdev->bd_read_only, which bdev_read_only() consults for writes and mmap.
 * Both generations give the same handle ownership: one open reference that
 * the module releases once. Neither generation rejects a write open early,
 * so the read-only state is enforced by blkdev_write_iter() in both trees.
 * Trees between these generations are not claimed or tested. */
#ifndef PART_PROJECTION_BDEV_H
#define PART_PROJECTION_BDEV_H
#include <linux/fs.h>
#include <linux/blkdev.h>
#if defined(BLK_OPEN_READ)
typedef struct file pp_bdev_handle;
#define PP_OPEN_READ BLK_OPEN_READ
static inline pp_bdev_handle *pp_bdev_open_ro(dev_t dev) { return bdev_file_open_by_dev(dev,BLK_OPEN_READ,NULL,NULL); }
static inline void pp_bdev_close(pp_bdev_handle *h) { bdev_fput(h); }
static inline struct block_device *pp_bdev(pp_bdev_handle *h) { return file_bdev(h); }
static inline void pp_bdev_ro(struct block_device *bdev,bool ro)
{ if (ro) bdev_set_flag(bdev,BD_READ_ONLY); else bdev_clear_flag(bdev,BD_READ_ONLY); }
#else
typedef struct block_device pp_bdev_handle;
#define PP_OPEN_READ FMODE_READ
static inline pp_bdev_handle *pp_bdev_open_ro(dev_t dev) { return blkdev_get_by_dev(dev,FMODE_READ,NULL); }
static inline void pp_bdev_close(pp_bdev_handle *h) { blkdev_put(h,FMODE_READ); }
static inline struct block_device *pp_bdev(pp_bdev_handle *h) { return h; }
/* v6.1 has no exported per-bdev setter. Its BLKROSET handler assigns this
 * policy field with the same plain store, and bdev_read_only() reads it in
 * the write and mmap paths. */
static inline void pp_bdev_ro(struct block_device *bdev,bool ro) { bdev->bd_read_only=ro; }
#endif
#endif

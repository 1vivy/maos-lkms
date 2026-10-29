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
 * rule. Both counts are nonzero whenever any partition remains open.
 *
 * This line needs no retained disk reference: hold records the gendisk for
 * symmetry and adds no reference. Publication state is disk_openers(),
 * GD_DEAD and GENHD_FL_NO_PART, all guarded by disk->open_mutex. The scan
 * snapshot stores the whole flags word, which is what the core restored
 * before the port interface existed. v5.15 has no GENHD_FL_UP, so restoring
 * flags cannot resurrect a dead disk. */
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

static inline struct partition_meta_info *pp_bdev_info(struct block_device *bdev)
{
	return bdev->bd_meta_info;
}

static inline struct device *pp_bdev_dev(struct block_device *bdev)
{
	return &bdev->bd_device;
}

static inline void *pp_bvec_map(struct bio_vec *bv)
{
	return bvec_kmap_local(bv);
}

static inline void pp_bvec_unmap(void *addr, struct bio_vec *bv)
{
	(void)bv;
	kunmap_local(addr);
}

struct pp_disk_ref {
	struct gendisk *disk;
};
typedef struct pp_disk_ref pp_disk_ref;

static inline int pp_disk_hold(struct gendisk *disk, pp_disk_ref *ref)
{
	ref->disk = disk;
	return 0;
}

static inline void pp_disk_drop(pp_disk_ref *ref)
{
	ref->disk = NULL;
}

static inline void pp_disk_lock(pp_disk_ref *ref, struct gendisk *disk)
{
	(void)ref;
	mutex_lock(&disk->open_mutex);
}

static inline void pp_disk_unlock(pp_disk_ref *ref, struct gendisk *disk)
{
	(void)ref;
	mutex_unlock(&disk->open_mutex);
}

static inline unsigned int pp_disk_openers(pp_disk_ref *ref, struct gendisk *disk)
{
	(void)ref;
	return disk->part0->bd_openers;
}

static inline bool pp_disk_dead(struct gendisk *disk)
{
	return test_bit(GD_DEAD, &disk->state);
}

typedef struct {
	unsigned int flags;
} pp_scan_state;

static inline bool pp_disk_scan_suppressed(struct gendisk *disk)
{
	return !!(disk->flags & GENHD_FL_NO_PART);
}

static inline void pp_disk_scan_save(struct gendisk *disk, pp_scan_state *state)
{
	state->flags = disk->flags;
}

static inline void pp_disk_scan_restore(struct gendisk *disk,
					const pp_scan_state *state)
{
	disk->flags = state->flags;
}

static inline void pp_disk_scan_enable(struct gendisk *disk)
{
	disk->flags &= ~GENHD_FL_NO_PART;
}

typedef struct block_device pp_part_ref;

static inline void pp_part_hold(pp_part_ref *part)
{
	get_device(&part->bd_device);
}

static inline void pp_part_put(pp_part_ref *part)
{
	put_device(&part->bd_device);
}

static inline bool pp_part_read_only(pp_part_ref *part)
{
	return bdev_read_only(part);
}

static inline void pp_part_ro(pp_part_ref *part, bool ro)
{
	part->bd_read_only = ro;
}

/* Walks every non-zero partition under the caller's disk->open_mutex. */
static inline int pp_for_each_part(struct gendisk *disk, pp_disk_ref *ref,
	int (*fn)(struct block_device *, pp_part_ref *, void *), void *data)
{
	unsigned long index;
	struct block_device *bdev;
	int err = 0;

	(void)ref;
	xa_for_each(&disk->part_tbl, index, bdev) {
		if (!index)
			continue;
		err = fn(bdev, bdev, data);
		if (err)
			break;
	}
	return err;
}

#endif /* PART_PROJECTION_ABI_5_15_BDEV_H */

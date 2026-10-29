/* SPDX-License-Identifier: GPL-2.0-only */
/* v6.1 block-device port.
 *
 * v6.1 opens a plain struct block_device with blkdev_get_by_dev() and releases
 * it with blkdev_put(). It has no file-based open helper and no BD_* flags.
 * Read-only policy lives in bdev->bd_read_only, which bdev_read_only() consults
 * for writes and mmap. v6.1 has no exported per-bdev setter: its BLKROSET
 * handler assigns that field with the same plain store, so this port does the
 * same. The handle owns one open reference that the module releases once. A
 * write open is not rejected here; blkdev_write_iter() enforces the state.
 *
 * Publication state is the gendisk itself: disk_openers() counts whole and
 * partition openers, GD_DEAD marks a del_gendisk()ed disk and GENHD_FL_NO_PART
 * suppresses scanning. disk->open_mutex serializes those reads with open and
 * release. No retained block-device reference is needed, so hold adds none.
 * The scan snapshot stores the whole flags word, which is what the core
 * restored before the port interface existed. v6.1 has no GENHD_FL_UP. */
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
	return disk_openers(disk);
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

#endif /* PART_PROJECTION_ABI_6_1_BDEV_H */

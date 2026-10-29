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
 * claimed.
 *
 * Publication state is the gendisk itself: disk_openers() counts whole and
 * partition openers, GD_DEAD marks a del_gendisk()ed disk and GENHD_FL_NO_PART
 * suppresses scanning. disk->open_mutex serializes those reads with open and
 * release. No retained block-device reference is needed, so hold adds none.
 * The scan snapshot stores the whole flags word, which is what the core
 * restored before the port interface existed. 6.6 has no GENHD_FL_UP. */
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

#endif /* PART_PROJECTION_ABI_6_6_BDEV_H */

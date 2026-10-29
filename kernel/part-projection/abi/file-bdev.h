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
 * and provenance live in those ports, not here.
 *
 * Publication state is the gendisk itself: disk_openers() counts whole and
 * partition openers, GD_DEAD marks a del_gendisk()ed disk and GENHD_FL_NO_PART
 * suppresses scanning. disk->open_mutex serializes those reads with open and
 * release. No retained block-device reference is needed, so hold adds none.
 * The scan snapshot stores the whole flags word, which is what the core
 * restored before the port interface existed. Neither line has GENHD_FL_UP. */
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
	if (ro)
		bdev_set_flag(part, BD_READ_ONLY);
	else
		bdev_clear_flag(part, BD_READ_ONLY);
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

#endif /* PART_PROJECTION_ABI_FILE_BDEV_H */

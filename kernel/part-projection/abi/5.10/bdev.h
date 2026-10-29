/* SPDX-License-Identifier: GPL-2.0-only */
/* android12-5.10 block-device port.
 *
 * 5.10 opens a plain struct block_device with blkdev_get_by_dev() and releases
 * it with blkdev_put(). It has no file-based open helper and no bdev_handle.
 * Read-only policy of a partition is hd_struct.policy, which bdev_read_only()
 * returns; set_device_ro() stores the same field, so this port does the same
 * plain store.
 *
 * There is no GD_DEAD and no GENHD_FL_NO_PART here. A disk is dead once
 * del_gendisk() clears GENHD_FL_UP (block/genhd.c:918), after every partition
 * was invalidated (block/genhd.c:906-919). Partition scanning is controlled by
 * GENHD_FL_NO_PART_SCAN, and disk_max_parts() still caps partitions by
 * disk->minors. DM allocates its disk with one minor (drivers/md/dm.c:1849)
 * and does not set the scan flag, so this line expresses "scan suppressed" as
 * !disk_part_scan_enabled(). Enabling a scan therefore needs
 * GENHD_FL_EXT_DEVT: without it disk_max_parts() stays 1, and partition dev_t
 * lookup would go through blk_register_region() with the one-minor range that
 * device_add_disk() registered. GENHD_FL_EXT_DEVT makes 5.10 allocate each
 * partition dev_t from ext_devt_idr, which get_gendisk() resolves, so the port
 * sets that bit together with clearing the scan flag. The scan snapshot keeps
 * only those two bits and never rewrites GENHD_FL_UP, so restoring a dead disk
 * cannot resurrect it.
 *
 * Disk serialization and opener counts use the whole-disk block_device:
 * bdget_disk(disk, 0) returns an unopened reference that owns no opener (only
 * __blkdev_get() increments bd_openers, fs/block_dev.c:1568), and that bdev's
 * bd_mutex is what __blkdev_get() and __blkdev_put() hold around bd_openers and
 * around the open/release callbacks. Opening any partition recurses into the
 * whole device on that partition's first open (fs/block_dev.c:1537-1543), so
 * whole->bd_openers is nonzero whenever any whole or partition opener exists;
 * a partition's later opens do not add another whole-device open. The retained
 * reference is only valid for bd_mutex and bd_openers: after the last close
 * __blkdev_put() clears bd_part and bd_disk (fs/block_dev.c:1802-1806). It must
 * be released with bdput().
 *
 * Partition metadata and read-only policy come from the hd_struct that
 * disk_part_iter_next() hands out with a device reference, never from a
 * retained bdev's bd_part. Partition bdevs for identity and holder checks come
 * from bdget_disk(disk, partno) inside the iterator; bdget_part() and
 * get_gendisk() are not exported in this line. */
#ifndef PART_PROJECTION_ABI_5_10_BDEV_H
#define PART_PROJECTION_ABI_5_10_BDEV_H

#include <linux/fs.h>
#include <linux/blkdev.h>
#include <linux/genhd.h>
#include <linux/highmem.h>

#define PP_BDEV_ABI_LINE "5.10"

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
	return bdev->bd_part->info;
}

static inline struct device *pp_bdev_dev(struct block_device *bdev)
{
	return part_to_dev(bdev->bd_part);
}

/* 5.10 has no kmap_local_page(); kmap_atomic() is the local-mapping primitive
 * of this line. kunmap_atomic() masks its argument to the page boundary. */
static inline void *pp_bvec_map(struct bio_vec *bv)
{
	return kmap_atomic(bv->bv_page) + bv->bv_offset;
}

static inline void pp_bvec_unmap(void *addr, struct bio_vec *bv)
{
	kunmap_atomic((char *)addr - bv->bv_offset);
}

/* Retained whole-disk block_device used for the line's open/close mutex and
 * true opener count. It is not an opener and must not be dereferenced for
 * bd_part, bd_disk, bd_contains or a device model pointer. */
struct pp_disk_ref {
	struct block_device *bdev;
};
typedef struct pp_disk_ref pp_disk_ref;

static inline int pp_disk_hold(struct gendisk *disk, pp_disk_ref *ref)
{
	struct block_device *bdev = bdget_disk(disk, 0);

	if (!bdev)
		return -ENXIO;
	ref->bdev = bdev;
	return 0;
}

static inline void pp_disk_drop(pp_disk_ref *ref)
{
	bdput(ref->bdev);
	ref->bdev = NULL;
}

static inline void pp_disk_lock(pp_disk_ref *ref, struct gendisk *disk)
{
	(void)disk;
	mutex_lock(&ref->bdev->bd_mutex);
}

static inline void pp_disk_unlock(pp_disk_ref *ref, struct gendisk *disk)
{
	(void)disk;
	mutex_unlock(&ref->bdev->bd_mutex);
}

static inline unsigned int pp_disk_openers(pp_disk_ref *ref, struct gendisk *disk)
{
	(void)disk;
	return ref->bdev->bd_openers;
}

static inline bool pp_disk_dead(struct gendisk *disk)
{
	return !(disk->flags & GENHD_FL_UP);
}

/* Partition-scan controls owned by this port. */
#define PP_SCAN_MASK (GENHD_FL_EXT_DEVT | GENHD_FL_NO_PART_SCAN)

typedef struct {
	unsigned int flags;
} pp_scan_state;

static inline bool pp_disk_scan_suppressed(struct gendisk *disk)
{
	return !disk_part_scan_enabled(disk);
}

static inline void pp_disk_scan_save(struct gendisk *disk, pp_scan_state *state)
{
	state->flags = disk->flags & PP_SCAN_MASK;
}

static inline void pp_disk_scan_restore(struct gendisk *disk,
					const pp_scan_state *state)
{
	disk->flags = (disk->flags & ~PP_SCAN_MASK) | state->flags;
}

static inline void pp_disk_scan_enable(struct gendisk *disk)
{
	disk->flags |= GENHD_FL_EXT_DEVT;
	disk->flags &= ~GENHD_FL_NO_PART_SCAN;
}

/* Partition reference for read-only rollback. The hd_struct is pinned by its
 * device reference, which is also what disk_part_iter_next() relies on. */
typedef struct hd_struct pp_part_ref;

static inline void pp_part_hold(pp_part_ref *part)
{
	get_device(part_to_dev(part));
}

static inline void pp_part_put(pp_part_ref *part)
{
	put_device(part_to_dev(part));
}

static inline bool pp_part_read_only(pp_part_ref *part)
{
	return part->policy;
}

static inline void pp_part_ro(pp_part_ref *part, bool ro)
{
	part->policy = ro;
}

/* Walks every non-zero partition under the caller's bd_mutex. The bdev is an
 * unopened bdget_disk() reference used only for holder and identity checks. */
static inline int pp_for_each_part(struct gendisk *disk, pp_disk_ref *ref,
	int (*fn)(struct block_device *, pp_part_ref *, void *), void *data)
{
	struct disk_part_iter piter;
	struct hd_struct *part;
	int err = 0;

	(void)ref;
	disk_part_iter_init(&piter, disk, DISK_PITER_INCL_EMPTY);
	while ((part = disk_part_iter_next(&piter))) {
		struct block_device *bdev = bdget_disk(disk, part->partno);

		if (!bdev)
			continue;
		err = fn(bdev, part, data);
		bdput(bdev);
		if (err)
			break;
	}
	disk_part_iter_exit(&piter);
	return err;
}

#endif /* PART_PROJECTION_ABI_5_10_BDEV_H */

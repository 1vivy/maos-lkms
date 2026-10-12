// SPDX-License-Identifier: GPL-2.0-only
/* Based on upstream dm-linear (Sistina Software 2001-2003).
 * Only novel mapping responsibility: per-range write rejection/open mode.
 * DM owns clone allocation, splitting, completion, flush and crypto stacking. */
#include <linux/module.h>
#include <linux/device-mapper.h>
#include <linux/bio.h>
#include <linux/slab.h>
#include "projection.h"
#include <linux/highmem.h>
#include <linux/blk-crypto.h>
struct pp_range { struct dm_dev *dev; sector_t offset; bool ro; };
/* DM fans out empty WRITE|PREFLUSH bios, not request-level REQ_OP_FLUSH.
 * A data-bearing write must never bypass a range's read-only protection. */
static bool empty_flush(const struct bio *bio)
{
 return bio_op(bio) == REQ_OP_WRITE && (bio->bi_opf & REQ_PREFLUSH) &&
  !bio->bi_iter.bi_size;
}
static int range_ctr(struct dm_target *ti, unsigned int argc, char **argv)
{
 struct pp_range *r;
 unsigned long long offset;
 char extra;
 int err;
 if (argc != 3 || (strcmp(argv[2], "ro") && strcmp(argv[2], "rw")))
  return -EINVAL;
 if (sscanf(argv[1], "%llu%c", &offset, &extra) != 1 || offset != (sector_t)offset)
  return -EINVAL;
 r = kzalloc(sizeof(*r), GFP_KERNEL);
 if (!r) return -ENOMEM;
 r->offset = offset; r->ro = !strcmp(argv[2], "ro");
 err = dm_get_device(ti, argv[0], r->ro ? BLK_OPEN_READ : dm_table_get_mode(ti->table), &r->dev);
 if (err) { kfree(r); return err; }
 ti->private = r;
 ti->num_flush_bios = 1;
 ti->num_discard_bios = !r->ro;
 ti->num_write_zeroes_bios = !r->ro;
 ti->num_secure_erase_bios = !r->ro;
 return 0;
}
static void range_dtr(struct dm_target *ti)
{
 struct pp_range *r = ti->private;
 dm_put_device(ti, r->dev); kfree(r);
}
static int range_map(struct dm_target *ti, struct bio *bio)
{
 struct pp_range *r = ti->private;
 if (r->ro && bio_op(bio) != REQ_OP_READ && !empty_flush(bio))
  return DM_MAPIO_KILL;
 bio_set_dev(bio, r->dev->bdev);
 bio->bi_iter.bi_sector = r->offset + dm_target_offset(ti, bio->bi_iter.bi_sector);
 return DM_MAPIO_REMAPPED;
}
static int range_iterate(struct dm_target *ti, iterate_devices_callout_fn fn, void *data)
{
 struct pp_range *r = ti->private;
 return fn(ti, r->dev, r->offset, ti->len, data);
}
static void range_status(struct dm_target *ti, status_type_t type, unsigned int flags,
 char *result, unsigned int maxlen)
{
 struct pp_range *r = ti->private;
 snprintf(result, maxlen, "%s %llu %s", r->dev->name,
  (unsigned long long)r->offset, r->ro ? "ro" : "rw");
}
static struct target_type range_target = {
 .name = "pp-range", .version = {1, 0, 0}, .module = THIS_MODULE,
 .features = DM_TARGET_PASSES_CRYPTO,
 .ctr = range_ctr, .dtr = range_dtr, .map = range_map,
 .iterate_devices = range_iterate, .status = range_status,
};
struct pp_meta { unsigned int lbs; u8 data[]; };
/* Metadata snapshots have no backing block device, so they do not collapse
 * the crypto capability intersection of the actual data backings. */
static int meta_ctr(struct dm_target *ti, unsigned int argc, char **argv)
{
 unsigned int sector;
 struct pp_meta *data;
 int err;
 if (argc != 2 || !ti->len || ti->len > 88 || kstrtouint(argv[1],10,&sector))
  return -EINVAL;
 data=kmalloc(sizeof(*data) + (ti->len << SECTOR_SHIFT),GFP_KERNEL);
 if (!data) return -ENOMEM;
 err=pp_metadata_copy(argv[0],data->data,sector,ti->len,&data->lbs);
 if (err) { kfree(data); return err; }
 if ((ti->begin | ti->len) & ((data->lbs / 512) - 1)) { kfree(data); return -EINVAL; }
 ti->private=data;
 ti->num_flush_bios=1;
 return 0;
}
static void meta_dtr(struct dm_target *ti) { kfree(ti->private); }
static int meta_map(struct dm_target *ti,struct bio *bio)
{
 struct bio_vec bv;
 struct bvec_iter iter;
 size_t offset=dm_target_offset(ti,bio->bi_iter.bi_sector) << SECTOR_SHIFT;
 if (empty_flush(bio)) { bio_endio(bio); return DM_MAPIO_SUBMITTED; }
 if (bio_op(bio)!=REQ_OP_READ || bio_has_crypt_ctx(bio) ||
     offset + bio->bi_iter.bi_size > (ti->len << SECTOR_SHIFT))
  return DM_MAPIO_KILL;
 bio_for_each_segment(bv,bio,iter) {
  void *dest=bvec_kmap_local(&bv);
  memcpy(dest,((struct pp_meta *)ti->private)->data+offset,bv.bv_len);
  kunmap_local(dest);
  offset+=bv.bv_len;
 }
 bio_endio(bio);
 return DM_MAPIO_SUBMITTED;
}
static int hole_map(struct dm_target *ti,struct bio *bio)
{
 if (empty_flush(bio)) { bio_endio(bio); return DM_MAPIO_SUBMITTED; }
 if (bio_op(bio)!=REQ_OP_READ || bio_has_crypt_ctx(bio)) return DM_MAPIO_KILL;
 /* Sub-page GPT edges share cache pages with unallocated disk space. */
 zero_fill_bio(bio);
 bio_endio(bio);
 return DM_MAPIO_SUBMITTED;
}
static int hole_ctr(struct dm_target *ti,unsigned int argc,char **argv)
{ if (argc) return -EINVAL; ti->num_flush_bios=1; return 0; }
static void meta_hints(struct dm_target *ti, struct queue_limits *limits)
{
 struct pp_meta *m=ti->private;
 limits->logical_block_size=max(limits->logical_block_size,m->lbs);
 limits->physical_block_size=max(limits->physical_block_size,m->lbs);
}
static struct target_type meta_target={
 .name="pp-meta",.version={2,0,0},.module=THIS_MODULE,
 .features=DM_TARGET_PASSES_CRYPTO,.ctr=meta_ctr,.dtr=meta_dtr,.map=meta_map,.io_hints=meta_hints,
};
static struct target_type hole_target={
 .name="pp-hole",.version={1,1,0},.module=THIS_MODULE,
 .features=DM_TARGET_PASSES_CRYPTO,.ctr=hole_ctr,.map=hole_map,
};
int pp_target_init(void)
{
 int err=dm_register_target(&range_target);
 if (err) return err;
 err=dm_register_target(&meta_target);
 if (err) goto range;
 err=dm_register_target(&hole_target);
 if (!err) return 0;
 dm_unregister_target(&meta_target);
range:
 dm_unregister_target(&range_target);
 return err;
}
void pp_target_exit(void)
{
 dm_unregister_target(&hole_target);
 dm_unregister_target(&meta_target);
 dm_unregister_target(&range_target);
}

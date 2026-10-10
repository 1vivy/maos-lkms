// SPDX-License-Identifier: GPL-2.0-only
/* Configfs lifecycle/namespace controls. No gendisk or BIO submission. */
#include <linux/module.h>
#include <linux/configfs.h>
#include <linux/blkdev.h>
#include <linux/device-mapper.h>
#include <linux/slab.h>
#include <linux/capability.h>
#include <linux/overflow.h>
#include "projection.h"
static DEFINE_MUTEX(lock);
static bool active, sealed;
static struct gendisk *published;
static unsigned int saved_flags;
static dev_t publish_dev;
static struct configfs_subsystem subsystem;
static struct config_group endpoints;
static LIST_HEAD(items);
static unsigned int endpoint_count;
#define PP_METADATA_SECTORS 88U
static unsigned int metadata_lbs, metadata_sectors;
static u8 metadata[PP_METADATA_SECTORS << SECTOR_SHIFT];
static bool metadata_ready,metadata_frozen;
static unsigned int metadata_next;
static char metadata_generation[33];
int pp_metadata_copy(void *dest,unsigned int sector,unsigned int count, unsigned int *lbs)
{
 int err=0;
 mutex_lock(&lock);
 if (!metadata_ready || sector > metadata_sectors ||
     count > metadata_sectors-sector)
  err=-EINVAL;
 else {
  metadata_frozen=true;
  *lbs=metadata_lbs;
  memcpy(dest,metadata+(sector << SECTOR_SHIFT),count << SECTOR_SHIFT);
 }
 mutex_unlock(&lock);
 return err;
}
/* Text stores report errors synchronously; binary release ignores errors.
 * Records are "<32-hex generation> <logical block bytes> <chunk index> <1024 hex characters>".
 * Ordered records and a generation token prevent stale/mixed upload commits. */
static ssize_t pp_metadata_store(struct config_item *i,const char *text,size_t size)
{
 unsigned int sector, lbs, chunks;
 int position=0,err=-EINVAL;
 size_t count=size;
 char generation[33];
 u8 token[16],data[512];
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 mutex_lock(&lock);
 if (active || metadata_frozen) { err=-EBUSY; goto out; }
 metadata_ready=false;
 if (count && text[count-1]=='\n') count--;
 if (sscanf(text,"%32s %u %u %n",generation,&lbs,&sector,&position)!=3 ||
     strlen(generation)!=32 || hex2bin(token,generation,sizeof(token)) ||
     (lbs != 512 && lbs != 1024 && lbs != 2048 && lbs != 4096) ||
     position < 0 || (size_t)position > count || count-position != sizeof(data)*2 ||
     hex2bin(data,text+position,sizeof(data)))
  goto failed;
 chunks=(3 + 2 * DIV_ROUND_UP(16384U,lbs)) * (lbs / 512);
 if (sector >= chunks) goto failed;
 if (!sector && !metadata_next) {
  metadata_lbs=lbs; metadata_sectors=chunks;
  memcpy(metadata_generation,generation,sizeof(generation));
 }
 if (sector != metadata_next || lbs != metadata_lbs || strcmp(generation,metadata_generation))
  goto failed;
 memcpy(metadata+(sector << SECTOR_SHIFT),data,sizeof(data));
 metadata_next++;
 metadata_ready=metadata_next==metadata_sectors;
 err=0;
 goto out;
failed:
 metadata_next=0;
out:
 mutex_unlock(&lock);
 return err ? err : size;
}
CONFIGFS_ATTR_WO(pp_,metadata);
struct endpoint {
 struct config_item item;
 struct list_head entry;
 dev_t dev;
 bool hide, writable, pinned, hidden_changed;
 struct file *file, *whole;
 char name[PARTITION_META_INFO_VOLNAMELTH];
};
struct ro_part { struct list_head entry; struct block_device *bdev; };
struct ro_disk { struct list_head entry; struct gendisk *disk; };
static LIST_HEAD(ro_parts);
static LIST_HEAD(ro_disks);
static struct endpoint *ep(struct config_item *i) { return container_of(i, struct endpoint, item); }
static int parse_dev(const char *s, dev_t *dev)
{
 unsigned int a,b; char extra;
 if (sscanf(s, "%u:%u %c", &a,&b,&extra) != 2) return -EINVAL;
 *dev = MKDEV(a,b);
 return *dev && MAJOR(*dev)==a && MINOR(*dev)==b ? 0 : -EINVAL;
}
static bool writable_disk(struct gendisk *d)
{
 struct endpoint *e;
 list_for_each_entry(e,&items,entry)
  if (e->writable && file_bdev(e->file)->bd_disk == d) return true;
 return false;
}
static bool writable_part(struct block_device *b)
{
 struct endpoint *e;
 list_for_each_entry(e,&items,entry)
  if (e->writable && file_bdev(e->file)==b) return true;
 return false;
}
static void restore(void)
{
 struct endpoint *e;
 struct ro_part *p,*pn;
 struct ro_disk *d,*dn;
 list_for_each_entry_safe(p,pn,&ro_parts,entry) {
  bdev_clear_flag(p->bdev,BD_READ_ONLY); list_del(&p->entry); kfree(p);
 }
 list_for_each_entry_safe(d,dn,&ro_disks,entry) {
  set_disk_ro(d->disk,false); list_del(&d->entry); kfree(d);
 }
 list_for_each_entry(e,&items,entry) {
  if (e->file) {
   struct block_device *b=file_bdev(e->file);
   if (e->hidden_changed && b->bd_meta_info) {
    memcpy(b->bd_meta_info->volname,e->name,sizeof(e->name));
    kobject_uevent(&b->bd_device.kobj,KOBJ_CHANGE);
    e->hidden_changed=false;
   }
   if (e->whole) { bdev_fput(e->whole); e->whole=NULL; }
   bdev_fput(e->file); e->file=NULL;
  }
  if (e->pinned) { configfs_undepend_item(&e->item); e->pinned=false; }
 }
 if (published) {
  mutex_lock(&published->open_mutex);
  published->flags=saved_flags;
  mutex_unlock(&published->open_mutex);
  put_disk(published); published=NULL;
 }
 active=false; sealed=false; metadata_ready=false; metadata_frozen=false; metadata_next=0;
}
static int seal_disk(struct gendisk *disk)
{
 unsigned long index;
 struct block_device *b;
 if (!writable_disk(disk)) {
  struct ro_disk *d;
  if (get_disk_ro(disk)) return 0;
  d=kmalloc(sizeof(*d),GFP_KERNEL); if (!d) return -ENOMEM;
  d->disk=disk; list_add_tail(&d->entry,&ro_disks); set_disk_ro(disk,true);
  return 0;
 }
 mutex_lock(&disk->open_mutex);
 xa_for_each(&disk->part_tbl,index,b) {
  struct ro_part *p;
  if (!index || b->bd_holder || writable_part(b) || bdev_read_only(b)) continue;
  p=kmalloc(sizeof(*p),GFP_KERNEL);
  if (!p) { mutex_unlock(&disk->open_mutex); return -ENOMEM; }
  p->bdev=b; list_add_tail(&p->entry,&ro_parts); bdev_set_flag(b,BD_READ_ONLY);
 }
 mutex_unlock(&disk->open_mutex);
 return 0;
}
static int commit(bool seal)
{
 struct endpoint *e;
 struct mapped_device *md;
 int err;
 if (active) return -EBUSY;
 if (!metadata_ready) return -EINVAL;
 md=dm_get_md(publish_dev);
 if (!md) return -ENODEV;
 /* A disk reference, NOT a long-lived DM holder: dm_destroy waits for holders. */
 published=dm_disk(md);
 if (queue_logical_block_size(published->queue) != metadata_lbs) {
  dm_put(md); published=NULL; return -EINVAL;
 }
 get_device(disk_to_dev(published));
 dm_put(md);
 saved_flags=published->flags;
 list_for_each_entry(e,&items,entry) {
  err=configfs_depend_item_unlocked(&subsystem,&e->item);
  if (err) goto fail;
  e->pinned=true;
  e->file=bdev_file_open_by_dev(e->dev,BLK_OPEN_READ,NULL,NULL);
  if (IS_ERR(e->file)) { err=PTR_ERR(e->file); e->file=NULL; goto fail; }
  if (e->hide && (!bdev_is_partition(file_bdev(e->file)) || !file_bdev(e->file)->bd_meta_info)) {
   err=-EINVAL; goto fail;
  }
  e->whole=bdev_file_open_by_dev(disk_devt(file_bdev(e->file)->bd_disk),BLK_OPEN_READ,NULL,NULL);
  if (IS_ERR(e->whole)) { err=PTR_ERR(e->whole); e->whole=NULL; goto fail; }
  if (e->hide) memcpy(e->name,file_bdev(e->file)->bd_meta_info->volname,sizeof(e->name));
 }
 /* Do not mutate namespace until every reference and rollback record exists. */
 if (seal) list_for_each_entry(e,&items,entry) {
  err=seal_disk(file_bdev(e->file)->bd_disk); if (err) goto fail;
 }
 list_for_each_entry(e,&items,entry) if (e->hide) {
  file_bdev(e->file)->bd_meta_info->volname[0]=0;
  e->hidden_changed=true;
  kobject_uevent(&file_bdev(e->file)->bd_device.kobj,KOBJ_CHANGE);
 }
 mutex_lock(&published->open_mutex);
 published->flags &= ~GENHD_FL_NO_PART;
 mutex_unlock(&published->open_mutex);
 active=true; sealed=seal;
 return 0;
fail:
 /* The disk reference also protects rollback after the DM holder is released. */
 restore(); return err;
}
static ssize_t endpoint_dev_show(struct config_item *i,char *b)
{ return sysfs_emit(b,"%u:%u\n",MAJOR(ep(i)->dev),MINOR(ep(i)->dev)); }
static ssize_t endpoint_dev_store(struct config_item *i,const char *b,size_t n)
{ int err; if (!capable(CAP_SYS_ADMIN)) return -EPERM; mutex_lock(&lock); err=active ? -EBUSY : parse_dev(b,&ep(i)->dev); mutex_unlock(&lock); return err ? err : n; }
#define BOOL_ATTR(field) \
static ssize_t endpoint_##field##_show(struct config_item *i,char *b) { return sysfs_emit(b,"%u\n",ep(i)->field); } \
static ssize_t endpoint_##field##_store(struct config_item *i,const char *b,size_t n) { bool v; int err; if (!capable(CAP_SYS_ADMIN)) return -EPERM; err=kstrtobool(b,&v); mutex_lock(&lock); if (active) err=-EBUSY; if (!err) ep(i)->field=v; mutex_unlock(&lock); return err ? err : n; } \
CONFIGFS_ATTR(endpoint_,field)
BOOL_ATTR(hide);
BOOL_ATTR(writable);
CONFIGFS_ATTR(endpoint_,dev);
static struct configfs_attribute *ep_attrs[]={ &endpoint_attr_dev,&endpoint_attr_hide,&endpoint_attr_writable,NULL };
static void release(struct config_item *i) { kfree(ep(i)); }
static struct configfs_item_operations ep_ops={ .release=release };
static const struct config_item_type ep_type={ .ct_owner=THIS_MODULE,.ct_item_ops=&ep_ops,.ct_attrs=ep_attrs };
static struct config_item *make(struct config_group *g,const char *name)
{
 struct endpoint *e;
 if (!capable(CAP_SYS_ADMIN)) return ERR_PTR(-EPERM);
 mutex_lock(&lock);
 if (active) { mutex_unlock(&lock); return ERR_PTR(-EBUSY); }
 if (endpoint_count >= 384) { mutex_unlock(&lock); return ERR_PTR(-ENOSPC); }
 e=kzalloc(sizeof(*e),GFP_KERNEL);
 if (!e) { mutex_unlock(&lock); return ERR_PTR(-ENOMEM); }
 config_item_init_type_name(&e->item,name,&ep_type);
 endpoint_count++;
 list_add_tail(&e->entry,&items); mutex_unlock(&lock); return &e->item;
}
static void drop(struct config_group *g,struct config_item *i)
{ mutex_lock(&lock); list_del(&ep(i)->entry); endpoint_count--; mutex_unlock(&lock); config_item_put(i); }
static struct configfs_group_operations group_ops={ .make_item=make,.drop_item=drop };
static const struct config_item_type group_type={ .ct_owner=THIS_MODULE,.ct_group_ops=&group_ops };
static ssize_t pp_abi_show(struct config_item *i,char *b) { return sysfs_emit(b,"4\n"); }
static ssize_t pp_state_show(struct config_item *i,char *b) { return sysfs_emit(b,"%s\n",active ? (sealed ? "sealed" : "active") : "idle"); }
static ssize_t pp_dev_show(struct config_item *i,char *b) { return sysfs_emit(b,"%u:%u\n",MAJOR(publish_dev),MINOR(publish_dev)); }
static ssize_t pp_dev_store(struct config_item *i,const char *b,size_t n)
{ int err; if (!capable(CAP_SYS_ADMIN)) return -EPERM; mutex_lock(&lock); err=active ? -EBUSY : parse_dev(b,&publish_dev); mutex_unlock(&lock); return err ? err : n; }
static ssize_t pp_commit_store(struct config_item *i,const char *b,size_t n)
{
 int err;
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 if (!sysfs_streq(b,"1") && !sysfs_streq(b,"seal")) return -EINVAL;
 mutex_lock(&subsystem.su_mutex); mutex_lock(&lock);
 err=commit(sysfs_streq(b,"seal"));
 mutex_unlock(&lock); mutex_unlock(&subsystem.su_mutex); return err ? err : n;
}
static ssize_t pp_reset_store(struct config_item *i,const char *b,size_t n)
{
 int err=0;
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 if (!sysfs_streq(b,"1")) return -EINVAL;
 mutex_lock(&subsystem.su_mutex); mutex_lock(&lock);
 if (published) {
  mutex_lock(&published->open_mutex);
  if (!test_bit(GD_DEAD,&published->state) || disk_openers(published))
   err=-EBUSY;
  mutex_unlock(&published->open_mutex);
 }
 if (!err)
  restore();
 mutex_unlock(&lock); mutex_unlock(&subsystem.su_mutex);
 return err ? err : n;
}
CONFIGFS_ATTR_RO(pp_,abi);
CONFIGFS_ATTR_RO(pp_,state);
CONFIGFS_ATTR(pp_,dev);
CONFIGFS_ATTR_WO(pp_,commit);
CONFIGFS_ATTR_WO(pp_,reset);
static struct configfs_attribute *attrs[]={ &pp_attr_abi,&pp_attr_state,&pp_attr_dev,&pp_attr_metadata,&pp_attr_commit,&pp_attr_reset,NULL };
static const struct config_item_type type={ .ct_owner=THIS_MODULE,.ct_attrs=attrs };
static int __init init(void)
{
 int err=pp_target_init(); if (err) return err;
 config_group_init(&subsystem.su_group); mutex_init(&subsystem.su_mutex);
 config_item_set_name(&subsystem.su_group.cg_item,"part-projection");
 subsystem.su_group.cg_item.ci_type=&type;
 config_group_init_type_name(&endpoints,"endpoints",&group_type);
 configfs_add_default_group(&endpoints,&subsystem.su_group);
 err=configfs_register_subsystem(&subsystem);
 if (err)
  pp_target_exit();
 return err;
}
static void __exit fini(void) { configfs_unregister_subsystem(&subsystem); pp_target_exit(); }
module_init(init); module_exit(fini);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("DM-composed partition publication and endpoint namespace controls ABI4");
#include "egysk_lkm.h"
EGYSK_LKM_METADATA("part-projection", "2", "4", "1");

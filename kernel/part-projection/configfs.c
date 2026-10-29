// SPDX-License-Identifier: GPL-2.0-only
/* Configfs lifecycle/namespace controls. No BIO submission. */
#include <linux/module.h>
#include <linux/configfs.h>
#include <linux/blkdev.h>
#include <linux/device-mapper.h>
#include <linux/slab.h>
#include <linux/capability.h>
#include <linux/overflow.h>
#include "projection.h"
#include "bdev.h"
static DEFINE_MUTEX(lock);
static bool active, sealed, failed;
static struct configfs_subsystem subsystem;
static struct config_group endpoints, disks;
static LIST_HEAD(items);
static LIST_HEAD(disk_items);
static unsigned int endpoint_count;
#define PP_METADATA_SECTORS 88U
struct projection_disk {
 struct config_group group;
 struct list_head entry;
 dev_t dev, anchor;
 struct gendisk *published;
 struct mapped_device *preparing;
 struct device *anchor_parent;
 pp_disk_ref ref;
 pp_scan_state scan;
 bool pinned, ref_held;
 unsigned int metadata_lbs, metadata_sectors, metadata_next;
 u8 metadata[PP_METADATA_SECTORS << SECTOR_SHIFT];
 bool metadata_ready, metadata_frozen;
 char metadata_generation[33];
};
static struct projection_disk *pd(struct config_item *i)
{ return container_of(to_config_group(i),struct projection_disk,group); }
static bool owned(void) { return active || failed; }
int pp_metadata_copy(const char *name,void *dest,unsigned int sector,unsigned int count,
 unsigned int *lbs)
{
 struct projection_disk *d;
 int err=-ENOENT;
 mutex_lock(&lock);
 if (failed) { err=-EBUSY; goto out; }
 list_for_each_entry(d,&disk_items,entry) {
  if (strcmp(name,config_item_name(&d->group.cg_item))) continue;
  if (!d->metadata_ready || sector > d->metadata_sectors ||
      count > d->metadata_sectors-sector) { err=-EINVAL; break; }
  d->metadata_frozen=true;
  *lbs=d->metadata_lbs;
  memcpy(dest,d->metadata+(sector << SECTOR_SHIFT),count << SECTOR_SHIFT);
  err=0;
  break;
 }
out:
 mutex_unlock(&lock);
 return err;
}
/* Text stores report errors synchronously; binary release ignores errors.
 * Records are "<32-hex generation> <logical block bytes> <chunk index> <1024 hex characters>".
 * Ordered records and a generation token prevent stale/mixed upload commits. */
static ssize_t pp_metadata_store(struct config_item *i,const char *text,size_t size)
{
 struct projection_disk *d=pd(i);
 unsigned int sector, lbs, chunks;
 int position=0,err=-EINVAL;
 size_t count=size;
 char generation[33];
 u8 token[16],data[512];
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 mutex_lock(&lock);
 if (owned() || d->metadata_frozen) { err=-EBUSY; goto out; }
 d->metadata_ready=false;
 if (count && text[count-1]=='\n') count--;
 if (sscanf(text,"%32s %u %u %n",generation,&lbs,&sector,&position)!=3 ||
     strlen(generation)!=32 || hex2bin(token,generation,sizeof(token)) ||
     (lbs != 512 && lbs != 1024 && lbs != 2048 && lbs != 4096) ||
     position < 0 || (size_t)position > count || count-position != sizeof(data)*2 ||
     hex2bin(data,text+position,sizeof(data)))
  goto failed;
 chunks=(3 + 2 * DIV_ROUND_UP(16384U,lbs)) * (lbs / 512);
 if (sector >= chunks) goto failed;
 if (!sector && !d->metadata_next) {
  d->metadata_lbs=lbs; d->metadata_sectors=chunks;
  memcpy(d->metadata_generation,generation,sizeof(generation));
 }
 if (sector != d->metadata_next || lbs != d->metadata_lbs ||
     strcmp(generation,d->metadata_generation))
  goto failed;
 memcpy(d->metadata+(sector << SECTOR_SHIFT),data,sizeof(data));
 d->metadata_next++;
 d->metadata_ready=d->metadata_next==d->metadata_sectors;
 err=0;
 goto out;
failed:
 d->metadata_next=0;
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
 pp_bdev_handle *file, *whole;
 char name[PARTITION_META_INFO_VOLNAMELTH];
};
struct ro_part { struct list_head entry; pp_part_ref *part; };
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
  if (e->writable && pp_bdev(e->file)->bd_disk == d) return true;
 return false;
}
static bool writable_part(struct block_device *b)
{
 struct endpoint *e;
 list_for_each_entry(e,&items,entry)
  if (e->writable && pp_bdev(e->file)==b) return true;
 return false;
}
/* Namespace ancestry is independent of endpoint access and sealing policy. */
static int prepare_anchor(struct projection_disk *d)
{
 pp_bdev_handle *file;
 struct gendisk *disk;
 struct projection_disk *other;
 struct device *parent, *ancestor;
 int err=0;
 if (!d->anchor) return 0;
 file=pp_bdev_open_ro(d->anchor);
 if (IS_ERR(file)) return PTR_ERR(file);
 disk=pp_bdev(file)->bd_disk;
 parent=disk_to_dev(disk)->parent;
 if (!parent || !device_is_registered(parent)) { err=-EINVAL; goto out; }
 list_for_each_entry(other,&disk_items,entry) {
  if (disk==other->published) { err=-EINVAL; goto out; }
  for (ancestor=parent; ancestor; ancestor=ancestor->parent)
   if (ancestor==disk_to_dev(other->published)) { err=-EINVAL; goto out; }
 }
 d->anchor_parent=get_device(parent);
out:
 pp_bdev_close(file);
 return err;
}
static void restore(void)
{
 struct endpoint *e;
 struct ro_part *p,*pn;
 struct ro_disk *d,*dn;
 struct projection_disk *disk;
 list_for_each_entry_safe(p,pn,&ro_parts,entry) {
  pp_part_ro(p->part,false); list_del(&p->entry);
  pp_part_put(p->part); kfree(p);
 }
 list_for_each_entry_safe(d,dn,&ro_disks,entry) {
  set_disk_ro(d->disk,false); list_del(&d->entry); put_disk(d->disk); kfree(d);
 }
 list_for_each_entry(e,&items,entry) {
  if (e->file) {
   struct block_device *b=pp_bdev(e->file);
   struct partition_meta_info *info=pp_bdev_info(b);
   if (e->hidden_changed && info) {
    memcpy(info->volname,e->name,sizeof(e->name));
    kobject_uevent(&pp_bdev_dev(b)->kobj,KOBJ_CHANGE);
    e->hidden_changed=false;
   }
   if (e->whole) { pp_bdev_close(e->whole); e->whole=NULL; }
   pp_bdev_close(e->file); e->file=NULL;
  }
  if (e->pinned) { configfs_undepend_item(&e->item); e->pinned=false; }
 }
 list_for_each_entry(disk,&disk_items,entry) {
  if (disk->published) {
   if (disk->ref_held) {
    pp_disk_lock(&disk->ref,disk->published);
    pp_disk_scan_restore(disk->published,&disk->scan);
    pp_disk_unlock(&disk->ref,disk->published);
    pp_disk_drop(&disk->ref); disk->ref_held=false;
   }
   put_disk(disk->published); disk->published=NULL;
  }
  put_device(disk->anchor_parent); disk->anchor_parent=NULL;
  if (disk->preparing) { dm_put(disk->preparing); disk->preparing=NULL; }
  disk->metadata_ready=false; disk->metadata_frozen=false; disk->metadata_next=0;
  if (disk->pinned) {
   configfs_undepend_item(&disk->group.cg_item); disk->pinned=false;
  }
 }
 active=false; sealed=false; failed=false;
}
static int seal_part(struct block_device *bdev,pp_part_ref *part,void *data)
{
 struct ro_part *p;
 (void)data;
 /* Skip rules stay identical to the pre-port loop. */
 if (bdev->bd_holder || writable_part(bdev) || pp_part_read_only(part)) return 0;
 p=kmalloc(sizeof(*p),GFP_KERNEL);
 if (!p) return -ENOMEM;
 pp_part_hold(part);
 p->part=part; list_add_tail(&p->entry,&ro_parts); pp_part_ro(part,true);
 return 0;
}
static int seal_disk(struct gendisk *disk)
{
 pp_disk_ref ref;
 int err;
 if (!writable_disk(disk)) {
  struct ro_disk *d;
  if (get_disk_ro(disk)) return 0;
  d=kmalloc(sizeof(*d),GFP_KERNEL); if (!d) return -ENOMEM;
  get_device(disk_to_dev(disk));
  d->disk=disk; list_add_tail(&d->entry,&ro_disks); set_disk_ro(disk,true);
  return 0;
 }
 err=pp_disk_hold(disk,&ref);
 if (err) return err;
 pp_disk_lock(&ref,disk);
 err=pp_for_each_part(disk,&ref,seal_part,NULL);
 pp_disk_unlock(&ref,disk);
 pp_disk_drop(&ref);
 return err;
}
/* Ordinary dm_destroy waits for these transient holders before unregistering
 * disks. Never retain a DM holder in active/failed state: removal must work. */
static void release_preparing(void)
{
 struct projection_disk *d;
 list_for_each_entry(d,&disk_items,entry) {
  if (d->preparing) { dm_put(d->preparing); d->preparing=NULL; }
 }
}
static int commit(bool seal)
{
 struct endpoint *e;
 struct projection_disk *d,*other;
 struct mapped_device *md;
 int err;
 if (owned()) return -EBUSY;
 if (list_empty(&disk_items)) return -EINVAL;
 list_for_each_entry(d,&disk_items,entry) {
  if (!d->metadata_ready || !d->dev) { err=-EINVAL; goto fail; }
  list_for_each_entry(other,&disk_items,entry)
   if (other!=d && other->dev==d->dev) { err=-EINVAL; goto fail; }
  err=configfs_depend_item_unlocked(&subsystem,&d->group.cg_item);
  if (err) goto fail;
  d->pinned=true;
  md=dm_get_md(d->dev);
  if (!md) { err=-ENODEV; goto fail; }
  /* Keep a transient holder through device_move so del_gendisk cannot race.
   * Only the independent disk ref survives publication or a move failure. */
  d->preparing=md;
  d->published=dm_disk(md);
  get_device(disk_to_dev(d->published));
  err=pp_disk_hold(d->published,&d->ref);
  if (err) goto fail;
  d->ref_held=true;
  pp_disk_lock(&d->ref,d->published);
  pp_disk_scan_save(d->published,&d->scan);
  err=(disk_devt(d->published)!=d->dev ||
       queue_logical_block_size(d->published->queue)!=d->metadata_lbs ||
       !pp_disk_scan_suppressed(d->published) ||
       disk_to_dev(d->published)->parent ||
       !device_is_registered(disk_to_dev(d->published)) ||
       pp_disk_dead(d->published)) ? -EINVAL : 0;
  pp_disk_unlock(&d->ref,d->published);
  if (err) goto fail;
 }
 list_for_each_entry(e,&items,entry) {
  err=configfs_depend_item_unlocked(&subsystem,&e->item);
  if (err) goto fail;
  e->pinned=true;
  e->file=pp_bdev_open_ro(e->dev);
  if (IS_ERR(e->file)) { err=PTR_ERR(e->file); e->file=NULL; goto fail; }
  if (e->hide && (!bdev_is_partition(pp_bdev(e->file)) || !pp_bdev_info(pp_bdev(e->file)))) {
   err=-EINVAL; goto fail;
  }
  e->whole=pp_bdev_open_ro(disk_devt(pp_bdev(e->file)->bd_disk));
  if (IS_ERR(e->whole)) { err=PTR_ERR(e->whole); e->whole=NULL; goto fail; }
  if (e->hide) memcpy(e->name,pp_bdev_info(pp_bdev(e->file))->volname,sizeof(e->name));
 }
 list_for_each_entry(d,&disk_items,entry) {
  err=prepare_anchor(d); if (err) goto fail;
 }
 /* All validation and references precede shared namespace mutation. */
 if (seal) list_for_each_entry(e,&items,entry) {
  err=seal_disk(pp_bdev(e->file)->bd_disk); if (err) goto fail;
 }
 list_for_each_entry(e,&items,entry) if (e->hide) {
  pp_bdev_info(pp_bdev(e->file))->volname[0]=0;
  e->hidden_changed=true;
  kobject_uevent(&pp_bdev_dev(pp_bdev(e->file))->kobj,KOBJ_CHANGE);
 }
 list_for_each_entry(d,&disk_items,entry) {
  if (!d->anchor_parent) continue;
  if (!device_is_registered(disk_to_dev(d->published)) ||
      pp_disk_dead(d->published) ||
      disk_to_dev(d->published)->parent) { err=-ENODEV; goto move_failed; }
  err=device_move(disk_to_dev(d->published),d->anchor_parent,DPM_ORDER_DEV_AFTER_PARENT);
  if (err) {
   /* core.c drops new_parent even if its internal class-link rollback fails.
    * Initial parent was NULL; repair only an observed surviving new parent.
    * device_del consumes this ref, while our anchor_parent ref spans reset. */
   if (disk_to_dev(d->published)->parent==d->anchor_parent)
    get_device(d->anchor_parent);
   goto move_failed;
  }
 }
 list_for_each_entry(d,&disk_items,entry)
  if (pp_disk_dead(d->published)) { err=-ENODEV; goto move_failed; }
 /* No disk is scan-enabled until every ancestry move has succeeded. */
 list_for_each_entry(d,&disk_items,entry) {
  pp_disk_lock(&d->ref,d->published);
  pp_disk_scan_enable(d->published);
  pp_disk_unlock(&d->ref,d->published);
 }
 active=true; sealed=seal;
 release_preparing();
 return 0;
move_failed:
 /* device_move can fail its own cleanup; never attempt a second ancestry
  * mutation or restore shared protections underneath a partial publication. */
 failed=true; sealed=seal;
 pr_err("part-projection: publication failed (%d); remove all owned disks before reset\n",err);
 release_preparing();
 return err;
fail:
 restore();
 return err;
}
static ssize_t endpoint_dev_show(struct config_item *i,char *b)
{ return sysfs_emit(b,"%u:%u\n",MAJOR(ep(i)->dev),MINOR(ep(i)->dev)); }
static ssize_t endpoint_dev_store(struct config_item *i,const char *b,size_t n)
{ int err; if (!capable(CAP_SYS_ADMIN)) return -EPERM; mutex_lock(&lock); err=owned() ? -EBUSY : parse_dev(b,&ep(i)->dev); mutex_unlock(&lock); return err ? err : n; }
#define BOOL_ATTR(field) \
static ssize_t endpoint_##field##_show(struct config_item *i,char *b) { return sysfs_emit(b,"%u\n",ep(i)->field); } \
static ssize_t endpoint_##field##_store(struct config_item *i,const char *b,size_t n) { bool v; int err; if (!capable(CAP_SYS_ADMIN)) return -EPERM; err=kstrtobool(b,&v); mutex_lock(&lock); if (owned()) err=-EBUSY; if (!err) ep(i)->field=v; mutex_unlock(&lock); return err ? err : n; } \
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
 if (owned()) { mutex_unlock(&lock); return ERR_PTR(-EBUSY); }
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
static ssize_t disk_dev_show(struct config_item *i,char *b)
{ return pd(i)->dev ? sysfs_emit(b,"%u:%u\n",MAJOR(pd(i)->dev),MINOR(pd(i)->dev)) : sysfs_emit(b,"none\n"); }
static ssize_t disk_dev_store(struct config_item *i,const char *b,size_t n)
{ int err; if (!capable(CAP_SYS_ADMIN)) return -EPERM; mutex_lock(&lock); err=owned() ? -EBUSY : parse_dev(b,&pd(i)->dev); mutex_unlock(&lock); return err ? err : n; }
static ssize_t disk_anchor_show(struct config_item *i,char *b)
{ return pd(i)->anchor ? sysfs_emit(b,"%u:%u\n",MAJOR(pd(i)->anchor),MINOR(pd(i)->anchor)) : sysfs_emit(b,"none\n"); }
static ssize_t disk_anchor_store(struct config_item *i,const char *b,size_t n)
{
 int err=0;
 dev_t next;
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 mutex_lock(&lock);
 if (owned()) err=-EBUSY;
 else if (sysfs_streq(b,"none")) pd(i)->anchor=0;
 else { err=parse_dev(b,&next); if (!err) pd(i)->anchor=next; }
 mutex_unlock(&lock);
 return err ? err : n;
}
CONFIGFS_ATTR(disk_,dev);
CONFIGFS_ATTR(disk_,anchor);
static struct configfs_attribute *disk_attrs[]={
 &disk_attr_dev,&disk_attr_anchor,&pp_attr_metadata,NULL
};
static void disk_release(struct config_item *i) { kfree(pd(i)); }
static struct configfs_item_operations disk_ops={ .release=disk_release };
static const struct config_item_type pp_disk_type={
 .ct_owner=THIS_MODULE,.ct_item_ops=&disk_ops,.ct_attrs=disk_attrs
};
static struct config_group *make_disk(struct config_group *g,const char *name)
{
 struct projection_disk *d;
 if (!capable(CAP_SYS_ADMIN)) return ERR_PTR(-EPERM);
 if (!*name || strlen(name)>=DM_NAME_LEN) return ERR_PTR(-EINVAL);
 mutex_lock(&lock);
 if (owned()) { mutex_unlock(&lock); return ERR_PTR(-EBUSY); }
 d=kzalloc(sizeof(*d),GFP_KERNEL);
 if (!d) { mutex_unlock(&lock); return ERR_PTR(-ENOMEM); }
 config_group_init_type_name(&d->group,name,&pp_disk_type);
 list_add_tail(&d->entry,&disk_items);
 mutex_unlock(&lock);
 return &d->group;
}
static void drop_disk(struct config_group *g,struct config_item *i)
{
 mutex_lock(&lock); list_del(&pd(i)->entry); mutex_unlock(&lock);
 config_item_put(i);
}
static struct configfs_group_operations disks_ops={
 .make_group=make_disk,.drop_item=drop_disk
};
static const struct config_item_type disks_type={
 .ct_owner=THIS_MODULE,.ct_group_ops=&disks_ops
};
static ssize_t pp_abi_show(struct config_item *i,char *b) { return sysfs_emit(b,"6\n"); }
static ssize_t pp_state_show(struct config_item *i,char *b)
{
 ssize_t n;
 mutex_lock(&lock);
 n=sysfs_emit(b,"%s\n",failed ? "failed" : active ? (sealed ? "sealed" : "active") : "idle");
 mutex_unlock(&lock);
 return n;
}
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
 struct projection_disk *d;
 int err=0;
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 if (!sysfs_streq(b,"1")) return -EINVAL;
 mutex_lock(&subsystem.su_mutex); mutex_lock(&lock);
 list_for_each_entry(d,&disk_items,entry) {
  if (!d->published || !d->ref_held) continue;
  pp_disk_lock(&d->ref,d->published);
  if (!pp_disk_dead(d->published) || pp_disk_openers(&d->ref,d->published) ||
      device_is_registered(disk_to_dev(d->published)))
   err=-EBUSY;
  pp_disk_unlock(&d->ref,d->published);
  if (err) break;
 }
 if (!err)
  restore();
 mutex_unlock(&lock); mutex_unlock(&subsystem.su_mutex);
 return err ? err : n;
}
CONFIGFS_ATTR_RO(pp_,abi);
CONFIGFS_ATTR_RO(pp_,state);
CONFIGFS_ATTR_WO(pp_,commit);
CONFIGFS_ATTR_WO(pp_,reset);
static struct configfs_attribute *attrs[]={ &pp_attr_abi,&pp_attr_state,&pp_attr_commit,&pp_attr_reset,NULL };
static const struct config_item_type type={ .ct_owner=THIS_MODULE,.ct_attrs=attrs };
static int __init init(void)
{
 int err=pp_target_init(); if (err) return err;
 config_group_init(&subsystem.su_group); mutex_init(&subsystem.su_mutex);
 config_item_set_name(&subsystem.su_group.cg_item,"part-projection");
 subsystem.su_group.cg_item.ci_type=&type;
 config_group_init_type_name(&endpoints,"endpoints",&group_type);
 configfs_add_default_group(&endpoints,&subsystem.su_group);
 config_group_init_type_name(&disks,"disks",&disks_type);
 configfs_add_default_group(&disks,&subsystem.su_group);
 err=configfs_register_subsystem(&subsystem);
 if (err)
  pp_target_exit();
 return err;
}
static void __exit fini(void) { configfs_unregister_subsystem(&subsystem); pp_target_exit(); }
module_init(init); module_exit(fini);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("DM-composed partition publication and endpoint namespace controls ABI6");
/* The selected abi/<line> port is visible in .modinfo, so a built artifact
 * states which kernel-line interface it was compiled against. */
MODULE_INFO(part_projection_bdev_abi, PP_BDEV_ABI_LINE);
#include "egysk_lkm.h"
EGYSK_LKM_METADATA("part-projection", "3", "6", "1");

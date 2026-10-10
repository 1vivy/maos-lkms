// SPDX-License-Identifier: GPL-2.0-only
/* Included by gpt.c: configuration snapshots never expose the private C layout. */
struct projection_item {
	struct config_item item;
	struct list_head entry;
	dev_t dev;
	bool hidden, ro, pinned;
};
static LIST_HEAD(projections);
static LIST_HEAD(hidden_devices);
static unsigned int projection_count, hidden_count;
static const char *state = "idle";
static int last_error;
static struct configfs_subsystem projection_subsys;
static struct config_group projection_group, hide_group;

static struct projection_item *to_projection(struct config_item *item)
{
	return container_of(item, struct projection_item, item);
}
static bool control_token(const char *buf, size_t count, const char *token)
{
	if (count && buf[count - 1] == '\n')
		count--;
	return count == strlen(token) && !memcmp(buf, token, count);
}
static void staged_changed(void)
{
	state = projection_count || hidden_count ? "staged" : "idle";
	last_error = 0;
}
/* Decimal only, exact major:minor, optionally one final newline. */
static int parse_device(const char *text, size_t count, dev_t *dev)
{
	u32 numbers[2] = { 0, 0 };
	unsigned int part = 0;
	size_t i;
	bool digit = false;
	if (count && text[count - 1] == '\n')
		count--;
	for (i = 0; i < count; i++) {
		if (text[i] == ':' && !part && digit) {
			part = 1;
			digit = false;
			continue;
		}
		if (text[i] < '0' || text[i] > '9' ||
		    check_mul_overflow(numbers[part], 10U, &numbers[part]) ||
		    check_add_overflow(numbers[part], (u32)(text[i] - '0'),
				       &numbers[part]))
			return -EINVAL;
		digit = true;
	}
	if (!part || !digit)
		return -EINVAL;
	return checked_dev(numbers[0], numbers[1], dev);
}
static ssize_t projection_dev_show(struct config_item *item, char *buf)
{
	struct projection_item *p = to_projection(item);
	ssize_t n;
	mutex_lock(&control_lock);
	n = scnprintf(buf, PAGE_SIZE, "%u:%u\n", MAJOR(p->dev), MINOR(p->dev));
	mutex_unlock(&control_lock);
	return n;
}
static ssize_t projection_dev_store(struct config_item *item, const char *buf,
				    size_t count)
{
	struct projection_item *p = to_projection(item), *other;
	dev_t dev;
	int err;
	if (!capable(CAP_SYS_ADMIN))
		return -EPERM;
	mutex_lock(&control_lock);
	err = active ? -EBUSY : parse_device(buf, count, &dev);
	if (!err) {
		list_for_each_entry(other, &projections, entry)
			if (other != p && other->dev == dev) {
				err = -EEXIST;
				break;
			}
	}
	if (!err) {
		p->dev = dev;
		staged_changed();
	}
	mutex_unlock(&control_lock);
	return err ? err : count;
}
static ssize_t projection_ro_show(struct config_item *item, char *buf)
{
	ssize_t n;
	mutex_lock(&control_lock);
	n = scnprintf(buf, PAGE_SIZE, "%u\n", to_projection(item)->ro);
	mutex_unlock(&control_lock);
	return n;
}
static ssize_t projection_ro_store(struct config_item *item, const char *buf,
				   size_t count)
{
	int err = 0;
	if (!capable(CAP_SYS_ADMIN))
		return -EPERM;
	mutex_lock(&control_lock);
	if (active)
		err = -EBUSY;
	else if (!control_token(buf, count, "0") && !control_token(buf, count, "1"))
		err = -EINVAL;
	else {
		to_projection(item)->ro = control_token(buf, count, "1");
		staged_changed();
	}
	mutex_unlock(&control_lock);
	return err ? err : count;
}
CONFIGFS_ATTR(projection_, dev);
CONFIGFS_ATTR(projection_, ro);
static struct configfs_attribute *projection_attrs[] = {
	&projection_attr_dev, &projection_attr_ro, NULL,
};
static void projection_release(struct config_item *item)
{
	kfree(to_projection(item));
}
static struct configfs_item_operations projection_item_ops = {
	.release = projection_release,
};
static const struct config_item_type projection_type = {
	.ct_owner = THIS_MODULE,
	.ct_item_ops = &projection_item_ops,
	.ct_attrs = projection_attrs,
};
static const struct config_item_type hidden_type = {
	.ct_owner = THIS_MODULE,
	.ct_item_ops = &projection_item_ops,
};
static struct config_item *projection_make(struct config_group *group,
					   const char *name)
{
	struct projection_item *p, *other;
	bool hidden = group == &hide_group;
	dev_t dev = 0;
	unsigned int i;
	size_t len = strlen(name);
	int err = 0;
	char canonical[32];
	if (!capable(CAP_SYS_ADMIN))
		return ERR_PTR(-EPERM);
	mutex_lock(&control_lock);
	if (active) {
		err = -EBUSY;
		goto out;
	}
	if ((hidden ? hidden_count : projection_count) >=
	    (hidden ? GPT_MAX_HIDDEN : GPT_MAX_PROJECTIONS)) {
		err = -ENOSPC;
		goto out;
	}
	if (hidden) {
		err = parse_device(name, len, &dev);
		if (err)
			goto out;
		snprintf(canonical, sizeof(canonical), "%u:%u", MAJOR(dev), MINOR(dev));
		if (strcmp(canonical, name)) {
			err = -EINVAL;
			goto out;
		}
		list_for_each_entry(other, &hidden_devices, entry)
			if (other->dev == dev) {
				err = -EEXIST;
				goto out;
			}
	} else {
		if (!len || len > GPT_LABEL_BYTES) {
			err = -EINVAL;
			goto out;
		}
		for (i = 0; i < len; i++)
			if (name[i] < 0x20 || name[i] > 0x7e) {
				err = -EINVAL;
				goto out;
			}
	}
	p = kzalloc(sizeof(*p), GFP_KERNEL);
	if (!p) {
		err = -ENOMEM;
		goto out;
	}
	p->hidden = hidden;
	p->dev = dev;
	config_item_init_type_name(&p->item, "",
				  hidden ? &hidden_type : &projection_type);
	err = config_item_set_name(&p->item, "%s", name);
	if (err) {
		config_item_put(&p->item);
		goto out;
	}
	list_add_tail(&p->entry, hidden ? &hidden_devices : &projections);
	if (hidden)
		hidden_count++;
	else
		projection_count++;
	staged_changed();
	mutex_unlock(&control_lock);
	return &p->item;
out:
	mutex_unlock(&control_lock);
	return ERR_PTR(err);
}
static void projection_drop(struct config_group *group, struct config_item *item)
{
	struct projection_item *p = to_projection(item);
	/* Active items are configfs-dependent and rmdir never reaches here. */
	mutex_lock(&control_lock);
	list_del(&p->entry);
	if (p->hidden)
		hidden_count--;
	else
		projection_count--;
	staged_changed();
	mutex_unlock(&control_lock);
	config_item_put(item);
}
static struct configfs_group_operations projection_group_ops = {
	.make_item = projection_make,
	.drop_item = projection_drop,
};
static const struct config_item_type projection_group_type = {
	.ct_owner = THIS_MODULE,
	.ct_group_ops = &projection_group_ops,
};
static ssize_t pp_abi_show(struct config_item *item, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "3\n");
}
static ssize_t pp_format_show(struct config_item *item, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "gpt\n");
}
static ssize_t pp_state_show(struct config_item *item, char *buf)
{
	ssize_t n;
	mutex_lock(&control_lock);
	n = scnprintf(buf, PAGE_SIZE, "%s\n", state);
	mutex_unlock(&control_lock);
	return n;
}
static ssize_t pp_last_error_show(struct config_item *item, char *buf)
{
	ssize_t n;
	mutex_lock(&control_lock);
	n = scnprintf(buf, PAGE_SIZE, "%d\n", last_error);
	mutex_unlock(&control_lock);
	return n;
}
static void unpin_items(void)
{
	struct projection_item *p;
	list_for_each_entry(p, &projections, entry)
		if (p->pinned) {
			configfs_undepend_item(&p->item);
			p->pinned = false;
		}
	list_for_each_entry(p, &hidden_devices, entry)
		if (p->pinned) {
			configfs_undepend_item(&p->item);
			p->pinned = false;
		}
}
static int pin_items(struct list_head *head)
{
	struct projection_item *p;
	int err;
	list_for_each_entry(p, head, entry) {
		err = configfs_depend_item_unlocked(&projection_subsys, &p->item);
		if (err)
			return err;
		p->pinned = true;
	}
	return 0;
}
static ssize_t pp_commit_store(struct config_item *item, const char *buf, size_t count)
{
	struct gpt_apply *a;
	struct projection_item *p;
	unsigned int i;
	int err = 0;
	if (!capable(CAP_SYS_ADMIN))
		return -EPERM;
	/* Match make/drop lock order; serialize item linkage as well as writes. */
	mutex_lock(&projection_subsys.su_mutex);
	mutex_lock(&control_lock);
	if (active) {
		err = -EBUSY;
		goto out;
	}
	if (!control_token(buf, count, "1") && !control_token(buf, count, "seal")) {
		err = -EINVAL;
		goto failed;
	}
	a = kzalloc(sizeof(*a), GFP_KERNEL);
	if (!a) {
		err = -ENOMEM;
		goto failed;
	}
	a->version = GPT_ABI_VERSION;
	a->flags = control_token(buf, count, "seal") ? GPT_APPLY_FLAG_SEAL : 0;
	a->count = projection_count;
	a->hide_count = hidden_count;
	i = 0;
	list_for_each_entry(p, &projections, entry) {
		a->projections[i].major = MAJOR(p->dev);
		a->projections[i].minor = MINOR(p->dev);
		a->projections[i].read_only = p->ro;
		strscpy(a->projections[i].name, config_item_name(&p->item),
			 sizeof(a->projections[i].name));
		i++;
	}
	i = 0;
	list_for_each_entry(p, &hidden_devices, entry) {
		a->hide[i].major = MAJOR(p->dev);
		a->hide[i++].minor = MINOR(p->dev);
	}
	err = pin_items(&projections);
	if (!err)
		err = pin_items(&hidden_devices);
	if (!err)
		err = apply_view(a);
	kfree(a);
	if (err) {
		unpin_items();
		goto failed;
	}
	state = "active";
	last_error = 0;
	goto out;
failed:
	state = "failed";
	last_error = err;
	WRITE_ONCE(ready, false);
out:
	mutex_unlock(&control_lock);
	mutex_unlock(&projection_subsys.su_mutex);
	return err ? err : count;
}
static ssize_t pp_destroy_store(struct config_item *item, const char *buf, size_t count)
{
	struct block_device *bdev;
	unsigned long index;
	int err = 0;
	if (!capable(CAP_SYS_ADMIN))
		return -EPERM;
	if (!control_token(buf, count, "1"))
		return -EINVAL;
	mutex_lock(&projection_subsys.su_mutex);
	mutex_lock(&control_lock);
	if (!active) {
		err = -ENODEV;
		goto out;
	}
	if (active->seal) {
		err = -EPERM;
		goto out;
	}
	/* Exclude new opens atomically with the busy check. view_open observes
	 * retiring under this same mutex; failed teardown changes nothing. */
	mutex_lock(&active->disk->open_mutex);
	xa_for_each(&active->disk->part_tbl, index, bdev)
		if (atomic_read(&bdev->bd_openers) || bdev->bd_holders) {
			err = -EBUSY;
			break;
		}
	if (!err)
		active->retiring = true;
	mutex_unlock(&active->disk->open_mutex);
	if (err)
		goto out;
	WRITE_ONCE(ready, false);
	destroy_view(active);
	active = NULL;
	unpin_items();
	staged_changed();
out:
	if (err)
		last_error = err;
	mutex_unlock(&control_lock);
	mutex_unlock(&projection_subsys.su_mutex);
	return err ? err : count;
}
CONFIGFS_ATTR_RO(pp_, abi);
CONFIGFS_ATTR_RO(pp_, format);
CONFIGFS_ATTR_RO(pp_, state);
CONFIGFS_ATTR_RO(pp_, last_error);
CONFIGFS_ATTR_WO(pp_, commit);
CONFIGFS_ATTR_WO(pp_, destroy);
static struct configfs_attribute *pp_attrs[] = {
	&pp_attr_abi, &pp_attr_format, &pp_attr_state, &pp_attr_last_error,
	&pp_attr_commit, &pp_attr_destroy, NULL,
};
static const struct config_item_type pp_type = {
	.ct_owner = THIS_MODULE,
	.ct_attrs = pp_attrs,
};
static int __init projection_init(void)
{
	ready = false;
	sealed = false;
	config_group_init_type_name(&projection_subsys.su_group,
				    "part-projection", &pp_type);
	mutex_init(&projection_subsys.su_mutex);
	config_group_init_type_name(&projection_group, "projections", &projection_group_type);
	config_group_init_type_name(&hide_group, "hide", &projection_group_type);
	configfs_add_default_group(&projection_group, &projection_subsys.su_group);
	configfs_add_default_group(&hide_group, &projection_subsys.su_group);
	return configfs_register_subsystem(&projection_subsys);
}
static void __exit projection_exit(void)
{
	mutex_lock(&projection_subsys.su_mutex);
	mutex_lock(&control_lock);
	WRITE_ONCE(ready, false);
	destroy_view(active);
	active = NULL;
	unpin_items();
	mutex_unlock(&control_lock);
	mutex_unlock(&projection_subsys.su_mutex);
	configfs_unregister_subsystem(&projection_subsys);
}
module_init(projection_init);
module_exit(projection_exit);

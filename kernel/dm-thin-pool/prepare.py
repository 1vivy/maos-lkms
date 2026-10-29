#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stage dm-thin-pool for one GKI kernel line.

The module embeds the Linux device-mapper thin-provisioning family, so its
sources must come from the kernel that loads it. One snapshot cannot serve more
than one kernel line: dm-thin, dm-bufio, dm-kcopyd and dm-io differ between
lines in interfaces and in data-path code.

Two profiles:

* ``verified``  - the 6.12 line stages the vendored tree in this directory. That
  tree was proven against ACK 6.12 and stays byte-identical here.
* ``generated`` - every other supported line stages that line's own kernel
  source and applies the port programme below.

The programme is a list of strict text edits, not a patch applied with fuzz.
Each edit must match exactly the declared number of times. A kernel line that
changed one of these regions fails closed and names the edit, so no build
silently compiles an unported source. Each staged tree records its kernel
source files, module files, edits and private symbol renames in
``PROVENANCE.json``.

This tool stages sources. It does not compile, load or qualify a module.
It writes a new directory only: an existing `--output` path is refused, and a
unique temporary sibling is removed if staging fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent

SCHEMA_VERSION = 1
MODULE_NAME = "dm-thin-pool"

# Lines whose block layer defines BLK_STS_INVAL in include/linux/blk_types.h.
# 6.1 does not, and its blk_errors[] table maps -EINVAL to BLK_STS_IOERR.
INVAL_STATUS_LINES = frozenset({"6.18"})

# Project sources under src/ that generated staging must copy from this tree.
PROJECT_HEADERS = ("src/subsystems.h",)

# Kernel lines with a port programme derived from the line's own source.
GENERATED_LINES = frozenset({"6.1", "6.18"})
# Kernel lines whose module sources are the vendored tree in this directory.
VERIFIED_LINES = frozenset({"6.12"})
# The verified tree is proven for exactly this branch. Another branch on the
# same line needs its own generated programme or a fresh proof.
VERIFIED_BRANCH = {"6.12": "android16-6.12"}

DM_FILES = (
    "dm-thin.c",
    "dm-thin-metadata.c",
    "dm-thin-metadata.h",
    "dm-bufio.c",
    "dm-io.c",
    "dm-kcopyd.c",
    "dm-bio-prison-v1.c",
    "dm-bio-prison-v1.h",
    "dm-bio-prison-v2.c",
    "dm-bio-prison-v2.h",
)
PERSISTENT_DATA_DIR = "drivers/md/persistent-data"

OUTPUT_REQUIRED = (".config", "Module.symvers", "System.map")
SOURCE_REQUIRED = ("Makefile",)
# The ACK identity declarations, in the order scripts/kmi_modules.py reads them.
IDENTITY_FILES = ("build.config.constants", "build.config.common", "bazel/constants.scl")

# Kernel-internal helpers the port replaces. A helper is listed here only when
# the matching in-tree source calls it; the port programme fails if a call site
# is absent, so the list cannot drift silently from the source it describes.
REPLACED_HELPERS = {
    "dm_device_name": "pool->name: the module owns the pool table name",
    "dm_table_get_md": "pool_ctr passes dm_table_device_name() instead",
    "dm_get_md": "thin_ctr resolves the pool through the private table",
    "dm_put": "thin_ctr holds no mapped-device reference",
    "dm_suspended": "pool_status commits unless DM_STATUS_NOFLUSH_FLAG",
    "dm_noflush_suspending": "thin_presuspend always starts the noflush work",
    "dm_internal_suspend_noflush": "private pool suspend gate",
    "dm_internal_resume": "private pool suspend gate",
    "errno_to_blk_status": "private errno mapping in dm-thin.c and dm-bufio.c",
    "wait_on_bit_io": "private bit wait wrapper",
    "bit_wait_io": "private bit wait wrapper",
    "bio_kmalloc": "module-owned bio_set allocated from pinned memory",
    "bio_uninit": "bio_put releases a bio_set allocation",
    "__dm_get_module_param": "READ_ONCE() plus clamp of the module parameter",
}

# Tokens that must not survive in a ported source: each one names kernel
# internals the port is required to replace, or a module entry point the
# composed module must not carry.
FORBIDDEN_AFTER_PORT = {
    "src/dm-thin.c": (
        "struct mapped_device",
        "pool_md",
        "thin_md",
        "dm_device_name(",
        "dm_table_get_md(",
        "dm_get_md(",
        "dm_put(",
        "dm_suspended(",
        "dm_noflush_suspending(",
        "dm_internal_suspend_noflush(",
        "dm_internal_resume(",
        "errno_to_blk_status(",
        "module_init(",
        "module_exit(",
    ),
    "src/dm-bufio.c": (
        "bio_kmalloc(",
        "bio_uninit(",
        "module_init(",
        "module_exit(",
    ),
    "src/dm-kcopyd.c": ("__dm_get_module_param(",),
    "src/dm-bio-prison-v1.c": ("module_init(", "module_exit("),
}

# Tokens the port owes the module and its consumer.
REQUIRED_AFTER_PORT = {
    "src/dm-thin.c": (
        '#include "subsystems.h"',
        "char name[DM_NAME_LEN];",
        "READ_ONCE(tc->pool->suspended)",
        "int __init thinpool_private_thin_init(void)",
        "void thinpool_private_thin_exit(void)",
        ".name = \"thin-pool\",",
        ".name = \"thin\",",
        "DM_TARGET_IMMUTABLE | DM_TARGET_PASSES_CRYPTO",
        ".features = DM_TARGET_PASSES_CRYPTO,",
        "skip_block_zeroing is mandatory for encrypted thin pools",
        "noflush_work(tc, do_noflush_start);",
    ),
    "src/dm-bufio.c": (
        '#include "subsystems.h"',
        "static blk_status_t thinpool_errno_to_blk_status(int error)",
        "#define wait_on_bit_io thinpool_wait_on_bit_io",
        "static struct bio_set dm_bufio_bioset;",
        "bioset_init(&dm_bufio_bioset, 16, 0, BIOSET_NEED_BVECS)",
        "bioset_exit(&dm_bufio_bioset);",
        "bio_put(bio);",
        "int __init thinpool_private_bufio_init(void)",
        "void thinpool_private_bufio_exit(void)",
    ),
    "src/dm-kcopyd.c": ("READ_ONCE(kcopyd_subjob_size_kb)",),
    "src/dm-io.c": ("thin_private_io",),
    "src/dm-bio-prison-v1.c": (
        '#include "subsystems.h"',
        "thin_private_prison_cell",
        "int __init thinpool_private_prison_init(void)",
        "void thinpool_private_prison_exit(void)",
    ),
}


class PortError(RuntimeError):
    """An input or source does not satisfy the port contract."""


def require(condition: object, reason: str) -> None:
    if not condition:
        raise PortError(reason)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Source:
    """One source file under a strictly checked edit programme."""

    def __init__(self, path: str, text: str) -> None:
        self.path = path
        self.text = text
        self.edits: list[dict[str, object]] = []

    def once(self, old: str, new: str, what: str) -> None:
        self._counted(old, new, 1, what)

    def all(self, old: str, new: str, expected: int, what: str) -> None:
        self._counted(old, new, expected, what)

    def _counted(self, old: str, new: str, expected: int, what: str) -> None:
        found = self.text.count(old)
        require(
            found == expected,
            f"{self.path}: {what}: expected {expected} match(es), found {found}: {old!r}",
        )
        self.text = self.text.replace(old, new)
        self.edits.append(
            {
                "file": self.path,
                "what": what,
                "matches": found,
                "before_sha256": text_digest(old),
                "after_sha256": text_digest(new),
            }
        )

    def forbid(self, token: str, what: str) -> None:
        require(token not in self.text, f"{self.path}: {what}: {token!r} remains")


def check_declared_tokens(source: Source, forbidden: tuple[str, ...],
                          required: tuple[str, ...]) -> None:
    for token in forbidden:
        source.forbid(token, "declared forbidden surface")
    for token in required:
        require(token in source.text, f"{source.path}: required token missing: {token!r}")


def ensure_external_definition(source: Source, definition: str, what: str) -> None:
    """Make one exact definition externally linked so a shared prototype applies.

    The subsystem entry points are declared in ``src/subsystems.h`` without
    storage class.  A line that defines one as ``static`` would keep internal
    linkage and contradict that prototype, so the programme drops the
    ``static`` keyword through this exact, counted edit.
    """
    internal = "static " + definition
    internal_hits = source.text.count(internal)
    plain_hits = source.text.count(definition) - internal_hits
    require(
        internal_hits + plain_hits == 1,
        f"{source.path}: {what}: expected one definition, "
        f"found static={internal_hits} external={plain_hits}: {definition.strip()!r}",
    )
    if internal_hits:
        source.once(internal, definition, what)


def require_external_definition(source: Source, definition: str, what: str) -> None:
    """Require an upstream entry point that this module calls to stay external."""
    require(
        "static " + definition not in source.text,
        f"{source.path}: {what}: definition must stay externally linked",
    )
    require(
        source.text.count(definition) == 1,
        f"{source.path}: {what}: expected exactly one definition",
    )


# ---------------------------------------------------------------- port programme

def bufio_private_helpers(line: str) -> str:
    """Private helpers for the buffered I/O data path.

    The errno mapping follows the line's own ``blk_errors[]`` table.  For
    example, 6.1 has no ``BLK_STS_INVAL`` entry, so -EINVAL maps to
    ``BLK_STS_IOERR`` there.  The helper must not name a status the line lacks.
    """
    inval = ""
    if line in INVAL_STATUS_LINES:
        inval = "\tcase -EINVAL:\n\t\treturn BLK_STS_INVAL;\n"
    return f"""/*
 * Private copies of kernel-internal helpers.  The module must not import a
 * non-exported block-layer internal, so the two helpers the buffered I/O data
 * path needs are defined here with the same semantics as the in-tree code.
 */
static blk_status_t thinpool_errno_to_blk_status(int error)
{{
	switch (error) {{
	case 0:
		return BLK_STS_OK;
	case -EOPNOTSUPP:
		return BLK_STS_NOTSUPP;
	case -ETIMEDOUT:
		return BLK_STS_TIMEOUT;
	case -ENOSPC:
		return BLK_STS_NOSPC;
	case -ENOMEM:
		return BLK_STS_RESOURCE;
	case -EBUSY:
		return BLK_STS_DEV_RESOURCE;
	case -EAGAIN:
		return BLK_STS_AGAIN;
	case -ENODEV:
		return BLK_STS_OFFLINE;
{inval}	default:
		return BLK_STS_IOERR;
	}}
}}

static int thinpool_bit_wait_io(struct wait_bit_key *key, int mode)
{{
	io_schedule();
	return signal_pending_state(mode, current) ? -EINTR : 0;
}}

static int thinpool_wait_on_bit_io(unsigned long *word, int bit, unsigned int mode)
{{
	might_sleep();
	if (!test_bit_acquire(bit, word))
		return 0;

	return out_of_line_wait_on_bit(word, bit, thinpool_bit_wait_io, mode);
}}

static int thinpool_wait_on_bit_lock_io(unsigned long *word, int bit,
					unsigned int mode)
{{
	might_sleep();
	if (!test_and_set_bit(bit, word))
		return 0;

	return out_of_line_wait_on_bit_lock(word, bit, thinpool_bit_wait_io,
					    mode);
}}

#define wait_on_bit_io thinpool_wait_on_bit_io
#define wait_on_bit_lock_io thinpool_wait_on_bit_lock_io
"""

SUSPEND_GATE_COMMENT = """/*
 * The private fork cannot recursively suspend mapped devices because those
 * DM-core entry points are not KMI exports.  Setting pool->suspended closes
 * the map-side gate: new bios are retained on retry_on_resume_list.  The
 * ordered pool workqueue is then flushed in postsuspend before commit, so all
 * metadata work admitted before the gate is complete.  The commit's data
 * device flush orders already-remapped writes before the new table is bound.
 *
 * This preserves the ordering established by upstream commit 583024d248f4
 * without recursively entering DM suspend.  It cannot reproduce that
 * suspend dependency deadlock: pool suspend never waits for a thin DM-core
 * suspend whose completion depends on this pool's worker.  Retained bios are
 * released only after pool resume clears the gate.
 */
"""

ZERO_NEW_BLOCKS_POLICY = """	/*
	 * An encrypted thin pool must not write zeroes below the encryption
	 * target, so the pool requires skip_block_zeroing.
	 */
	if (pf.zero_new_blocks) {
		ti->error = "skip_block_zeroing is mandatory for encrypted thin pools";
		r = -EINVAL;
		goto out_unlock;
	}

"""

POOL_TABLE_LOOKUP_OLD = """static struct pool *__pool_table_lookup(struct mapped_device *md)
{
	struct pool *pool = NULL, *tmp;

	BUG_ON(!mutex_is_locked(&dm_thin_pool_table.mutex));

	list_for_each_entry(tmp, &dm_thin_pool_table.pools, list) {
		if (tmp->pool_md == md) {
			pool = tmp;
			break;
		}
	}

	return pool;
}
"""

POOL_TABLE_LOOKUP_NEW = """static struct pool *__pool_table_lookup_name(const char *name)
{
	struct pool *pool;

	BUG_ON(!mutex_is_locked(&dm_thin_pool_table.mutex));

	list_for_each_entry(pool, &dm_thin_pool_table.pools, list)
		if (!strcmp(pool->name, name))
			return pool;

	return NULL;
}

static struct pool *__pool_table_lookup_dev(dev_t dev)
{
	struct pool *pool;

	BUG_ON(!mutex_is_locked(&dm_thin_pool_table.mutex));

	list_for_each_entry(pool, &dm_thin_pool_table.pools, list)
		if (pool->dev == dev)
			return pool;

	return NULL;
}

static struct pool *__pool_table_lookup_unbound(void)
{
	struct pool *pool;
	struct pool *found = NULL;

	BUG_ON(!mutex_is_locked(&dm_thin_pool_table.mutex));

	list_for_each_entry(pool, &dm_thin_pool_table.pools, list) {
		if (pool->dev)
			continue;
		if (found)
			return NULL;
		found = pool;
	}

	return found;
}
"""

THIN_CTR_LOOKUP_OLD = """	pool_md = dm_get_md(tc->pool_dev->bdev->bd_dev);
	if (!pool_md) {
		ti->error = "Couldn't get pool mapped device";
		r = -EINVAL;
		goto bad_common;
	}

	tc->pool = __pool_table_lookup(pool_md);
	if (!tc->pool) {
		ti->error = "Couldn't find pool object";
		r = -EINVAL;
		goto bad_pool_lookup;
	}
	__pool_inc(tc->pool);
"""

THIN_CTR_LOOKUP_NEW = """	tc->pool = __pool_table_lookup_dev(tc->pool_dev->bdev->bd_dev);
	if (!tc->pool) {
		const char *name = kbasename(argv[0]);

		tc->pool = __pool_table_lookup_name(name);
		if (!tc->pool)
			tc->pool = __pool_table_lookup_unbound();
		if (tc->pool && tc->pool->dev &&
		    tc->pool->dev != tc->pool_dev->bdev->bd_dev)
			tc->pool = NULL;
		else if (tc->pool)
			tc->pool->dev = tc->pool_dev->bdev->bd_dev;
	}
	if (!tc->pool) {
		ti->error = "Couldn't find pool object";
		r = -EINVAL;
		goto bad_common;
	}
	__pool_inc(tc->pool);
"""


def port_thin(source: Source, line: str) -> None:
    source.once(
        '#include "dm-thin-metadata.h"\n',
        '#include "subsystems.h"\n#include "dm-thin-metadata.h"\n',
        "declare the shared subsystem entry points",
    )
    source.once(
        "#include <linux/slab.h>\n",
        "#include <linux/slab.h>\n#include <linux/string.h>\n",
        "include linux/string.h for strscpy, strcmp and kbasename",
    )
    source.once(
        "\tstruct dm_target *ti;\t/* Only set if a pool target is bound */\n"
        "\n"
        "\tstruct mapped_device *pool_md;\n",
        "\tstruct dm_target *ti;\t/* Only set if a pool target is bound */\n"
        "\n"
        "\tchar name[DM_NAME_LEN];\n\tdev_t dev;\n",
        "pool identity: stable table name and bound pool dev_t",
    )
    source.once(
        "\tbool suspended:1;\n",
        "\tbool suspended;\n",
        "suspend gate must support READ_ONCE",
    )
    source.once(
        "\tstruct mapped_device *thin_md;\n",
        "",
        "thin device carries no mapped-device reference",
    )
    source.all(
        "dm_device_name(pool->pool_md)",
        "pool->name",
        21,
        "pool name in diagnostics",
    )
    source.once(
        """/*
 * A global list of pools that uses a struct mapped_device as a key.
 */
""",
        """/*
 * A global list of pools keyed first by the control target's stable table
 * name, then by the pool block device dev_t once a thin opens that device.
 */
""",
        "pool table key documentation",
    )
    source.once(POOL_TABLE_LOOKUP_OLD, POOL_TABLE_LOOKUP_NEW, "pool table lookups")
    source.once(
        """	if (r && !op->parent_bio->bi_status)
		op->parent_bio->bi_status = errno_to_blk_status(r);
""",
        """	if (r && !op->parent_bio->bi_status)
		op->parent_bio->bi_status =
			r == -ENOSPC ? BLK_STS_NOSPC : BLK_STS_IOERR;
""",
        "discard completion status without errno_to_blk_status",
    )
    source.once(
        "static struct pool *pool_create(struct mapped_device *pool_md,\n",
        "static struct pool *pool_create(const char *name,\n",
        "pool_create identity argument",
    )
    source.once(
        "\tpool->pool_md = pool_md;\n",
        "\tstrscpy(pool->name, name, sizeof(pool->name));\n",
        "pool_create records the table name",
    )
    source.once(
        "static struct pool *__pool_find(struct mapped_device *pool_md,\n",
        "static struct pool *__pool_find(const char *name,\n",
        "__pool_find identity argument",
    )
    source.once(
        "\t\tif (pool->pool_md != pool_md) {\n",
        "\t\tif (strcmp(pool->name, name)) {\n",
        "__pool_find compares table names",
    )
    source.once(
        "\t\tpool = __pool_table_lookup(pool_md);\n",
        "\t\tpool = __pool_table_lookup_name(name);\n",
        "__pool_find name lookup",
    )
    source.once(
        "\t\t\tpool = pool_create(pool_md, metadata_dev, data_dev, block_size, read_only, error);\n",
        "\t\t\tpool = pool_create(name, metadata_dev, data_dev, block_size,\n"
        "\t\t\t\t\t   read_only, error);\n",
        "__pool_find create call",
    )
    source.once(
        """	pool = __pool_find(dm_table_get_md(ti->table), metadata_dev->bdev, data_dev->bdev,
			   block_size, pf.mode == PM_READ_ONLY, &ti->error, &pool_created);
""",
        """	pool = __pool_find(dm_table_device_name(ti->table), metadata_dev->bdev,
			   data_dev->bdev, block_size, pf.mode == PM_READ_ONLY,
			   &ti->error, &pool_created);
""",
        "pool_ctr binds the pool to the table name",
    )
    source.once(
        "\tthin_hook_bio(tc, bio);\n\n\tif (tc->requeue_mode) {\n",
        "\tthin_hook_bio(tc, bio);\n\n"
        "\tif (READ_ONCE(tc->pool->suspended)) {\n"
        "\t\tretry_on_resume(bio);\n"
        "\t\treturn DM_MAPIO_SUBMITTED;\n"
        "\t}\n\n"
        "\tif (tc->requeue_mode) {\n",
        "thin_bio_map honours the private suspend gate",
    )
    source.once(
        "static void pool_suspend_active_thins(struct pool *pool)\n"
        "{\n"
        "\tstruct thin_c *tc;\n"
        "\n"
        "\t/* Suspend all active thin devices */\n"
        "\ttc = get_first_thin(pool);\n"
        "\twhile (tc) {\n"
        "\t\tdm_internal_suspend_noflush(tc->thin_md);\n"
        "\t\ttc = get_next_thin(pool, tc);\n"
        "\t}\n"
        "}\n"
        "\n"
        "static void pool_resume_active_thins(struct pool *pool)\n"
        "{\n"
        "\tstruct thin_c *tc;\n"
        "\n"
        "\t/* Resume all active thin devices */\n"
        "\ttc = get_first_thin(pool);\n"
        "\twhile (tc) {\n"
        "\t\tdm_internal_resume(tc->thin_md);\n"
        "\t\ttc = get_next_thin(pool, tc);\n"
        "\t}\n"
        "}\n"
        "\n"
        "static void pool_resume(struct dm_target *ti)\n",
        SUSPEND_GATE_COMMENT + "static void pool_resume(struct dm_target *ti)\n",
        "replace recursive thin suspension with the private pool gate",
    )
    source.once(
        """	/*
	 * Must requeue active_thins' bios and then resume
	 * active_thins _before_ clearing 'suspend' flag.
	 */
	requeue_bios(pool);
	pool_resume_active_thins(pool);

	spin_lock_irq(&pool->lock);
	pool->low_water_triggered = false;
	pool->suspended = false;
	spin_unlock_irq(&pool->lock);

	do_waker(&pool->waker.work);
""",
        """	spin_lock_irq(&pool->lock);
	pool->low_water_triggered = false;
	pool->suspended = false;
	spin_unlock_irq(&pool->lock);

	requeue_bios(pool);
	do_waker(&pool->waker.work);
""",
        "pool_resume releases retained bios after the gate",
    )
    source.once(
        """	spin_lock_irq(&pool->lock);
	pool->suspended = true;
	spin_unlock_irq(&pool->lock);

	pool_suspend_active_thins(pool);
}
""",
        """	spin_lock_irq(&pool->lock);
	pool->suspended = true;
	spin_unlock_irq(&pool->lock);
}
""",
        "pool_presuspend closes the gate without DM suspend",
    )
    source.once(
        """	pool_resume_active_thins(pool);

	spin_lock_irq(&pool->lock);
	pool->suspended = false;
	spin_unlock_irq(&pool->lock);
}
""",
        """	spin_lock_irq(&pool->lock);
	pool->suspended = false;
	spin_unlock_irq(&pool->lock);
	requeue_bios(pool);
	wake_worker(pool);
}
""",
        "pool_presuspend_undo reopens the gate and requeues",
    )
    source.once(
        "\t\tif (!(status_flags & DM_STATUS_NOFLUSH_FLAG) && !dm_suspended(ti))\n",
        "\t\tif (!(status_flags & DM_STATUS_NOFLUSH_FLAG))\n",
        "pool_status commit without dm_suspended",
    )
    source.once(
        """	pool_md = dm_get_md(tc->pool_dev->bdev->bd_dev);
	if (!pool_md) {
		ti->error = "Couldn't get pool mapped device";
		r = -EINVAL;
		goto bad_common;
	}

	tc->pool = __pool_table_lookup(pool_md);
	if (!tc->pool) {
		ti->error = "Couldn't find pool object";
		r = -EINVAL;
		goto bad_pool_lookup;
	}
	__pool_inc(tc->pool);
""",
        THIN_CTR_LOOKUP_NEW,
        "thin_ctr resolves the pool through the private table",
    )
    source.once(
        "\tstruct mapped_device *pool_md;\n",
        "",
        "thin_ctr holds no mapped-device reference",
    )
    source.once(
        "\ttc->thin_md = dm_table_get_md(ti->table);\n",
        "",
        "thin_ctr does not capture the thin mapped device",
    )
    source.once(
        "\tsynchronize_rcu();\n\n\tdm_put(pool_md);\n\n\treturn 0;\n",
        "\tsynchronize_rcu();\n\n\treturn 0;\n",
        "thin_ctr success path drops the dm_put",
    )
    source.once(
        "bad_pool:\n\t__pool_dec(tc->pool);\nbad_pool_lookup:\n\tdm_put(pool_md);\nbad_common:\n",
        "bad_pool:\n\t__pool_dec(tc->pool);\nbad_common:\n",
        "thin_ctr failure path drops the dm_put",
    )
    source.once(
        """	if (dm_noflush_suspending(ti))
		noflush_work(tc, do_noflush_start);
""",
        """	noflush_work(tc, do_noflush_start);
""",
        "thin_presuspend starts the noflush work for both suspend kinds",
    )
    source.once(
        """	/*
	 * The dm_noflush_suspending flag has been cleared by now, so
	 * unfortunately we must always run this.
	 */
	noflush_work(tc, do_noflush_stop);
""",
        """	/* Pair the presuspend transition for both flush and noflush suspend. */
	noflush_work(tc, do_noflush_stop);
""",
        "thin_postsuspend documents the paired transition",
    )
    ensure_external_definition(source, "int __init dm_thin_init(void)\n",
                               "thin init linkage")
    source.once(
        """int __init dm_thin_init(void)
{
	int r = -ENOMEM;

	pool_table_init();

	_new_mapping_cache = KMEM_CACHE(dm_thin_new_mapping, 0);
""",
        """static bool private_names;
module_param(private_names, bool, 0444);
MODULE_PARM_DESC(private_names,
		 "register thin-private/thin-pool-private instead of upstream names");

int __init thinpool_private_thin_init(void)
{
	int r = -ENOMEM;

	pool_table_init();
	if (private_names) {
		thin_target.name = "thin-private";
		pool_target.name = "thin-pool-private";
	}

	_new_mapping_cache = kmem_cache_create("thin_private_mapping",
					      sizeof(struct dm_thin_new_mapping),
					      0, 0, NULL);
""",
        "thin subsystem init entry point and private slab name",
    )
    ensure_external_definition(source, "void dm_thin_exit(void)\n",
                               "thin exit linkage")
    source.once(
        "void dm_thin_exit(void)\n",
        "void thinpool_private_thin_exit(void)\n",
        "thin subsystem exit entry point",
    )
    source.once(
        "module_init(dm_thin_init);\nmodule_exit(dm_thin_exit);\n\n",
        "",
        "composed module carries no module_init or module_exit",
    )
    # The proven 6.12 vendor tree and upstream 6.18 both declare crypto
    # passthrough. dm-table.c drops inline-encryption capabilities for a
    # stacked device when a member target lacks the flag, and dm-thin keeps
    # the bio crypt context across remap. 6.1 upstream predates the flag, so
    # the port declares it there and asserts it elsewhere.
    if line == "6.1":
        source.once(
            "\t\t    DM_TARGET_IMMUTABLE,\n",
            "\t\t    DM_TARGET_IMMUTABLE | DM_TARGET_PASSES_CRYPTO,\n",
            "pool target passes inline-encryption bios",
        )
        source.once(
            'static struct target_type thin_target = {\n\t.name = "thin",\n',
            'static struct target_type thin_target = {\n\t.name = "thin",\n'
            "\t.features = DM_TARGET_PASSES_CRYPTO,\n",
            "thin target passes inline-encryption bios",
        )
        metadata_mode = (
            "\tmetadata_mode = FMODE_READ | "
            "((pf.mode == PM_READ_ONLY) ? 0 : FMODE_WRITE);\n"
        )
    else:
        metadata_mode = (
            "\tmetadata_mode = BLK_OPEN_READ |\n"
            "\t\t((pf.mode == PM_READ_ONLY) ? 0 : BLK_OPEN_WRITE);\n"
        )
    source.once(
        metadata_mode,
        ZERO_NEW_BLOCKS_POLICY + metadata_mode,
        "encrypted thin pools require skip_block_zeroing",
    )


def port_bufio(source: Source, line: str) -> None:
    source.once(
        "#include <linux/dm-bufio.h>\n",
        '#include "subsystems.h"\n#include <linux/dm-bufio.h>\n',
        "declare the shared subsystem entry points",
    )
    source.once(
        '#define DM_MSG_PREFIX "bufio"\n',
        bufio_private_helpers(line) + '\n#define DM_MSG_PREFIX "bufio"\n',
        "private block-layer helpers",
    )
    if line in INVAL_STATUS_LINES:
        require("return BLK_STS_INVAL;" in source.text,
                f"{source.path}: {line} defines BLK_STS_INVAL but the mapping omits it")
    else:
        source.forbid("BLK_STS_INVAL",
                      f"{line} has no BLK_STS_INVAL; the mapping must not name it")
    source.once(
        "\t\tb->end_io(b, errno_to_blk_status(r));\n",
        "\t\tb->end_io(b, thinpool_errno_to_blk_status(r));\n",
        "private errno mapping in the dm-io fallback",
    )
    source.once(
        "\tbio_uninit(bio);\n\tkfree(bio);\n",
        "\tbio_put(bio);\n",
        "bio_set completion frees with bio_put",
    )
    if line == "6.1":
        source.once(
            "\tbio = bio_kmalloc(vec_size, GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN);\n",
            "\tbio = bio_alloc_bioset(b->c->bdev, vec_size, op,\n"
            "\t\t\t       GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN,\n"
            "\t\t\t       &dm_bufio_bioset);\n",
            "use_bio allocates from the module bio_set",
        )
        source.once(
            "\tbio_init(bio, b->c->bdev, bio->bi_inline_vecs, vec_size, op);\n",
            "",
            "BIO_SET allocation is already initialized",
        )
    elif line == "6.18":
        source.once(
            "\tbio = bio_kmalloc(1, GFP_NOWAIT);\n",
            "\tbio = bio_alloc_bioset(b->c->bdev, 1, op, GFP_NOWAIT,\n"
            "\t\t\t       &dm_bufio_bioset);\n",
            "use_bio allocates from the module bio_set",
        )
        source.once(
            "\tbio_init_inline(bio, b->c->bdev, 1, op);\n",
            "",
            "bio_alloc_bioset already initializes the bio",
        )
    else:  # pragma: no cover - guarded by the profile table
        raise PortError(f"dm-bufio.c: no port programme for kernel line {line}")

    source.once(
        "static struct workqueue_struct *dm_bufio_wq;\n",
        "static struct workqueue_struct *dm_bufio_wq;\n"
        "static struct bio_set dm_bufio_bioset;\n",
        "module-owned bio_set declaration",
    )
    source.once(
        '\tdm_bufio_wq = alloc_workqueue("dm_bufio_cache",',
        "\tif (bioset_init(&dm_bufio_bioset, 16, 0, BIOSET_NEED_BVECS))\n"
        "\t\treturn -ENOMEM;\n"
        "\n"
        '\tdm_bufio_wq = alloc_workqueue("thin_private_bufio",',
        "module bio_set init and private workqueue name",
    )
    source.once(
        "\tif (!dm_bufio_wq)\n\t\treturn -ENOMEM;\n",
        "\tif (!dm_bufio_wq) {\n\t\tbioset_exit(&dm_bufio_bioset);\n"
        "\t\treturn -ENOMEM;\n\t}\n",
        "workqueue failure releases the module bio_set",
    )
    source.once(
        "\tdestroy_workqueue(dm_bufio_wq);\n",
        "\tdestroy_workqueue(dm_bufio_wq);\n\tbioset_exit(&dm_bufio_bioset);\n",
        "exit releases the module bio_set",
    )
    ensure_external_definition(source, "int __init dm_bufio_init(void)\n",
                               "bufio init linkage")
    source.once(
        "int __init dm_bufio_init(void)\n",
        "int __init thinpool_private_bufio_init(void)\n",
        "bufio init entry point is visible to the module entry point",
    )
    ensure_external_definition(source, "void __exit dm_bufio_exit(void)\n",
                               "bufio exit linkage")
    source.once(
        "void __exit dm_bufio_exit(void)\n",
        "void thinpool_private_bufio_exit(void)\n",
        "bufio exit entry point",
    )
    source.once(
        "module_init(dm_bufio_init)\nmodule_exit(dm_bufio_exit)\n\n",
        "",
        "composed module carries no module_init or module_exit",
    )


def port_kcopyd(source: Source, line: str) -> None:
    require_external_definition(source, "int __init dm_kcopyd_init(void)\n",
                                "kcopyd init linkage")
    require_external_definition(source, "void dm_kcopyd_exit(void)\n",
                                "kcopyd exit linkage")
    source.once(
        """static unsigned int dm_get_kcopyd_subjob_size(void)
{
	unsigned int sub_job_size_kb;

	sub_job_size_kb = __dm_get_module_param(&kcopyd_subjob_size_kb,
						DEFAULT_SUB_JOB_SIZE_KB,
						MAX_SUB_JOB_SIZE_KB);

	return sub_job_size_kb << 1;
}
""",
        """static unsigned int dm_get_kcopyd_subjob_size(void)
{
	unsigned int sub_job_size_kb = READ_ONCE(kcopyd_subjob_size_kb);

	return clamp(sub_job_size_kb, DEFAULT_SUB_JOB_SIZE_KB,
		     MAX_SUB_JOB_SIZE_KB) << 1;
}
""",
        "sub-job size without __dm_get_module_param",
    )


def port_dm_io(source: Source, line: str) -> None:
    require_external_definition(source, "int __init dm_io_init(void)\n",
                                "io init linkage")
    require_external_definition(source, "void dm_io_exit(void)\n",
                                "io exit linkage")
    source.once(
        "\t_dm_io_cache = KMEM_CACHE(io, 0);\n",
        "\t_dm_io_cache = kmem_cache_create(\"thin_private_io\",\n"
        "\t\t\t\t\t sizeof(struct io), 0, 0, NULL);\n",
        "private io slab name",
    )


def port_prison_v1(source: Source, line: str) -> None:
    source.once(
        '#include "dm.h"\n',
        '#include "subsystems.h"\n#include "dm.h"\n',
        "declare the shared subsystem entry points",
    )
    source.once(
        "\t_cell_cache = KMEM_CACHE(dm_bio_prison_cell, 0);\n",
        "\t_cell_cache = kmem_cache_create(\"thin_private_prison_cell\",\n"
        "\t\t\t\t\tsizeof(struct dm_bio_prison_cell),\n"
        "\t\t\t\t\t0, 0, NULL);\n",
        "private cell slab name",
    )
    ensure_external_definition(source, "int __init dm_bio_prison_init(void)\n",
                               "prison init linkage")
    source.once(
        "int __init dm_bio_prison_init(void)\n",
        "int __init thinpool_private_prison_init(void)\n",
        "prison init entry point",
    )
    ensure_external_definition(source, "void __exit dm_bio_prison_exit(void)\n",
                               "prison exit linkage")
    source.once(
        "void __exit dm_bio_prison_exit(void)\n",
        "void thinpool_private_prison_exit(void)\n",
        "prison exit entry point",
    )
    source.once(
        """/*
 * module hooks
 */
module_init(dm_bio_prison_init);
module_exit(dm_bio_prison_exit);

""",
        "",
        "composed module carries no module_init or module_exit",
    )


# (source path under src/, edit function) per kernel line.
PROGRAMMES = {
    "6.1": (
        ("dm-thin.c", port_thin),
        ("dm-bufio.c", port_bufio),
        ("dm-kcopyd.c", port_kcopyd),
        ("dm-io.c", port_dm_io),
        ("dm-bio-prison-v1.c", port_prison_v1),
    ),
    "6.18": (
        ("dm-thin.c", port_thin),
        ("dm-bufio.c", port_bufio),
        ("dm-kcopyd.c", port_kcopyd),
        ("dm-io.c", port_dm_io),
        ("dm-bio-prison-v1.c", port_prison_v1),
    ),
}


# ------------------------------------------------------------------- inputs

def kernel_version(source: Path) -> tuple[int, int, int]:
    text = (source / "Makefile").read_text()

    def field(name: str) -> str:
        match = re.search(rf"^{name}\s*=\s*(.*)$", text, re.MULTILINE)
        require(match is not None, f"{source}/Makefile has no {name} assignment")
        return match.group(1).strip()

    try:
        return int(field("VERSION")), int(field("PATCHLEVEL")), int(field("SUBLEVEL"))
    except ValueError as error:
        raise PortError(f"{source}/Makefile has a non-numeric kernel version") from error


def uts_release(output: Path) -> str | None:
    header = output / "include/generated/utsrelease.h"
    if not header.is_file():
        return None
    match = re.search(r'^#define UTS_RELEASE "(.*)"$', header.read_text(), re.MULTILINE)
    return match.group(1) if match else None


def source_identity(source: Path, branch: str, generation: int) -> dict[str, object]:
    """Read the ACK identity declarations the source actually carries.

    ``scripts/kmi_modules.py`` requires a declared KMI generation and branch.
    Not every GKI line declares them: android14-6.1 declares only ``BRANCH``.
    A declaration that exists must match the caller, and absence is recorded
    instead of invented, so a lane never claims an identity its source denies.
    """
    constants = "\n".join(
        (source / name).read_text() for name in IDENTITY_FILES if (source / name).is_file()
    )
    branches = set(re.findall(r"^BRANCH=[\"']?([a-z0-9.-]+)[\"']?\s*$", constants, re.MULTILINE))
    generations = {
        int(value)
        for value in re.findall(r"^KMI_GENERATION=[\"']?(\d+)[\"']?\s*$", constants, re.MULTILINE)
    }
    if branches:
        require(branches == {branch},
                f"kernel source declares branch {sorted(branches)}, not {branch}")
    if generations:
        require(generations == {generation},
                f"kernel source declares KMI generation {sorted(generations)}, "
                f"not {generation}")
    return {
        "branch_declared": sorted(branches),
        "generation_declared": sorted(generations),
    }


def validate_inputs(args: argparse.Namespace) -> tuple[Path, Path, str, tuple[int, int, int]]:
    source = Path(args.kernel_source).resolve(strict=True)
    output = Path(args.kernel_output).resolve(strict=True)
    require(source.is_dir(), f"kernel source is not a directory: {source}")
    require(output.is_dir(), f"kernel output is not a directory: {output}")
    for name in SOURCE_REQUIRED:
        require((source / name).is_file(), f"kernel source is incomplete: missing {name}")
    for name in OUTPUT_REQUIRED:
        require((output / name).is_file() and (output / name).stat().st_size,
                f"kernel output is incomplete: missing {name}")
    require((output / "include/generated/utsrelease.h").is_file(),
            "kernel output is incomplete: missing include/generated/utsrelease.h")

    version = kernel_version(source)
    line = f"{version[0]}.{version[1]}"
    release = uts_release(output)
    require(release is not None,
            "kernel output has no UTS_RELEASE in include/generated/utsrelease.h")
    require(release.startswith(f"{line}."),
            f"kernel output release {release} is not a {line} kernel")
    match = re.fullmatch(r"android\d+-(\d+\.\d+)", args.branch)
    require(match is not None, f"branch must be an exact ACK branch: {args.branch}")
    require(match.group(1) == line,
            f"branch {args.branch} does not match kernel source {line}")
    require(args.arch in ("aarch64", "x86_64"), f"unsupported architecture: {args.arch}")
    require(args.generation >= 0, "generation must be nonnegative")
    require(line in GENERATED_LINES or line in VERIFIED_LINES,
            f"unsupported kernel line {line}: no port programme (supported: "
            f"{', '.join(sorted(GENERATED_LINES | VERIFIED_LINES))})")
    if line in VERIFIED_LINES:
        proven = VERIFIED_BRANCH[line]
        require(args.branch == proven,
                f"the verified sources are proven for {proven}, not {args.branch}")
    if line in GENERATED_LINES:
        for name in DM_FILES:
            path = source / "drivers/md" / name
            require(path.is_file(), f"kernel source is incomplete: missing {path.name}")
        require((source / PERSISTENT_DATA_DIR).is_dir(),
                f"kernel source is incomplete: missing {PERSISTENT_DATA_DIR}")
    _ = source_identity(source, args.branch, args.generation)
    return source, output, line, version


def require_absent_target(target: Path) -> None:
    """This tool only creates a staged tree. It never replaces an existing path."""
    require(not target.exists(),
            f"target exists: {target}; remove it before staging")
    require(not target.parent.exists() or target.parent.is_dir(),
            f"staging parent is not a directory: {target.parent}")


# ----------------------------------------------------------------- staging

def stage_generated(source: Path, line: str, staged: Path) -> tuple[dict[str, str], dict[str, str], list[dict[str, object]]]:
    kernel_files: dict[str, str] = {}
    programme = dict(PROGRAMMES[line])
    edits: list[dict[str, object]] = []
    sources: dict[str, Source] = {}

    for name in DM_FILES:
        path = source / "drivers/md" / name
        kernel_files[f"drivers/md/{name}"] = digest(path)
        sources[f"src/{name}"] = Source(f"src/{name}", path.read_text())

    persistent = source / PERSISTENT_DATA_DIR
    persistent_files = sorted(
        path for path in persistent.iterdir() if path.suffix in (".c", ".h")
    )
    require(persistent_files, f"no persistent-data sources under {persistent}")
    for path in persistent_files:
        kernel_files[f"{PERSISTENT_DATA_DIR}/{path.name}"] = digest(path)
        sources[f"src/persistent-data/{path.name}"] = Source(
            f"src/persistent-data/{path.name}", path.read_text()
        )

    for name, port in programme.items():
        port(sources[f"src/{name}"], line)
        edits.extend(sources[f"src/{name}"].edits)

    for name, text in sources.items():
        check_declared_tokens(
            Source(name, text.text),
            FORBIDDEN_AFTER_PORT.get(name, ()),
            REQUIRED_AFTER_PORT.get(name, ()),
        )

    for name, item in sources.items():
        path = staged / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.text, newline="\n")
    # Project sources live in this module tree, not in the kernel source. The
    # generated sources include subsystems.h, so the staged tree must carry it.
    module_files: dict[str, str] = {}
    for name in PROJECT_HEADERS:
        project = MODULE_DIR / name
        require(project.is_file(), f"project header is missing: {project}")
        target = staged / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project, target)
        module_files[name] = digest(project)
    return kernel_files, module_files, edits


def stage_verified(staged: Path) -> dict[str, str]:
    module_files: dict[str, str] = {}
    for path in sorted((MODULE_DIR / "src").rglob("*")):
        if path.suffix not in (".c", ".h"):
            continue
        relative = path.relative_to(MODULE_DIR)
        target = staged / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        module_files[relative.as_posix()] = digest(path)
    return module_files


STAGED_MAKEFILE = """# SPDX-License-Identifier: GPL-2.0-only
# Generated by kernel/dm-thin-pool/prepare.py for a staged tree. The admitted
# build path is scripts/kmi_modules.py, which needs only Kbuild and the kernel
# source and output. This file builds the same Kbuild directly.
ifneq ($(KERNELRELEASE),)
include $(src)/Kbuild
else
KMI_SRC ?=
KMI_OUT ?=
KMI_ARCH ?= aarch64
ARCH_aarch64 := arm64
ARCH_x86_64 := x86_64
ARCH_MAPPED := $(ARCH_$(KMI_ARCH))
ifeq ($(strip $(ARCH_MAPPED)),)
$(error KMI_ARCH must be aarch64 or x86_64)
endif
.DEFAULT_GOAL := modules
.PHONY: modules clean
modules:
	@test -n "$(KMI_SRC)" -a -n "$(KMI_OUT)" || { echo "KMI_SRC and KMI_OUT are required" >&2; exit 2; }
	$(MAKE) -C "$(KMI_SRC)" O="$(KMI_OUT)" M="$(CURDIR)" ARCH="$(ARCH_MAPPED)" LLVM=1 KBUILD_GENDWARFKSYMS_STABLE=1 KBUILD_MODPOST_WARN=1 modules
clean:
	@test -n "$(KMI_SRC)" -a -n "$(KMI_OUT)" || { echo "KMI_SRC and KMI_OUT are required" >&2; exit 2; }
	$(MAKE) -C "$(KMI_SRC)" O="$(KMI_OUT)" M="$(CURDIR)" clean
endif
"""


def common_files(staged: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in ("Kbuild", "thin-main.c", "private-rename.h", "LICENSE"):
        source = MODULE_DIR / name
        target = staged / name
        shutil.copyfile(source, target)
        files[name] = digest(source)
    (staged / "Makefile").write_text(STAGED_MAKEFILE, newline="\n")
    files["Makefile"] = digest(staged / "Makefile")
    include = MODULE_DIR.parents[1] / "include" / "egysk_lkm.h"
    require(include.is_file(), f"repository include is missing: {include}")
    (staged / "include").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(include, staged / "include/egysk_lkm.h")
    files["include/egysk_lkm.h"] = digest(include)
    (staged / "stage.mk").write_text(
        "# Generated by prepare.py: staged module has its own include directory.\n"
        "THINPOOL_INCLUDE_DIR := $(src)/include\n",
        newline="\n",
    )
    return files


def private_rename_inventory(staged: Path) -> dict[str, object]:
    text = (staged / "private-rename.h").read_text()
    pairs = re.findall(r"^#define\s+(\S+)\s+(thinpool_private_\S+)$", text, re.MULTILINE)
    require(pairs, "private-rename.h defines no private renames")
    for original, private in pairs:
        require(private.startswith("thinpool_private_"),
                f"private-rename.h renames {original} outside the private namespace")
    sources = "\n".join(
        path.read_text() for path in sorted((staged / "src").rglob("*.c"))
    )
    unused = [original for original, _ in pairs if not re.search(rf"\b{re.escape(original)}\b", sources)]
    return {
        "renames": len(pairs),
        "private_rename_sha256": digest(staged / "private-rename.h"),
        "unused_renames": unused,
    }


def kbuild_members(staged: Path) -> set[str]:
    text = (staged / "Kbuild").read_text().replace("\\\n", " ")
    match = re.search(r"^dm-thin-pool-y\s*:=\s*(.*)$", text, re.MULTILINE)
    require(match is not None, "Kbuild has no dm-thin-pool-y member list")
    members = {token.strip() for token in match.group(1).split()}
    return {member.removesuffix(".o") + ".c" for member in members}


def check_exports_renamed(staged: Path) -> int:
    """Every symbol the staged DM family exports must be renamed.

    A module that exports a name the kernel also exports fails modpost.  The
    matching source decides the export set, and private-rename.h must cover it.
    """
    header = (staged / "private-rename.h").read_text()
    renames = {
        match.group(1)
        for match in re.finditer(r"^#define\s+(\S+)\s+thinpool_private_\S+$",
                                 header, re.MULTILINE)
    }
    exported: dict[str, str] = {}
    for path in sorted((staged / "src").rglob("*.c")):
        for match in re.finditer(r"^EXPORT_SYMBOL(?:_GPL)?\((\w+)\)",
                                 path.read_text(), re.MULTILINE):
            exported.setdefault(match.group(1), path.relative_to(staged).as_posix())
    missing = [name for name in sorted(exported) if name not in renames]
    require(
        not missing,
        "staged exports lack a private rename: "
        + ", ".join(f"{name} ({exported[name]})" for name in missing),
    )
    return len(exported)


def check_members(staged: Path) -> None:
    members = kbuild_members(staged)
    staged_sources = {
        path.relative_to(staged).as_posix() for path in (staged / "src").rglob("*.c")
    }
    staged_sources.add("thin-main.c")
    missing = members - staged_sources
    extra = staged_sources - members
    require(not missing, f"Kbuild compiles absent sources: {sorted(missing)}")
    require(not extra, f"staged sources absent from Kbuild: {sorted(extra)}")


def module_entry_points(staged: Path) -> dict[str, str]:
    entry_points: dict[str, str] = {}
    for path in sorted(staged.rglob("*")):
        if path.suffix not in (".c", ".h"):
            continue
        text = path.read_text()
        if "module_init(" in text or "module_exit(" in text:
            require(path.name == "thin-main.c",
                    f"module entry point outside thin-main.c: {path.name}")
    text = (staged / "thin-main.c").read_text()
    for symbol in ("thinpool_private_init", "thinpool_private_exit"):
        require(symbol in text, f"thin-main.c has no {symbol}")
    entry_points["thin-main.c"] = "module_init(thinpool_private_init)/module_exit(thinpool_private_exit)"
    return entry_points


def target_versions(staged: Path) -> dict[str, list[int]]:
    text = (staged / "src/dm-thin.c").read_text()
    versions: dict[str, list[int]] = {}
    for name in ("pool_target", "thin_target"):
        match = re.search(
            rf"static struct target_type {name} = \{{(.*?)\n\}};", text, re.DOTALL
        )
        require(match is not None, f"dm-thin.c has no {name} definition")
        version = re.search(r"\.version = \{(\d+), (\d+), (\d+)\}", match.group(1))
        require(version is not None, f"{name} has no version triple")
        versions[name] = [int(value) for value in version.groups()]
    return versions


def provenance(args: argparse.Namespace, source: Path, output: Path, line: str,
               version: tuple[int, int, int], staged: Path, profile: str,
               kernel_files: dict[str, str], module_inputs: dict[str, str],
               edits: list[dict[str, object]], exported_symbols: int) -> dict[str, object]:
    files = {
        path.relative_to(staged).as_posix(): digest(path)
        for path in sorted(staged.rglob("*"))
        if path.is_file() and path.name != "PROVENANCE.json"
    }
    output_files = {
        name: digest(output / name) for name in OUTPUT_REQUIRED
        if (output / name).is_file()
    }
    uts = uts_release(output)
    if uts is not None:
        output_files["include/generated/utsrelease.h"] = digest(
            output / "include/generated/utsrelease.h"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "module": MODULE_NAME,
        "profile": profile,
        "kmi": {"branch": args.branch, "generation": args.generation, "arch": args.arch},
        "kernel": {
            "line": line,
            "source_makefile_version": ".".join(str(part) for part in version),
            "release": uts,
            "identity": source_identity(source, args.branch, args.generation),
        },
        "inputs": {
            "kernel_source_files": kernel_files,
            "kernel_source_role": (
                "identity-reference" if profile == "verified" else "staged-input"
            ),
            "kernel_output_files": output_files,
        },
        "module_inputs": module_inputs,
        "files": files,
        "port": {
            "tool": "kernel/dm-thin-pool/prepare.py",
            "tool_sha256": digest(MODULE_DIR / "prepare.py"),
            "edits": edits,
            "replaced_kernel_helpers": REPLACED_HELPERS,
            "private_symbols": private_rename_inventory(staged),
            "exported_symbols_renamed": exported_symbols,
            "target_versions": target_versions(staged),
            "entry_points": module_entry_points(staged),
        },
        "assumptions": [
            "Sources, build output and branch name come from one kernel line; a mismatch fails here.",
            "The staged module is not built, admitted or loaded by this tool.",
            "Private imports are admitted by scripts/kmi_modules.py against the same kernel output.",
        ],
        "proof": (
            "ACK 6.12 build and device records: see PROVENANCE.md"
            if profile == "verified"
            else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage dm-thin-pool sources for one GKI kernel line."
    )
    parser.add_argument("--branch", required=True, help="exact ACK branch, for example android16-6.12")
    parser.add_argument("--generation", type=int, required=True, help="KMI generation of that branch")
    parser.add_argument("--arch", required=True, choices=("aarch64", "x86_64"))
    parser.add_argument("--kernel-source", required=True, help="matching kernel source tree")
    parser.add_argument("--kernel-output", required=True, help="complete matching kernel output tree")
    parser.add_argument("--output", required=True, help="staging directory to write")
    args = parser.parse_args(argv)

    temporary: Path | None = None
    try:
        source, output, line, version = validate_inputs(args)
        target = Path(args.output).resolve()
        require(target != MODULE_DIR.resolve(),
                "the staging output must not be this source directory")
        require_absent_target(target)
        # Additive: the caller names a fresh path, so a missing parent chain
        # is created here and nothing existing is touched.
        target.parent.mkdir(parents=True, exist_ok=True)
        # A unique sibling of the target, created by this invocation only.
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.prepare-", dir=target.parent)
        )
        staged = temporary

        if line in VERIFIED_LINES:
            module_files = stage_verified(staged)
            edits: list[dict[str, object]] = []
            kernel_files = {
                f"drivers/md/{name}": digest(source / "drivers/md" / name)
                for name in DM_FILES
            }
            profile = "verified"
        else:
            kernel_files, module_files, edits = stage_generated(source, line, staged)
            profile = "generated"

        common = common_files(staged)
        # Module inputs: the verified tree plus the shared files for 6.12, or
        # the project headers plus the shared files for a generated tree (its
        # device-mapper sources are kernel inputs).
        module_inputs = dict(module_files)
        module_inputs.update(common)
        check_members(staged)
        exported_symbols = check_exports_renamed(staged)
        record = provenance(args, source, output, line, version, staged, profile,
                            kernel_files, module_inputs, edits, exported_symbols)
        (staged / "PROVENANCE.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", newline="\n"
        )
        temporary.rename(target)
        temporary = None
    except (PortError, OSError) as error:
        if temporary is not None:
            # Remove only the directory this invocation created.
            shutil.rmtree(temporary, ignore_errors=True)
        print(f"prepare: {error}", file=sys.stderr)
        return 2

    print(f"prepare: {target} ({profile} profile, kernel line {line})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

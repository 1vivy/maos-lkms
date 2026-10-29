# SPDX-License-Identifier: GPL-2.0-only
"""ABI port data for the 6.1 kernel line.

``prepare.py`` applies the shared edit programme.  This file holds only the
real 6.1 differences: the kernel sources the programme edits, the edits the
6.1 source needs, and the constants those edits depend on.  Each edit is an
exact ``(old, new, what)`` triple.  The shared programme applies it once.
"""

LINE = "6.1"
PROFILE = "generated"
VERIFIED_BRANCH = None

# Edited kernel sources, in programme order.
SOURCES = (
    "dm-thin.c",
    "dm-bufio.c",
    "dm-kcopyd.c",
    "dm-io.c",
    "dm-bio-prison-v1.c",
)

# 6.1 opens the metadata device with FMODE_READ/FMODE_WRITE.  It has no
# BLK_OPEN_READ/BLK_OPEN_WRITE open flags.
METADATA_MODE = (
    "\tmetadata_mode = FMODE_READ | "
    "((pf.mode == PM_READ_ONLY) ? 0 : FMODE_WRITE);\n"
)

# 6.1 names the pool through pool_md at every dm_device_name() site.  It has no
# discard path that names it through tc->pool.
POOL_NAME_TC_USES = 0

# 6.1 dm-table.c drops inline-encryption capabilities for a stacked device
# when a member target lacks DM_TARGET_PASSES_CRYPTO.  The thin data path
# keeps the bio crypt context.  The 6.1 source predates the flag, so the
# programme adds it to both targets.
THIN_CRYPTO_EDITS = (
    (
        "\t\t    DM_TARGET_IMMUTABLE,\n",
        "\t\t    DM_TARGET_IMMUTABLE | DM_TARGET_PASSES_CRYPTO,\n",
        "pool target passes inline-encryption bios",
    ),
    (
        'static struct target_type thin_target = {\n\t.name = "thin",\n',
        'static struct target_type thin_target = {\n\t.name = "thin",\n'
        "\t.features = DM_TARGET_PASSES_CRYPTO,\n",
        "thin target passes inline-encryption bios",
    ),
)

# 6.1 blk_errors[] maps -EINVAL to BLK_STS_IOERR and has no BLK_STS_INVAL
# entry, so the private mapping must not name that status.
BUFIO_ERRNO_INVAL_CASE = ""
BUFIO_ERRNO_REQUIRES_INVAL = False

# 6.1 defines BLK_STS_OFFLINE (5.17 and later) and test_bit_acquire.
BLK_STS_OFFLINE_AVAILABLE = True
BUFIO_USES_TEST_BIT_ACQUIRE = True

# 6.1 dm-bufio allocates with bio_kmalloc() and initializes with bio_init().
BUFIO_BIO_ALLOC_EDITS = (
    (
        "\tbio = bio_kmalloc(vec_size, GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN);\n",
        "\tbio = bio_alloc_bioset(b->c->bdev, vec_size, op,\n"
        "\t\t\t       GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN,\n"
        "\t\t\t       &dm_bufio_bioset);\n",
        "use_bio allocates from the module bio_set",
    ),
    (
        "\tbio_init(bio, b->c->bdev, bio->bi_inline_vecs, vec_size, op);\n",
        "",
        "BIO_SET allocation is already initialized",
    ),
)

# 6.1 frees the module bio_set allocation with bio_uninit()/kfree().  The
# module bio_set must release it with bio_put() instead.
BUFIO_BIO_COMPLETION_EDITS = (
    (
        "\tbio_uninit(bio);\n\tkfree(bio);\n",
        "\tbio_put(bio);\n",
        "bio_set completion frees with bio_put",
    ),
)

# 6.1 declares the sub-job size in `unsigned int`.
KCOPYD_SUBJOB_TYPE = "unsigned int"

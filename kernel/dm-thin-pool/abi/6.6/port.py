# SPDX-License-Identifier: GPL-2.0-only
"""ABI port data for the 6.6 kernel line.

``prepare.py`` applies the shared edit programme.  This file holds only the
real 6.6 differences: the kernel sources the programme edits, the edits the
6.6 source needs, and the constants those edits depend on.  Each edit is an
exact ``(old, new, what)`` triple.  The shared programme applies it once.
"""

LINE = "6.6"
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

# 6.6 opens the metadata device with BLK_OPEN_READ/BLK_OPEN_WRITE.
METADATA_MODE = (
    "\tmetadata_mode = BLK_OPEN_READ |\n"
    "\t\t((pf.mode == PM_READ_ONLY) ? 0 : BLK_OPEN_WRITE);\n"
)

# 6.6 names the pool through pool_md at every dm_device_name() site.
POOL_NAME_TC_USES = 0

# 6.6 dm-table.c drops inline-encryption capabilities for a stacked device
# when a member target lacks DM_TARGET_PASSES_CRYPTO.  The thin data path
# keeps the bio crypt context.  The 6.6 source does not set the flag, so the
# programme adds it to both targets; include/linux/device-mapper.h defines it.
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

# 6.6 include/linux/blk_types.h has BLK_STS_OFFLINE but no BLK_STS_INVAL; its
# blk_errors[] maps -ENODEV to BLK_STS_OFFLINE and -EINVAL to BLK_STS_IOERR.
BUFIO_ERRNO_INVAL_CASE = ""
BUFIO_ERRNO_REQUIRES_INVAL = False
BLK_STS_OFFLINE_AVAILABLE = True

# 6.6 waits with test_bit_acquire().
BUFIO_USES_TEST_BIT_ACQUIRE = True

# 6.6 dm-bufio allocates with one-vector bio_kmalloc() and initializes with
# bio_init().  bio_alloc_bioset() initializes the bio itself.
BUFIO_BIO_ALLOC_EDITS = (
    (
        "\tbio = bio_kmalloc(1, GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN);\n",
        "\tbio = bio_alloc_bioset(b->c->bdev, 1, op, GFP_NOWAIT,\n"
        "\t\t\t       &dm_bufio_bioset);\n",
        "use_bio allocates from the module bio_set",
    ),
    (
        "\tbio_init(bio, b->c->bdev, bio->bi_inline_vecs, 1, op);\n",
        "",
        "bio_alloc_bioset already initializes the bio",
    ),
)

# 6.6 frees the module bio_set allocation with bio_uninit()/kfree().
BUFIO_BIO_COMPLETION_EDITS = (
    (
        "\tbio_uninit(bio);\n\tkfree(bio);\n",
        "\tbio_put(bio);\n",
        "bio_set completion frees with bio_put",
    ),
)

# 6.6 declares the sub-job size in `unsigned int`.
KCOPYD_SUBJOB_TYPE = "unsigned int"

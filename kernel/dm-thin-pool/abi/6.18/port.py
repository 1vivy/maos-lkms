# SPDX-License-Identifier: GPL-2.0-only
"""ABI port data for the 6.18 kernel line.

``prepare.py`` applies the shared edit programme.  This file holds only the
real 6.18 differences: the kernel sources the programme edits, the edits the
6.18 source needs, and the constants those edits depend on.  Each edit is an
exact ``(old, new, what)`` triple.  The shared programme applies it once.
"""

LINE = "6.18"
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

# 6.18 opens the metadata device with BLK_OPEN_READ/BLK_OPEN_WRITE.
METADATA_MODE = (
    "\tmetadata_mode = BLK_OPEN_READ |\n"
    "\t\t((pf.mode == PM_READ_ONLY) ? 0 : BLK_OPEN_WRITE);\n"
)

# 6.18 names the pool through pool_md at every dm_device_name() site.
POOL_NAME_TC_USES = 0

# Upstream 6.18 already declares DM_TARGET_PASSES_CRYPTO on both targets.
# The shared REQUIRED_AFTER_PORT check asserts both flags survive staging, so
# this line needs no edit.
THIN_CRYPTO_EDITS = ()

# 6.18 blk_errors[] has BLK_STS_INVAL, so -EINVAL maps to it.
BUFIO_ERRNO_INVAL_CASE = "\tcase -EINVAL:\n\t\treturn BLK_STS_INVAL;\n"
BUFIO_ERRNO_REQUIRES_INVAL = True

# 6.18 defines BLK_STS_OFFLINE and test_bit_acquire.
BLK_STS_OFFLINE_AVAILABLE = True
BUFIO_USES_TEST_BIT_ACQUIRE = True

# 6.18 dm-bufio allocates with one-vector bio_kmalloc() and initializes with
# bio_init_inline().  bio_alloc_bioset() initializes the bio itself.
BUFIO_BIO_ALLOC_EDITS = (
    (
        "\tbio = bio_kmalloc(1, GFP_NOWAIT);\n",
        "\tbio = bio_alloc_bioset(b->c->bdev, 1, op, GFP_NOWAIT,\n"
        "\t\t\t       &dm_bufio_bioset);\n",
        "use_bio allocates from the module bio_set",
    ),
    (
        "\tbio_init_inline(bio, b->c->bdev, 1, op);\n",
        "",
        "bio_alloc_bioset already initializes the bio",
    ),
)

# 6.18 frees the module bio_set allocation with bio_uninit()/kfree().
BUFIO_BIO_COMPLETION_EDITS = (
    (
        "\tbio_uninit(bio);\n\tkfree(bio);\n",
        "\tbio_put(bio);\n",
        "bio_set completion frees with bio_put",
    ),
)

# 6.18 declares the sub-job size in `unsigned int`.
KCOPYD_SUBJOB_TYPE = "unsigned int"

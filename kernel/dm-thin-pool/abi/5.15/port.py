# SPDX-License-Identifier: GPL-2.0-only
"""ABI port data for the 5.15 kernel line.

``prepare.py`` applies the shared edit programme.  This file holds only the
real 5.15 differences: the kernel sources the programme edits, the edits the
5.15 source needs, and the constants those edits depend on.  Each edit is an
exact ``(old, new, what)`` triple.  The shared programme applies it once.
"""

LINE = "5.15"
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

# 5.15 opens the metadata device with FMODE_READ/FMODE_WRITE.  It has no
# BLK_OPEN_READ/BLK_OPEN_WRITE open flags.
METADATA_MODE = (
    "\tmetadata_mode = FMODE_READ | "
    "((pf.mode == PM_READ_ONLY) ? 0 : FMODE_WRITE);\n"
)

# The 5.15 discard passdown warning names the pool through tc->pool.
POOL_NAME_TC_USES = 1

# 5.15 dm-table.c drops inline-encryption capabilities for a stacked device
# when a member target lacks DM_TARGET_PASSES_CRYPTO.  The thin data path
# keeps the bio crypt context.  The 5.15 source does not set the flag, so the
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

# 5.15 include/linux/blk_types.h has no BLK_STS_INVAL and no BLK_STS_OFFLINE;
# its blk_errors[] maps -EINVAL and -ENODEV to BLK_STS_IOERR.
BUFIO_ERRNO_INVAL_CASE = ""
BUFIO_ERRNO_REQUIRES_INVAL = False
BLK_STS_OFFLINE_AVAILABLE = False

# 5.15 wait_bit.h tests the bit with test_bit(); test_bit_acquire() does not
# exist in this line.
BUFIO_USES_TEST_BIT_ACQUIRE = False

# 5.15 bio_alloc_bioset() takes (gfp, nr_iovecs, bio_set) and sets no bdev or
# op.  The source already calls bio_set_dev() and bio_set_op_attrs() after the
# allocation, so only the allocator changes.  bio_kmalloc() initializes the
# bio itself, so there is no bio_init() call to drop.
BUFIO_BIO_ALLOC_EDITS = (
    (
        "\tbio = bio_kmalloc(GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN, vec_size);\n",
        "\tbio = bio_alloc_bioset(GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN,\n"
        "\t\t\t       vec_size, &dm_bufio_bioset);\n",
        "use_bio allocates from the module bio_set",
    ),
)

# 5.15 bio_complete() already releases the bio with bio_put().
BUFIO_BIO_COMPLETION_EDITS = ()

# 5.15 declares the sub-job size in `unsigned`.
KCOPYD_SUBJOB_TYPE = "unsigned"

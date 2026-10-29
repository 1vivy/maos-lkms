# SPDX-License-Identifier: GPL-2.0-only
"""ABI port data for the Android 12 5.10 kernel line.

The counted shared programme matches the exact android12-5.10 5.10.252
sources.  These declarations describe actual pre-5.15 APIs, not simulated
version macros.  Source staging does not establish build or runtime admission.
"""

LINE = "5.10"
PROFILE = "generated"
VERIFIED_BRANCH = None

SOURCES = (
    "dm-thin.c",
    "dm-bufio.c",
    "dm-kcopyd.c",
    "dm-io.c",
    "dm-bio-prison-v1.c",
)

# The metadata device uses fmode_t, before BLK_OPEN_READ/BLK_OPEN_WRITE.
METADATA_MODE = (
    "\tmetadata_mode = FMODE_READ | "
    "((pf.mode == PM_READ_ONLY) ? 0 : FMODE_WRITE);\n"
)
POOL_NAME_TC_USES = 1

# This ACK defines DM_TARGET_PASSES_CRYPTO and dm-table.c intersects the
# stacked keyslot manager's capabilities only for targets carrying it.
# dm-thin's remap paths retain the original bio and its crypt context.
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

# block/blk-core.c maps unrecognized -EINVAL and -ENODEV to BLK_STS_IOERR;
# include/linux/blk_types.h defines neither INVAL nor OFFLINE in this ACK.
BUFIO_ERRNO_INVAL_CASE = ""
BUFIO_ERRNO_REQUIRES_INVAL = False
BLK_STS_OFFLINE_AVAILABLE = False

# wait_bit.h uses test_bit(), not the later test_bit_acquire().
BUFIO_USES_TEST_BIT_ACQUIRE = False

# bio_kmalloc() itself delegates to the three-argument bio_alloc_bioset()
# with a NULL pool.  Preserve the existing subsequent device/op setup and
# bio_put() on completion and bio_add_page() failure, using our owned pool.
BUFIO_BIO_ALLOC_EDITS = (
    (
        "\tbio = bio_kmalloc(GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN, vec_size);\n",
        "\tbio = bio_alloc_bioset(GFP_NOWAIT | __GFP_NORETRY | __GFP_NOWARN,\n"
        "\t\t\t       vec_size, &dm_bufio_bioset);\n",
        "use_bio allocates from the module bio_set",
    ),
)
BUFIO_BIO_COMPLETION_EDITS = ()

KCOPYD_SUBJOB_TYPE = "unsigned"

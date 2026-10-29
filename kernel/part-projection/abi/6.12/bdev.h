/* SPDX-License-Identifier: GPL-2.0-only */
/* android16-6.12 block-device port.
 *
 * 6.12 uses the file-based open interface. Recorded DDK input:
 * ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee.
 * No 6.12-specific quirk remains, so the port reuses the shared file-based
 * implementation. */
#ifndef PART_PROJECTION_ABI_6_12_BDEV_H
#define PART_PROJECTION_ABI_6_12_BDEV_H

#define PP_BDEV_ABI_LINE "6.12"

#include "../file-bdev.h"

#endif /* PART_PROJECTION_ABI_6_12_BDEV_H */

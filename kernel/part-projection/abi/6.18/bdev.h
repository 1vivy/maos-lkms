/* SPDX-License-Identifier: GPL-2.0-only */
/* android17-6.18 block-device port.
 *
 * 6.18 keeps the file-based open interface of 6.12. Recorded DDK input:
 * ghcr.io/ylarod/ddk-min@sha256:fb8b66200bf402cf65a751060fc1aa29524b9fa8840feef16c7b196a4f3f0e6e.
 * No 6.18-specific quirk remains in this boundary, so the port reuses the
 * shared file-based implementation. Keep it as a separate port because the
 * line has its own provenance and admission record. */
#ifndef PART_PROJECTION_ABI_6_18_BDEV_H
#define PART_PROJECTION_ABI_6_18_BDEV_H

#define PP_BDEV_ABI_LINE "6.18"

#include "../file-bdev.h"

#endif /* PART_PROJECTION_ABI_6_18_BDEV_H */

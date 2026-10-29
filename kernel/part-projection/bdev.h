/* SPDX-License-Identifier: GPL-2.0-only */
/* Block-device ABI selection for the pinned DDK kernel lines.
 *
 * The functional core (configfs.c, target.c) uses only the pp_bdev_* and
 * pp_disk_openers() interface below. Each supported kernel line has its own
 * port under abi/: that port owns the open, close, handle type, read-only
 * mechanism and open-count accessor of its line, and states the line it
 * applies to. This file selects a port from the version of the kernel headers
 * being built against. It does not translate one line's code for another line,
 * and it refuses lines that nobody ported, so an unported tree fails at compile
 * time instead of silently using a wrong interface.
 *
 * Supported lines: 5.15, 6.1, 6.6, 6.12, 6.18. */
#ifndef PART_PROJECTION_BDEV_H
#define PART_PROJECTION_BDEV_H

#include <linux/version.h>

#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 15, 0) && LINUX_VERSION_CODE < KERNEL_VERSION(5, 16, 0)
#include "abi/5.15/bdev.h"
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(6, 1, 0) && LINUX_VERSION_CODE < KERNEL_VERSION(6, 2, 0)
#include "abi/6.1/bdev.h"
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(6, 6, 0) && LINUX_VERSION_CODE < KERNEL_VERSION(6, 7, 0)
#include "abi/6.6/bdev.h"
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(6, 12, 0) && LINUX_VERSION_CODE < KERNEL_VERSION(6, 13, 0)
#include "abi/6.12/bdev.h"
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(6, 18, 0) && LINUX_VERSION_CODE < KERNEL_VERSION(6, 19, 0)
#include "abi/6.18/bdev.h"
#else
#error "part-projection: no block-device port for this kernel line; supported lines are 5.15, 6.1, 6.6, 6.12 and 6.18"
#endif

#endif /* PART_PROJECTION_BDEV_H */

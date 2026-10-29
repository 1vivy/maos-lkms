/* SPDX-License-Identifier: GPL-2.0-only */
/* Block-device ABI selection for the pinned DDK kernel lines.
 *
 * The functional core (configfs.c, target.c) uses only the pp_bdev_*,
 * pp_disk_*, pp_part_* and pp_for_each_part() interface below. Each supported
 * kernel line has its own port under abi/: that port owns the open, close,
 * handle type, read-only mechanism, open-count accessor, disk serialization
 * mutex, deadness test, partition-scan controls and partition iteration of its
 * line, and states the line it applies to. This file selects a port from the
 * version of the kernel headers being built against. It does not translate one
 * line's code for another line, and it refuses lines that nobody ported, so an
 * unported tree fails at compile time instead of silently using a wrong
 * interface.
 *
 * Port interface:
 *   pp_bdev_handle, PP_OPEN_READ, pp_bdev_open_ro(), pp_bdev_close(), pp_bdev()
 *   pp_bdev_info(), pp_bdev_dev()
 *   pp_disk_ref, pp_disk_hold(), pp_disk_drop(), pp_disk_lock(),
 *   pp_disk_unlock(), pp_disk_openers(), pp_disk_dead()
 *   pp_scan_state, pp_disk_scan_suppressed(), pp_disk_scan_save(),
 *   pp_disk_scan_restore(), pp_disk_scan_enable()
 *   pp_part_ref, pp_part_hold(), pp_part_put(), pp_part_read_only(),
 *   pp_part_ro(), pp_for_each_part()
 *
 * Supported lines: 5.10, 5.15, 6.1, 6.6, 6.12, 6.18. */
#ifndef PART_PROJECTION_BDEV_H
#define PART_PROJECTION_BDEV_H

#include <linux/version.h>

#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0) && LINUX_VERSION_CODE < KERNEL_VERSION(5, 11, 0)
#include "abi/5.10/bdev.h"
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(5, 15, 0) && LINUX_VERSION_CODE < KERNEL_VERSION(5, 16, 0)
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
#error "part-projection: no block-device port for this kernel line; supported lines are 5.10, 5.15, 6.1, 6.6, 6.12 and 6.18"
#endif

#endif /* PART_PROJECTION_BDEV_H */

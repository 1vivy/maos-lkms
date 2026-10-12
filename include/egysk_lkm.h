/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef EGYSK_LKM_H
#define EGYSK_LKM_H
#include <linux/module.h>
/* Descriptive build/load metadata, never authorization or a readiness shortcut. */
#define EGYSK_LKM_METADATA(name, version, abi, critical) \
	MODULE_INFO(egysk_name, name); \
	MODULE_INFO(egysk_version, version); \
	MODULE_INFO(egysk_abi, abi); \
	MODULE_INFO(egysk_critical, critical)
/* Reset to false at init; publish true only after the owned operation succeeds. */
#define EGYSK_LKM_READY_PARAM(value) \
	module_param(value, bool, 0444); \
	MODULE_PARM_DESC(value, "owned operation complete (read-only)")
#endif

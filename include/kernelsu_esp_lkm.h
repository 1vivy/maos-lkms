/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef KERNELSU_ESP_LKM_H
#define KERNELSU_ESP_LKM_H
#include <linux/module.h>
/* Descriptive build/load receipts, never authorization or a readiness shortcut. */
#define KERNELSU_ESP_LKM_METADATA(name, version, abi, critical) \
	MODULE_INFO(kernelsu_esp_name, name); \
	MODULE_INFO(kernelsu_esp_version, version); \
	MODULE_INFO(kernelsu_esp_abi, abi); \
	MODULE_INFO(kernelsu_esp_critical, critical)
/* Reset to false at init; publish true only after the owned operation succeeds. */
#define KERNELSU_ESP_LKM_READY_PARAM(value) \
	module_param(value, bool, 0444); \
	MODULE_PARM_DESC(value, "owned operation complete (read-only)")
#endif

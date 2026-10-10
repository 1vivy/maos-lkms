/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PART_PROJECTION_INTERNAL_H
#define PART_PROJECTION_INTERNAL_H
/* Private construction snapshot; not a userspace wire structure. */
#define GPT_ABI_VERSION 3U
#define GPT_MAX_PROJECTIONS 128U
#define GPT_MAX_HIDDEN 256U
#define GPT_LABEL_BYTES 36U
#define GPT_APPLY_FLAG_SEAL 1U
struct gpt_projection {
	u32 major, minor;
	u8 read_only, reserved[7];
	char name[GPT_LABEL_BYTES + 1];
	u8 reserved2[3];
};
struct gpt_device { u32 major, minor; };
struct gpt_apply {
	u32 version, count, hide_count, flags;
	struct gpt_projection projections[GPT_MAX_PROJECTIONS];
	struct gpt_device hide[GPT_MAX_HIDDEN];
};
#endif

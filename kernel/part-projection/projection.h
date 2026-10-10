/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PART_PROJECTION_INTERNAL_H
#define PART_PROJECTION_INTERNAL_H
int pp_metadata_copy(void *dest, unsigned int sector, unsigned int count, unsigned int *lbs);
int pp_target_init(void);
void pp_target_exit(void);
#endif

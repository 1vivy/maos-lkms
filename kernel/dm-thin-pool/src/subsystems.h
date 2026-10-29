/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef THINPOOL_SUBSYSTEMS_H
#define THINPOOL_SUBSYSTEMS_H

/* Shared by the composed module entry point and its subsystem definitions. */
int thinpool_private_dm_io_init(void);
void thinpool_private_dm_io_exit(void);
int dm_kcopyd_init(void);
void dm_kcopyd_exit(void);
int thinpool_private_bufio_init(void);
void thinpool_private_bufio_exit(void);
int thinpool_private_prison_init(void);
void thinpool_private_prison_exit(void);
int thinpool_private_thin_init(void);
void thinpool_private_thin_exit(void);

#endif

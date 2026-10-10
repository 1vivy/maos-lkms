#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# The explicit KMI_BRANCH/KMI_GENERATION/KMI_ARCH identify prepared build artifacts.
set -eu
MODULE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec make -C "$MODULE_DIR" KMI_SRC="${KMI_SRC:?}" KMI_OUT="${KMI_OUT:?}" \
	KMI_BRANCH="${KMI_BRANCH:?}" KMI_GENERATION="${KMI_GENERATION:?}" \
	KMI_ARCH="${KMI_ARCH:?}" JOBS="${JOBS:-13}" modules

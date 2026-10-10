# SPDX-License-Identifier: GPL-2.0-only
ifneq ($(KERNELRELEASE),)
include $(src)/Kbuild
else
.DEFAULT_GOAL := modules
PHONE_MODULE := dm-thin-pool
include ../../scripts/phone-module.mk
endif

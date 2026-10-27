#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Exact prepared ACK/DDK inputs; never synthesize CRCs or skip exact admission.
set -eu
if [ "$#" -ne 5 ]; then
    echo "usage: $0 branch generation aarch64|x86_64 kernel-source kernel-output" >&2
    exit 2
fi
branch=$1
generation=$2
arch=$3
source=$4
output=$5
case "$arch" in aarch64|x86_64) ;; *) echo "invalid architecture: $arch" >&2; exit 2 ;; esac
if [ ! -d "$source" ] || [ ! -r "$source/Makefile" ]; then
    echo "prepared kernel source required: $source (missing readable Makefile)" >&2
    exit 2
fi
if [ ! -d "$output" ]; then
    echo "complete matching kernel output required: $output (directory is missing)" >&2
    exit 2
fi
for input in Module.symvers System.map include/generated/utsrelease.h .config; do
    if [ ! -s "$output/$input" ]; then
        echo "complete matching kernel output required: $output/$input" >&2
        exit 2
    fi
done
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
# One engine archive for the bridge and standalone lanes; the source default
# would build a second copy inside the materialized tree.
EFVS_CARGO_TARGET_DIR=$root/out/linux-cargo
export EFVS_CARGO_TARGET_DIR
python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from scripts.kmi_modules import kmi_identity; kmi_identity(Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]))' "$root" "$source" "$branch" "$generation"
# The freestanding engine uses its pinned nightly and rust-src, not CONFIG_RUST.
# Fetch locked dependencies explicitly before its offline Kbuild invocation.
python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from scripts.kmi_modules import efvs_source; efvs_source(Path(sys.argv[1]) / "kernel/efivar_store")' "$root"
"${CARGO:-$HOME/.cargo/bin/cargo}" +nightly-2026-08-08 fetch --locked --manifest-path "$root/kernel/efivar_store/.source/Cargo.toml"
destination=$root/out/modules/$branch-$generation/$arch
rm -rf "$destination"
for module in dm-thin-pool part-projection efivarfs efivar_store; do
    directory=$root/kernel/$module
    module_destination=$destination/$module
    mkdir -p "$module_destination"
    python3 "$root/scripts/kmi_modules.py" build --module-dir "$directory" --module "$module" \
        --branch "$branch" --generation "$generation" --arch "$arch" \
        --kmi-src "$source" --kmi-out "$output" --output-dir "$module_destination" \
        --jobs "${JOBS:-4}"
    # Verify the exact shipped bytes; do not strip after admission.
    python3 "$root/scripts/kmi_modules.py" verify --branch "$branch" --generation "$generation" \
        --arch "$arch" --kmi-out "$output" --module "$module_destination/$module.ko"
done
# Exercise the pinned source's standalone Kbuild too, including the x86_64
# freestanding target in that matrix lane; the product bridge is not its only path.
standalone_destination=$root/out/standalone/$branch-$generation/$arch/efivar_store
rm -rf "$standalone_destination"
mkdir -p "$standalone_destination"
python3 "$root/scripts/kmi_modules.py" build \
    --module-dir "$root/kernel/efivar_store/.source/linux" --module efivar_store \
    --branch "$branch" --generation "$generation" --arch "$arch" \
    --kmi-src "$source" --kmi-out "$output" --output-dir "$standalone_destination" \
    --jobs "${JOBS:-4}"
python3 "$root/scripts/kmi_modules.py" verify \
    --module "$standalone_destination/efivar_store.ko" \
    --branch "$branch" --generation "$generation" --arch "$arch" --kmi-out "$output"

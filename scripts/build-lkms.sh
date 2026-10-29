#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Build requested modules against exact prepared source and output.
set -eu
if [ "$#" -lt 5 ]; then
    echo "usage: $0 branch generation aarch64|x86_64 kernel-source kernel-output [module ...]" >&2
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
. "$root/scripts/out-dir.sh"
select_out_dir "$root"
out_root=$OUT_DIR
if [ "$#" -eq 5 ]; then
    full_set=1
    set -- "$branch" "$generation" "$arch" "$source" "$output" \
        dm-thin-pool part-projection efivarfs efivar_store
else
    full_set=0
fi
shift 5
requested=
seen=' '
count=0
for module do
    case "$module" in dm-thin-pool|part-projection|efivarfs|efivar_store) ;; *)
        echo "unknown module: $module" >&2
        exit 2
        ;;
    esac
    case "$seen" in *" $module "*)
        echo "duplicate module request: $module" >&2
        exit 2
        ;;
    esac
    seen="$seen$module "
    requested="${requested}${requested:+,}$module"
    count=$((count + 1))
done
[ "$count" -gt 0 ] || { echo "no modules requested" >&2; exit 2; }
if [ "$count" -eq 4 ]; then full_set=1; fi
clang_version=$(python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from scripts.kmi_modules import clang_version; print(clang_version(Path(sys.argv[2])))' "$root" "$source")
clang_dir=${DDK_CLANG_DIR:-$out_root/ddk/clang/clang-$clang_version/bin}
if [ ! -x "$clang_dir/clang" ] || [ ! -x "$clang_dir/ld.lld" ]; then
    echo "matching DDK clang $clang_version required at $clang_dir (run sh scripts/bootstrap-ddk-clang.sh $branch $generation, or set DDK_CLANG_DIR)" >&2
    exit 2
fi
PATH=$clang_dir:$PATH
export PATH
unset CROSS_COMPILE
echo "compiler: $("$clang_dir/clang" --version | head -n 1)" >&2
python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from scripts.kmi_modules import kmi_identity; kmi_identity(Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]))' "$root" "$source" "$branch" "$generation"
EFVS_CARGO_TARGET_DIR=$out_root/linux-cargo
if [ -n "${EFIVAR_STORE_REPO:-}" ] && [ -d "$EFIVAR_STORE_REPO" ]; then
    EFVS_SOURCE_DIR=$(CDPATH='' cd -- "$EFIVAR_STORE_REPO" && pwd -P)
else
    EFVS_SOURCE_DIR=$out_root/sources/efivar_store
fi
if [ -z "${EFVS_RUSTC:-}" ]; then
    cargo_path=$(command -v "${CARGO:-cargo}" 2>/dev/null || true)
    [ -n "$cargo_path" ] || cargo_path=$HOME/.cargo/bin/cargo
    EFVS_RUSTC=$(dirname -- "$cargo_path")/rustc
fi
export EFVS_CARGO_TARGET_DIR EFVS_SOURCE_DIR EFVS_RUSTC
destination=$out_root/modules/$branch-$generation/$arch
if [ -e "$destination/set.json" ]; then
    echo "module set record already exists: $destination/set.json (select a fresh OUT_DIR)" >&2
    exit 2
fi
mkdir -p "$destination"
include_stage=$out_root/module-src/$branch-$generation/include
if [ -e "$include_stage" ]; then
    if [ ! -f "$include_stage/egysk_lkm.h" ] || ! cmp -s "$root/include/egysk_lkm.h" "$include_stage/egysk_lkm.h"; then
        echo "staged shared header differs from current source: $include_stage" >&2
        exit 2
    fi
else
    mkdir -p "$(dirname -- "$include_stage")"
    python3 -c 'import shutil, sys; shutil.copytree(sys.argv[1], sys.argv[2])' "$root/include" "$include_stage"
fi
failures=
strip_args=
if [ "${STRIP_DEBUG:-0}" = 1 ]; then strip_args=--strip-debug; fi
for module do
    module_source=$root/kernel/$module
    prepared_source=0
    module_destination=$destination/$module
    if [ -e "$module_destination" ]; then
        echo "$module: refusing to overwrite existing output $module_destination" >&2
        failures="${failures}${failures:+,}$module"
        continue
    fi
    if [ "$module" = dm-thin-pool ] && [ -f "$module_source/prepare.py" ]; then
        prepared=$out_root/prepared/$branch-$generation/$arch/dm-thin-pool
        if [ -e "$prepared" ]; then
            echo "dm-thin-pool: refusing to overwrite prepared output $prepared" >&2
            failures="${failures}${failures:+,}dm-thin-pool"
            continue
        fi
        if ! python3 "$module_source/prepare.py" --branch "$branch" --generation "$generation" \
            --arch "$arch" --kernel-source "$source" --kernel-output "$output" --output "$prepared"; then
            echo "dm-thin-pool: source preparation failed for $branch generation $generation" >&2
            failures="${failures}${failures:+,}dm-thin-pool"
            continue
        fi
        module_source=$prepared
        prepared_source=1
    fi
    if [ "$prepared_source" -eq 1 ]; then
        staged_source=$module_source
    else
        staged_source=$out_root/module-src/$branch-$generation/$arch/$module
        if [ -e "$staged_source" ]; then
            echo "$module: refusing to overwrite staged source $staged_source" >&2
            failures="${failures}${failures:+,}$module"
            continue
        fi
        mkdir -p "$(dirname -- "$staged_source")"
        if ! python3 -c 'import shutil, sys; shutil.copytree(sys.argv[1], sys.argv[2], ignore=shutil.ignore_patterns(".git", ".source", "*.o", "*.ko", "*.cmd", "*.mod", "*.mod.c", "*.mod.o", "*.a", "*.d", "*.order", "*.dtb", "*.dtbo", "*.symvers", "*.build.log", "efvs-*.json", "Module.symvers", "Module.markers", "modules.order", "modules.builtin", "modules.builtin.modinfo", ".depend", ".cache.mk", ".tmp_versions"))' "$module_source" "$staged_source"; then
            echo "$module: source staging failed" >&2
            failures="${failures}${failures:+,}$module"
            continue
        fi
    fi
    if [ "$module" = efivar_store ]; then
        if ! python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from scripts.kmi_modules import efvs_source; efvs_source(Path(sys.argv[1]) / "kernel/efivar_store")' "$root" || \
            ! "${CARGO:-$HOME/.cargo/bin/cargo}" +nightly-2026-08-08 fetch --locked --manifest-path "$EFVS_SOURCE_DIR/Cargo.toml"; then
            echo "efivar_store: pinned source or Rust dependencies are unavailable" >&2
            failures="${failures}${failures:+,}efivar_store"
            continue
        fi
        if [ -e "$staged_source/.source" ]; then
            echo "efivar_store: refusing to overwrite source link $staged_source/.source" >&2
            failures="${failures}${failures:+,}efivar_store"
            continue
        fi
        source_link=$(python3 -c 'import os, sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$EFVS_SOURCE_DIR" "$staged_source")
        ln -s "$source_link" "$staged_source/.source"
    fi
    mkdir -p "$module_destination"
    if [ -n "${KMI_ABI:-}" ]; then
        # shellcheck disable=SC2086
        if ! python3 "$root/scripts/kmi_modules.py" build --module-dir "$staged_source" --module "$module" \
            --branch "$branch" --generation "$generation" --arch "$arch" --kmi-src "$source" \
            --kmi-out "$output" --kmi-abi "$KMI_ABI" --output-dir "$module_destination" \
            --jobs "${JOBS:-4}" $strip_args; then
            echo "$module: build or admission failed" >&2
            failures="${failures}${failures:+,}$module"
            continue
        fi
        if ! python3 "$root/scripts/kmi_modules.py" verify --branch "$branch" --generation "$generation" \
            --arch "$arch" --kmi-out "$output" --kmi-abi "$KMI_ABI" --module "$module_destination/$module.ko"; then
            echo "$module: final-byte admission failed" >&2
            failures="${failures}${failures:+,}$module"
            continue
        fi
    else
        # shellcheck disable=SC2086
        if ! python3 "$root/scripts/kmi_modules.py" build --module-dir "$staged_source" --module "$module" \
            --branch "$branch" --generation "$generation" --arch "$arch" --kmi-src "$source" \
            --kmi-out "$output" --output-dir "$module_destination" --jobs "${JOBS:-4}" $strip_args; then
            echo "$module: build or admission failed" >&2
            failures="${failures}${failures:+,}$module"
            continue
        fi
        if ! python3 "$root/scripts/kmi_modules.py" verify --branch "$branch" --generation "$generation" --arch "$arch" --kmi-out "$output" --module "$module_destination/$module.ko"; then
            echo "$module: final-byte admission failed" >&2
            failures="${failures}${failures:+,}$module"
            continue
        fi
    fi
done
if ! python3 "$root/scripts/module_set.py" record --directory "$destination" --branch "$branch" \
    --generation "$generation" --arch "$arch" --requested "$requested" --failed "$failures"; then
    failures="${failures:-module-set record}"
fi
if [ -n "$failures" ]; then
    echo "module build failures: $failures" >&2
    exit 1
fi
if [ "$full_set" -eq 1 ]; then
    standalone_source=$EFVS_SOURCE_DIR/linux
    if [ -n "${EFIVAR_STORE_REPO:-}" ] && [ -d "$EFIVAR_STORE_REPO" ]; then
        standalone_repo=$out_root/sources/efivar_store-standalone
        if [ -e "$standalone_repo" ]; then
            echo "standalone EFVS source staging already exists: $standalone_repo (select a fresh OUT_DIR)" >&2
            exit 1
        fi
        if ! python3 -c 'import shutil, sys; shutil.copytree(sys.argv[1], sys.argv[2], ignore=shutil.ignore_patterns(".git", "target", "out"))' "$EFVS_SOURCE_DIR" "$standalone_repo"; then
            echo "standalone EFVS source staging failed" >&2
            exit 1
        fi
        standalone_source=$standalone_repo/linux
    fi
    standalone_destination=$out_root/standalone/$branch-$generation/$arch/efivar_store
    if [ -e "$standalone_destination" ]; then
        echo "standalone output already exists: $standalone_destination (select a fresh OUT_DIR)" >&2
        exit 1
    fi
    mkdir -p "$standalone_destination"
    if [ -n "${KMI_ABI:-}" ]; then
        python3 "$root/scripts/kmi_modules.py" build --module-dir "$standalone_source" --module efivar_store \
            --branch "$branch" --generation "$generation" --arch "$arch" --kmi-src "$source" \
            --kmi-out "$output" --kmi-abi "$KMI_ABI" --output-dir "$standalone_destination" --jobs "${JOBS:-4}"
        python3 "$root/scripts/kmi_modules.py" verify --module "$standalone_destination/efivar_store.ko" \
            --branch "$branch" --generation "$generation" --arch "$arch" --kmi-out "$output" --kmi-abi "$KMI_ABI"
    else
        python3 "$root/scripts/kmi_modules.py" build --module-dir "$standalone_source" --module efivar_store \
            --branch "$branch" --generation "$generation" --arch "$arch" --kmi-src "$source" \
            --kmi-out "$output" --output-dir "$standalone_destination" --jobs "${JOBS:-4}"
        python3 "$root/scripts/kmi_modules.py" verify --module "$standalone_destination/efivar_store.ko" \
            --branch "$branch" --generation "$generation" --arch "$arch" --kmi-out "$output"
    fi
fi

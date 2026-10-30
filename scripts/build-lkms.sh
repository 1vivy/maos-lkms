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
    set -- "$branch" "$generation" "$arch" "$source" "$output" \
        dm-thin-pool part-projection
fi
shift 5
requested=
seen=' '
count=0
for module do
    case "$module" in dm-thin-pool|part-projection) ;; *)
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
clang_version=$(python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from scripts.kmi_modules import clang_version; print(clang_version(Path(sys.argv[2]), sys.argv[3] or None))' "$root" "$source" "${DDK_CLANG:-}")
clang_dir=${DDK_CLANG_DIR:-$out_root/ddk/clang/clang-$clang_version/bin}
if [ ! -x "$clang_dir/clang" ] || [ ! -x "$clang_dir/ld.lld" ]; then
    echo "matching DDK clang $clang_version required at $clang_dir (run sh scripts/bootstrap-ddk-clang.sh $branch $generation, or set DDK_CLANG_DIR)" >&2
    exit 2
fi
PATH=$clang_dir:$PATH
export PATH
unset CROSS_COMPILE
# CLANG_FLAGS before 5.15 derives --target from CROSS_COMPILE, so those lines
# need the triple prefix; 5.15 and later derive the target without one.
if python3 -c 'import re, sys; from pathlib import Path; t = (Path(sys.argv[1]) / "Makefile").read_text(); v = tuple(int(re.search(rf"^{k}\s*=\s*(\d+)", t, re.M).group(1)) for k in ("VERSION", "PATCHLEVEL")); sys.exit(0 if v < (5, 15) else 1)' "$source"; then
    case "$arch" in
        aarch64) CROSS_COMPILE=aarch64-linux-gnu- ;;
        x86_64) CROSS_COMPILE=x86_64-linux-gnu- ;;
    esac
    export CROSS_COMPILE
fi
echo "compiler: $("$clang_dir/clang" --version | head -n 1)" >&2
python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from scripts.kmi_modules import kmi_identity; kmi_identity(Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]))' "$root" "$source" "$branch" "$generation"
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
# One build and one verify call serve both lanes; KMI_ABI adds the published dump.
run_build() {
    if [ -n "${KMI_ABI:-}" ]; then
        set -- --kmi-abi "$KMI_ABI" "$@"
    fi
    # shellcheck disable=SC2086
    python3 "$root/scripts/kmi_modules.py" build --module-dir "$staged_source" --module "$module" \
        --branch "$branch" --generation "$generation" --arch "$arch" --kmi-src "$source" \
        --kmi-out "$output" --output-dir "$module_destination" --jobs "${JOBS:-4}" "$@" $strip_args
}

run_verify() {
    if [ -n "${KMI_ABI:-}" ]; then
        set -- --kmi-abi "$KMI_ABI" "$@"
    fi
    python3 "$root/scripts/kmi_modules.py" verify --branch "$branch" --generation "$generation" \
        --arch "$arch" --kmi-out "$output" --module "$module_destination/$module.ko" "$@"
}

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
        if ! python3 -c 'import shutil, sys; shutil.copytree(sys.argv[1], sys.argv[2], ignore=shutil.ignore_patterns(".git", "*.o", "*.ko", "*.cmd", "*.mod", "*.mod.c", "*.mod.o", "*.a", "*.d", "*.order", "*.dtb", "*.dtbo", "*.symvers", "*.build.log", "Module.symvers", "Module.markers", "modules.order", "modules.builtin", "modules.builtin.modinfo", ".depend", ".cache.mk", ".tmp_versions"))' "$module_source" "$staged_source"; then
            echo "$module: source staging failed" >&2
            failures="${failures}${failures:+,}$module"
            continue
        fi
    fi
    mkdir -p "$module_destination"
    if ! run_build; then
        echo "$module: build or admission failed" >&2
        failures="${failures}${failures:+,}$module"
        continue
    fi
    if ! run_verify; then
        echo "$module: final-byte admission failed" >&2
        failures="${failures}${failures:+,}$module"
        continue
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

#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Extract the compiler pinned by the selected ACK source into OUT_DIR.
set -eu
if [ "$#" -eq 0 ]; then
    branch=android16-6.12
    generation=6
elif [ "$#" -eq 2 ]; then
    branch=$1
    generation=$2
else
    echo "usage: $0 [branch generation]" >&2
    exit 2
fi
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
. "$script_dir/ddk-targets.sh"
resolve_ddk_target "$branch" "$generation"
image=$DDK_IMAGE
version=$DDK_CLANG
expected=${version#clang-}
root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
. "$script_dir/out-dir.sh"
select_out_dir "$root"
out_root=$OUT_DIR
destination=$out_root/ddk/clang/$version
record=$out_root/ddk/clang/ddk-clang-$version.json
if [ -e "$record" ]; then
    echo "clang identity record already exists: $record (select a fresh OUT_DIR)" >&2
    exit 2
fi
if [ -e "$destination" ] && { [ ! -x "$destination/bin/clang" ] || [ ! -x "$destination/bin/ld.lld" ]; }; then
    echo "incomplete clang output already exists: $destination (select a fresh OUT_DIR)" >&2
    exit 2
fi
if [ ! -e "$destination" ]; then
    if ! command -v docker >/dev/null 2>&1; then
        echo "pinned DDK clang bootstrap requires docker for image $image" >&2
        exit 2
    fi
    if ! docker image inspect "$image" >/dev/null 2>&1; then
        echo "pulling pinned DDK image by digest: $image" >&2
        docker pull "$image"
    fi
    created=$(docker create "$image")
    trap 'docker rm -f "$created" >/dev/null 2>&1 || true' EXIT INT TERM
    mkdir -p "$destination"
    for path in bin lib AndroidVersion.txt; do
        docker cp "$created:/opt/ddk/clang/$version/$path" "$destination/"
    done
    docker rm -f "$created" >/dev/null
    trap - EXIT INT TERM
fi
reported=$("$destination/bin/clang" --version | head -n 1)
case "$reported" in *"based on $expected"*) ;; *)
    echo "unexpected pinned DDK clang version: $reported (expected $expected)" >&2
    exit 1
    ;;
esac
mkdir -p "$out_root/ddk/clang"
smoke=$out_root/ddk/clang/smoke-$version.c
if [ -e "$smoke" ]; then
    echo "clang smoke input already exists: $smoke (select a fresh OUT_DIR)" >&2
    exit 2
fi
for smoke_object in "$out_root/ddk/clang/smoke-aarch64-$version.o" "$out_root/ddk/clang/smoke-x86_64-$version.o"; do
    if [ -e "$smoke_object" ]; then
        echo "clang smoke output already exists: $smoke_object (select a fresh OUT_DIR)" >&2
        exit 2
    fi
done
printf '' >"$smoke"
"$destination/bin/clang" --target=aarch64-linux-gnu -ffreestanding -nostdinc -c \
    -o "$out_root/ddk/clang/smoke-aarch64-$version.o" "$smoke"
"$destination/bin/clang" --target=x86_64-linux-gnu -ffreestanding -nostdinc -c \
    -o "$out_root/ddk/clang/smoke-x86_64-$version.o" "$smoke"
rm -f "$smoke" "$out_root/ddk/clang/smoke-aarch64-$version.o" \
    "$out_root/ddk/clang/smoke-x86_64-$version.o"
{
    printf '{\n  "image": "%s",\n  "branch": "%s",\n  "generation": %s,\n  "clang_version": "%s",\n  "clang_version_line": "%s",\n  "clang_sha256": "%s",\n  "ld_lld_sha256": "%s"\n}\n' \
        "$image" "$branch" "$generation" "$version" "$reported" \
        "$(sha256sum "$destination/bin/clang" | cut -d' ' -f1)" \
        "$(sha256sum "$destination/bin/ld.lld" | cut -d' ' -f1)"
} >"$record"
echo "pinned DDK clang: $destination"
echo "identity recorded in $record"

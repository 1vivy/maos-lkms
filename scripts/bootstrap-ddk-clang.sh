#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Extract the pinned DDK clang into the ignored out/ tree. This is the compiler
# the android16-6.12 KMI names in build.config.constants (CLANG_VERSION).
# It is not a KMI input: the DDK kernel outputs are refused, because their CRCs
# do not match the published KMI. See README.md.
set -eu
image=ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee
version=clang-r536225
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
destination=$root/out/ddk/clang/$version
record=$root/out/ddk/clang/ddk-clang.json
if [ -x "$destination/bin/clang" ] && [ -x "$destination/bin/ld.lld" ]; then
    echo "pinned DDK clang present: $destination"
    exit 0
fi
if ! command -v docker >/dev/null 2>&1; then
    echo "pinned DDK clang bootstrap requires docker for image $image" >&2
    exit 2
fi
# A tag can move; the digest cannot. Pull exactly the recorded manifest.
if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker pull "$image"
fi
created=$(docker create "$image")
trap 'docker rm -f "$created" >/dev/null 2>&1 || true' EXIT INT TERM
mkdir -p "$destination"
# bin and lib carry the driver, the linker and the builtin headers. Skip the
# NDK runtime and C++ trees the kernel build does not use.
for path in bin lib AndroidVersion.txt; do
    docker cp "$created:/opt/ddk/clang/$version/$path" "$destination/"
done
docker rm -f "$created" >/dev/null
trap - EXIT INT TERM
reported=$("$destination/bin/clang" --version | head -n 1)
case "$reported" in
    *"based on r536225"*) ;;
    *)
        echo "unexpected pinned DDK clang version: $reported" >&2
        exit 1
        ;;
esac
# Prove the extracted driver runs here and targets the KMI architecture.
mkdir -p "$root/out/ddk/clang"
printf '' >"$root/out/ddk/clang/smoke.c"
"$destination/bin/clang" --target=aarch64-linux-gnu -ffreestanding -nostdinc -c \
    -o "$root/out/ddk/clang/smoke-aarch64.o" "$root/out/ddk/clang/smoke.c"
"$destination/bin/clang" --target=x86_64-linux-gnu -ffreestanding -nostdinc -c \
    -o "$root/out/ddk/clang/smoke-x86_64.o" "$root/out/ddk/clang/smoke.c"
rm -f "$root/out/ddk/clang/smoke.c" "$root/out/ddk/clang/smoke-aarch64.o" \
    "$root/out/ddk/clang/smoke-x86_64.o"
{
    echo "{"
    echo "  \"image\": \"$image\","
    echo "  \"clang_version\": \"$version\","
    echo "  \"clang_version_line\": \"$(printf '%s' "$reported" | sed 's/\\/\\\\/g; s/"/\\"/g')\","
    echo "  \"clang_sha256\": \"$(sha256sum "$destination/bin/clang" | cut -d' ' -f1)\","
    echo "  \"ld_lld_sha256\": \"$(sha256sum "$destination/bin/ld.lld" | cut -d' ' -f1)\""
    echo "}"
} >"$record"
echo "pinned DDK clang: $destination"
echo "identity recorded in $record"

#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# The canonical arm64 lane: the digest-pinned DDK image is the build input, the
# way KernelSU's CI builds its GKI modules against the same image family. The
# image's absolute /opt/ddk paths (its kdir Makefile and the kdir/source
# symlink both point there) are not relocatable, so the build runs inside the
# container instead of an extracted copy; the host's pinned nightly Rust
# toolchain is bind-mounted in for the freestanding efivar_store engine.
#
# Admission runs against this same image's published KMI ABI
# (gki/aarch64/abi.stg) and its own Module.symvers/System.map, not against
# Module.symvers CRCs: see scripts/kmi_modules.py and README.md.
set -eu
if [ "$#" -ne 2 ]; then
    echo "usage: $0 branch generation" >&2
    exit 2
fi
branch=$1
generation=$2
image=ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee
# The pinned digest is one image, built for one branch; it is not a generic
# per-branch index. Extend this list only by pinning another image digest.
case "$branch-$generation" in
    android16-6.12-6) ;;
    *)
        echo "no pinned DDK image for $branch generation $generation (only android16-6.12 generation 6)" >&2
        exit 2
        ;;
esac
if ! command -v docker >/dev/null 2>&1; then
    echo "the canonical arm64 lane requires docker for image $image" >&2
    exit 2
fi
if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker pull "$image"
fi
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cargo_home=${CARGO_HOME:-$HOME/.cargo}
rustup_home=${RUSTUP_HOME:-$HOME/.rustup}
if [ ! -d "$cargo_home" ] || [ ! -d "$rustup_home" ]; then
    echo "pinned nightly-2026-08-08 Rust toolchain required at $cargo_home / $rustup_home (for the freestanding efivar_store engine)" >&2
    exit 2
fi
mkdir -p "$root/out/ddk"
docker run --rm \
    -v "$root:$root" -w "$root" \
    -v "$cargo_home:/root/.cargo" -v "$rustup_home:/root/.rustup" \
    -e PATH="/opt/ddk/clang/clang-r536225/bin:/root/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0="*" \
    -e DDK_CLANG_DIR=/opt/ddk/clang/clang-r536225/bin \
    -e CARGO=/root/.cargo/bin/cargo \
    -e KMI_ABI="/opt/ddk/src/$branch/gki/aarch64/abi.stg" \
    -e JOBS="${JOBS:-4}" \
    --entrypoint /bin/sh \
    "$image" -c 'sh scripts/build-lkms.sh "$1" "$2" aarch64 "/opt/ddk/src/$1" "/opt/ddk/kdir/$1"' sh "$branch" "$generation"
{
    echo "{"
    echo "  \"image\": \"$image\","
    echo "  \"branch\": \"$branch\","
    echo "  \"generation\": $generation,"
    echo "  \"kmi_abi_sha256\": \"$(docker run --rm --entrypoint /bin/sh "$image" -c "sha256sum /opt/ddk/src/$branch/gki/aarch64/abi.stg" | cut -d' ' -f1)\""
    echo "}"
} >"$root/out/ddk/kmi-ddk-$branch-$generation.json"
echo "canonical arm64 lane: $root/out/ddk/kmi-ddk-$branch-$generation.json"

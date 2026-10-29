#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Build arm64 modules inside the digest-pinned DDK image.
set -eu
if [ "$#" -lt 2 ]; then
    echo "usage: $0 branch generation [module ...]" >&2
    exit 2
fi
branch=$1
generation=$2
shift 2
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
. "$script_dir/ddk-targets.sh"
resolve_ddk_target "$branch" "$generation"
image=$DDK_IMAGE
clang=$DDK_CLANG
abi=$DDK_ABI
root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
. "$script_dir/out-dir.sh"
select_out_dir "$root"
out_root=$OUT_DIR
mkdir -p "$out_root/ddk"
record=$out_root/ddk/kmi-ddk-$branch-$generation.json
if [ -e "$record" ]; then
    echo "DDK target record already exists: $record (select a fresh OUT_DIR)" >&2
    exit 2
fi
if [ "$branch-$generation" = "android14-6.1-11" ]; then
    echo "target has no published abi.stg; admission uses image Module.symvers and System.map" >&2
fi
if ! command -v docker >/dev/null 2>&1; then
    echo "the canonical arm64 lane requires docker for image $image" >&2
    exit 2
fi
if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "pulling pinned DDK image by digest: $image" >&2
    docker pull "$image"
fi
cargo_home=${CARGO_HOME:-$HOME/.cargo}
rustup_home=${RUSTUP_HOME:-$HOME/.rustup}
if [ ! -d "$cargo_home" ] || [ ! -d "$rustup_home" ]; then
    echo "pinned nightly-2026-08-08 Rust toolchain required at $cargo_home / $rustup_home (for the freestanding efivar_store engine)" >&2
    exit 2
fi
modules=$*
efivar_repo=
if [ -n "${EFIVAR_STORE_REPO:-}" ]; then
    if [ -d "$EFIVAR_STORE_REPO" ]; then
        efivar_repo=$(CDPATH='' cd -- "$EFIVAR_STORE_REPO" && pwd -P)
    else
        case "$EFIVAR_STORE_REPO" in
            *://*|*@*:*) ;;
            *) echo "EFIVAR_STORE_REPO is neither a local directory nor a repository URL: $EFIVAR_STORE_REPO" >&2; exit 2 ;;
        esac
    fi
fi
set -- docker run --rm --user "$(id -u):$(id -g)" \
    -v "$root:$root" -w "$root" \
    -v "$cargo_home:/cargo" -v "$rustup_home:/rustup"
if [ -n "$efivar_repo" ]; then
    set -- "$@" -v "$efivar_repo:/opt/maos/efivar-store:ro" \
        -e EFIVAR_STORE_REPO=/opt/maos/efivar-store
elif [ -n "${EFIVAR_STORE_REPO:-}" ]; then
    set -- "$@" -e "EFIVAR_STORE_REPO=$EFIVAR_STORE_REPO"
fi
set -- "$@" \
    -e OUT_DIR="$out_root" \
    -e HOME=/tmp -e CARGO_HOME=/cargo -e RUSTUP_HOME=/rustup \
    -e PATH="/opt/ddk/clang/$clang/bin:/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0="*" \
    -e DDK_CLANG_DIR="/opt/ddk/clang/$clang/bin" \
    -e CARGO=/cargo/bin/cargo \
    -e EFVS_RUSTC=/cargo/bin/rustc \
    -e KMI_ABI="${abi:+/opt/ddk/src/$branch/$abi}" \
    -e DDK_IMAGE="$image" \
    -e JOBS="${JOBS:-4}" \
    -e STRIP_DEBUG="${STRIP_DEBUG:-0}" \
    --entrypoint /bin/sh \
    "$image" -c 'branch=$1; generation=$2; shift 2; exec sh scripts/build-lkms.sh "$branch" "$generation" aarch64 "/opt/ddk/src/$branch" "/opt/ddk/kdir/$branch" "$@"' sh "$branch" "$generation"
# Module names are validated above; split the saved list into container arguments.
# shellcheck disable=SC2086
for module in $modules; do
    case "$module" in
        *[!A-Za-z0-9_-]*) echo "invalid module argument: $module" >&2; exit 2 ;;
    esac
    set -- "$@" "$module"
done
"$@"
abi_sha=
if [ -n "$abi" ]; then
    abi_sha=$(docker run --rm --entrypoint /bin/sh "$image" -c "sha256sum /opt/ddk/src/$branch/$abi" | cut -d' ' -f1)
fi
printf '{\n  "image": "%s",\n  "tag": "%s",\n  "branch": "%s",\n  "generation": %s,\n  "compiler": "%s",\n  "kmi_abi_path": "%s",\n  "kmi_abi_sha256": "%s"\n}\n' \
    "$image" "$DDK_TAG" "$branch" "$generation" "$clang" "$abi" "$abi_sha" \
    >"$record"
echo "canonical arm64 lane: $record"

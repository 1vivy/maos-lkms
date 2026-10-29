#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Pinned DDK image targets. Keep this table aligned with the image provenance.
resolve_ddk_target() {
    branch=$1
    generation=$2
    case "$branch-$generation" in
        android14-6.1-11)
            DDK_TAG=ghcr.io/ylarod/ddk-min:android14-6.1-20260828
            DDK_IMAGE=ghcr.io/ylarod/ddk-min@sha256:1dd6ac340b627a90a4031d6d0df6b129d8cc949b139fb56032c898f023d3d5d3
            DDK_CLANG=clang-r487747c
            DDK_ABI=
            ;;
        android16-6.12-6)
            DDK_TAG=ghcr.io/ylarod/ddk-min:android16-6.12-20260828
            DDK_IMAGE=ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee
            DDK_CLANG=clang-r536225
            DDK_ABI=gki/aarch64/abi.stg
            ;;
        android17-6.18-5)
            DDK_TAG=ghcr.io/ylarod/ddk-min:android17-6.18-20260828
            DDK_IMAGE=ghcr.io/ylarod/ddk-min@sha256:fb8b66200bf402cf65a751060fc1aa29524b9fa8840feef16c7b196a4f3f0e6e
            DDK_CLANG=clang-r584948c
            DDK_ABI=gki/aarch64/abi.stg
            ;;
        *)
            echo "no pinned DDK image for $branch generation $generation" >&2
            return 2
            ;;
    esac
    export DDK_TAG DDK_IMAGE DDK_CLANG DDK_ABI
}

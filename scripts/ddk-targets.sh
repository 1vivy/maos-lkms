#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Pinned DDK image targets. Keep this table aligned with the image provenance.
# Each image is pulled by digest. Tags are the labels that the images record;
# the 5.15 and 6.6 tags follow the community manifest at
# Shikochin/Droidspaces-LKM build/gki-targets.json (revision 8c14b35), which
# names the same digests.
resolve_ddk_target() {
    branch=$1
    generation=$2
    case "$branch-$generation" in
        android12-5.10-9)
            DDK_TAG=ghcr.io/ylarod/ddk-min:android12-5.10-20260313
            DDK_IMAGE=ghcr.io/ylarod/ddk-min@sha256:272ada1e61c525116032246df2a790d1ccec1804b7a9e0b09203c5e650dcb78e
            DDK_CLANG=clang-r416183b
            DDK_ABI=
            ;;
        android13-5.15-8)
            DDK_TAG=ghcr.io/ylarod/ddk-min:android13-5.15-20260313
            DDK_IMAGE=ghcr.io/ylarod/ddk-min@sha256:9e68cd9fcab748584755d31ba88ef134efc938dbde17f258c2652315f6cd81cd
            DDK_CLANG=clang-r450784e
            DDK_ABI=
            ;;
        android14-6.1-11)
            DDK_TAG=ghcr.io/ylarod/ddk-min:android14-6.1-20260828
            DDK_IMAGE=ghcr.io/ylarod/ddk-min@sha256:1dd6ac340b627a90a4031d6d0df6b129d8cc949b139fb56032c898f023d3d5d3
            DDK_CLANG=clang-r487747c
            DDK_ABI=
            ;;
        android15-6.6-8)
            DDK_TAG=ghcr.io/ylarod/ddk-min:android15-6.6-20260313
            DDK_IMAGE=ghcr.io/ylarod/ddk-min@sha256:51159bc935c75a282fc65bc87e02f16bd098d1cdf55dc558c4fdd0fcf7a132e2
            DDK_CLANG=clang-r510928
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

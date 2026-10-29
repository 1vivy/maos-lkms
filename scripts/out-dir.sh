#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Select an output directory under the repository's ignored out/ tree.
select_out_dir() {
    out_repo=$1
    out_requested=${OUT_DIR:-$out_repo/out/build-matrix}
    case "$out_requested" in /*) ;; *) out_requested=$out_repo/$out_requested ;; esac
    case "$out_requested" in "$out_repo/out"|"$out_repo/out"/*) ;; *)
        echo "OUT_DIR must be inside $out_repo/out: $out_requested" >&2
        return 2
        ;;
    esac
    case "/$out_requested/" in */../*)
        echo "OUT_DIR must not contain parent-directory components: $out_requested" >&2
        return 2
        ;;
    esac
    out_check=$out_requested
    while [ "$out_check" != "$out_repo" ] && [ "$out_check" != "/" ]; do
        if [ -L "$out_check" ]; then
            echo "OUT_DIR must not pass through a symlink: $out_check" >&2
            return 2
        fi
        out_check=$(dirname -- "$out_check")
    done
    mkdir -p "$out_requested"
    OUT_DIR=$(CDPATH='' cd -- "$out_requested" && pwd)
    case "$OUT_DIR" in "$out_repo/out"|"$out_repo/out"/*) ;; *)
        echo "OUT_DIR resolves outside $out_repo/out: $OUT_DIR" >&2
        return 2
        ;;
    esac
    export OUT_DIR
}

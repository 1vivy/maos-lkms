# `kernel/dm-thin-pool` — independent `dm-thin-pool.ko`

A separate **GPL-2.0-only** out-of-tree kernel module that provides the
device-mapper `thin-pool` and `thin` targets the multi-ROM thin-storage layout
needs. It is vendored from the Linux kernel dm-thin family and forked to use
only exported KMI surface; `PROVENANCE.md` records the exact origin, file set and
patch.

`dm-thin-pool.ko` is independent and never linked to a product/root runtime. The
repository's top-level `LICENSE` does **not** cover this subtree:
see `LICENSE` here (the verbatim GPL-2.0 text) and the `GPL-2.0-only` SPDX
headers of every vendored file.

## Output and identity

| Item | Value |
| --- | --- |
| Module file | `dm-thin-pool.ko`, built in this directory |
| Module name | `dm_thin_pool` (Kbuild normalizes hyphens) |
| Description | `maos thin provisioning targets (thin-pool, thin)` |
| Author | `maos` |
| License | `GPL v2` in `thin-main.c`; the vendored files keep their upstream `MODULE_LICENSE("GPL")` boilerplate, all GPL-2-compatible (see `PROVENANCE.md`) |
| Device-mapper targets | `thin-pool` (v1.23.0) and `thin` (v1.23.0), names unchanged from the proven build |

The module identity and readiness parameter apply to newly built modules. A previously built artifact does not change when source metadata changes.

Private symbol names use the `thinpool_private_*` prefix through `private-rename.h`. The module does not define or override kernel device-mapper symbols. It registers the two documented targets.


Source and shipped directories are independent: downstream packaging chooses
`modules/<id>/kmod/<branch>-<generation>/dm-thin-pool.ko`. Load this module before
activating thin volumes and before committing any projection using them. There
is no core-first runtime dependency, module LV, or generic boot activation.

## Module parameters

Read `/sys/module/dm_thin_pool/parameters/` after loading:

| Parameter | Access | Value |
| --- | --- | --- |
| `ready` | read-only (0444) | `Y` only after every subsystem and both targets initialized; `N` while any initializer fails and again as soon as unload teardown starts |

`ready` is set exactly once, after
the last initializer returns, and cleared first in the exit path; the proven
init order and every failure-unwind branch are unchanged.

## Build

Prerequisites:

- Exact ACK branch/generation source and complete matching GKI/DDK output with
  the published export whitelist (`Module.symvers`, `System.map`, generated headers).
  `modules_prepare` alone is insufficient.
- a clang/LLVM toolchain matching that kernel (`LLVM=1` is always used).

```sh
KMI_SRC=/path/to/kernel KMI_OUT=/path/to/out KMI_BRANCH=android16-6.12 KMI_GENERATION=6 KMI_ARCH=aarch64 kernel/dm-thin-pool/build.sh
```

or directly:

```sh
make -C kernel/dm-thin-pool KMI_SRC=/path/to/kernel KMI_OUT=/path/to/out KMI_BRANCH=android16-6.12 KMI_GENERATION=6 KMI_ARCH=aarch64 JOBS=4
```

- All four projects use explicit `KMI_SRC`, `KMI_OUT`, `KMI_BRANCH`,
  `KMI_GENERATION`, `KMI_ARCH` (`aarch64` or `x86_64`). No branch-only selection.
- `JOBS` defaults to 13 and is capped at 13.
- `KBUILD_GENDWARFKSYMS_STABLE=1` is always passed and old module objects are
  cleaned first.
- `KBUILD_MODPOST_WARN=1` allows unresolved imports during compilation. Admission then requires every undefined symbol to be exported by the target KMI (`gki/<arch>/abi.stg` on the canonical DDK lane, or `Module.symvers` here) or present in `System.map` when the target has `CONFIG_KALLSYMS_ALL=y`. The configured loader prebinds imports before `init_module`. Admission does not compare CRCs for imports other than a present `module_layout` record, which must match the published KMI CRC. See the root README.

- Ship `dm-thin-pool.ko` alone in a payload. The `<module>.ko.build.json` written
  beside it is release information for readers of the artifact directory; nothing
  verifies or packages it.

## Layout

| Path | Contents |
| --- | --- |
| `thin-main.c` | module entry point: init order, unwind, `ready` parameter, metadata |
| `src/` | vendored dm-thin family sources (`dm-thin`, `dm-thin-metadata`, `dm-bufio`, `dm-io`, `dm-kcopyd`, `dm-bio-prison-v1/v2`) |
| `src/persistent-data/` | vendored persistent-data helpers (btree, bitset, array, block/space maps, transaction manager) |
| `private-rename.h` | private `thinpool_private_*` renames for every non-exported symbol |
| `Kbuild`, `Makefile` | standalone module definition and exact-identity build wrapper |
| `build.sh` | scripted entry point forwarding the explicit KMI identity |
| `patches/0001-fork-dm-thin-for-exported-KMI-surface.patch` | the fork that adapts the vendored sources to the exported KMI |
| `PROVENANCE.md` | origin, exact file set with hashes, modifications, licensing |
| `LICENSE` | verbatim GPL-2.0 text |

## Verifying a built module

```sh
modinfo dm-thin-pool.ko
modprobe --dump-modversions dm-thin-pool.ko
insmod dm-thin-pool.ko
cat /sys/module/dm_thin_pool/parameters/ready
dmsetup targets                         # thin-pool and thin, both version 1.23.0
```

The recorded proof for the vendored sources covers: arm64 build, valid modpost
and signed `insmod` against ACK `f1bdb13583da85a47fcf1632a78ef52d6e6da651`; and
the full dm-thin behavior matrix in QEMU (snapshots, discard, partial-block
zeroing, `dm-default-key` ciphertext equality, ENOSPC modes, forced-reset
metadata recovery).

## Product build gates

`just gate <branch> <generation> <aarch64|x86_64> <source> <complete-output>`
builds all four independent projects plus the pinned store's standalone source
Kbuild. Module output stays in the ignored `out/` tree at
`out/modules/<branch>-<generation>/<arch>/<project>/`, and the standalone
Kbuild output stays at `out/standalone/<branch>-<generation>/<arch>/efivar_store/`.
The gate re-admits the exact shipped bytes. No stripping or mutation follows
`just host-contract` runs the ELF, identity, and build-info tests. It does not build init or daemon products.

CI runs host contract tests and the canonical digest-pinned arm64 DDK lane on pushes and pull requests. Manual dispatch can run the caller-supplied ACK lane on the prepared self-hosted `egysk-kmi` runner. Both lanes use complete matching KMI references. Header-only inputs and `modules_prepare` do not provide admission inputs. The pinned Rust nightly and `rust-src` build the freestanding store engine. Locked dependencies are fetched before offline Kbuild. Neither `CONFIG_RUST` nor a root runtime is required. CI uploads artifacts only.

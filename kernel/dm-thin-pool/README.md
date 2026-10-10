# `kernel/dm-thin-pool` — independent `dm-thin-pool.ko`

A separate **GPL-2.0-only** out-of-tree kernel module that provides the
device-mapper `thin-pool` and `thin` targets the multi-ROM thin-storage layout
needs. It is vendored from the Linux kernel dm-thin family and forked to use
only exported KMI surface; `PROVENANCE.md` records the exact origin, file set,
patch and proof evidence.

`dm-thin-pool.ko` is independent and never linked to a product/root runtime. The
repository's top-level `LICENSE` does **not** cover this subtree:
see `LICENSE` here (the verbatim GPL-2.0 text) and the `GPL-2.0-only` SPDX
headers of every vendored file.

## Output and identity

| Item | Value |
| --- | --- |
| Module file | `dm-thin-pool.ko`, built in this directory |
| Module name | `dm_thin_pool` (Kbuild normalizes hyphens) |
| Description | `esu thin provisioning targets (thin-pool, thin)` |
| Author | `esu` |
| License | `GPL v2` in `thin-main.c`; the vendored files keep their upstream `MODULE_LICENSE("GPL")` boilerplate, all GPL-2-compatible (see `PROVENANCE.md`) |
| Device-mapper targets | `thin-pool` (v1.23.0) and `thin` (v1.23.0), names unchanged from the proven build |

The proven private symbol names (`thinpool_private_*`, applied by
`private-rename.h`) are retained, so the module neither defines nor overrides
kernel device-mapper symbols, and the proven two-target registration is
unchanged.

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
  cleaned first. Disabling MODVERSIONS or inserting empty versions is forbidden.
- `KBUILD_MODPOST_WARN=1` allows non-KMI imports, but admission requires them
  in `System.map`. Every version CRC (including `module_layout`) must match
  `Module.symvers`; vermagic flags, not its release token, are enforced.
- Keep the generated `dm-thin-pool.ko.compat.json` beside `dm-thin-pool.ko` when copying it to a
  payload. The assembler checks the receipt and module again before packaging.

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
| `evidence/phone-d3144fcc5f04/` | frozen pre-import phone artifact, its import/modversion manifests and record summary |
| `PROVENANCE.md` | origin, exact file set with hashes, modifications, proof evidence, licensing |
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
and signed `insmod` against ACK `f1bdb13583da85a47fcf1632a78ef52d6e6da651`; the
full dm-thin behavior matrix in QEMU (snapshots, discard, partial-block zeroing,
`dm-default-key` ciphertext equality, ENOSPC modes, forced-reset metadata
recovery); and the phone-matched artifact below. `evidence/` states exactly what
the frozen artifact does and does not prove.

## Product build gates

`just gate <branch> <generation> <aarch64|x86_64> <source> <complete-output>
<artifact-dir>` builds all four independent projects plus the pinned store's
standalone source Kbuild. It copies artifacts and schema-2 receipts to
`<artifact-dir>/<branch>-<generation>/<arch>/` and verifies the copied bytes.
No stripping or mutation follows admission. `just host-contract` exercises the
ELF/identity/receipt tests; neither recipe builds legacy init or daemon products.

CI push/PR runs the host contracts. Manual build dispatch requires explicit
branch, generation, source and both architecture output paths. The ACK lane uses
a prepared self-hosted `kernelsu-esp-kmi` runner; the DDK lane uses the exact
selected DDK image release. Both architecture gates use real `Module.symvers`,
`System.map`, `.config` and generated headers. A header-only/minimal DDK image
without those complete matching references fails closed; modules_prepare is not
an admission input generator. The pinned nightly and rust-src are installed for
the freestanding store engine, with locked dependencies fetched before offline
Kbuild. No CONFIG_RUST or root runtime is required. CI uploads artifacts only;
the legacy daemon/init release and automatic publishing jobs are removed.

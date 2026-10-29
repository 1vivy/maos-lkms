# `kernel/dm-thin-pool` — independent `dm-thin-pool.ko`

A separate **GPL-2.0-only** out-of-tree kernel module that provides the
device-mapper `thin-pool` and `thin` targets the multi-ROM thin-storage layout
needs. Its device-mapper sources come from the kernel line that loads the
module: `prepare.py` stages that line's own dm-thin family and applies the
private-surface port. Shared transformations stay in `prepare.py`. Per-line
differences live in `abi/<line>/port.py`. `PROVENANCE.md` records the origin,
file set and port programme of each line.

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
| Device-mapper targets | `thin-pool` and `thin`, names unchanged from upstream; the version triple comes from the matching kernel source: 1.22.0 on 5.10, 5.15 and 6.1, 1.23.0 on 6.6 and 6.12, 1.24.0 on 6.18 |

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
| `private_names` | read-only (0444), set at load | `N` by default. With `insmod dm-thin-pool.ko private_names=1` the targets register as `thin-private` and `thin-pool-private`. The deployed module uses the upstream names. |

`ready` is set exactly once, after
the last initializer returns, and cleared first in the exit path; the proven
init order and every failure-unwind branch are unchanged.

## Supported kernel lines

| Line | Device-mapper sources | Profile |
| --- | --- | --- |
| 5.10 | that line's own kernel source, ported | generated |
| 5.15 | that line's own kernel source, ported | generated |
| 6.1 | that line's own kernel source, ported | generated |
| 6.6 | that line's own kernel source, ported | generated |
| 6.12 | the vendored tree proven against ACK 6.12 | verified |
| 6.18 | that line's own kernel source, ported | generated |

`prepare.py` validates the inputs, applies the shared port programme with the
edits from the selected `abi/<line>/port.py`, and writes a `PROVENANCE.json`
with the source hashes, the applied edits and the private symbol names. An
unsupported line, or an edit whose anchor changed in the kernel source, fails
with exit status 2. The tool never compiles, loads or qualifies a module.

Each line file names its profile, the edited sources in order and the
version-specific edits. The 6.12 file names the one proven branch and applies
no edits. The 5.10, 5.15, 6.1, 6.6 and 6.18 files hold the crypto flags,
metadata open flags, errno statuses, wait-bit test, bio allocation and
completion forms, and the kcopyd declaration that their sources need. The 5.10
and 5.15 files also name the one discard-path site that reaches the pool name
through `tc->pool`.

The ACK identity declarations differ per line. `android12-5.10` declares
`BRANCH=android12-5.10` and generation 9 in `build.config.common`; that source
has no `build.config.constants`. `android13-5.15` declares
`BRANCH` in `build.config.constants` and generation 8 in
`build.config.common`. `android14-6.1` declares `BRANCH` in
`build.config.constants` and generation 11 in `build.config.common`.
`android15-6.6` declares branch and generation 8 in `build.config.common`.
`android16-6.12` declares branch and generation 6. `android17-6.18` declares
branch and generation 5 through a `build.config.constants` symlink to
`bazel/constants.scl`. `prepare.py` requires every declaration that exists to
match the call and records the ones that do not exist.

```sh
python3 kernel/dm-thin-pool/prepare.py \
    --branch android17-6.18 --generation 5 --arch aarch64 \
    --kernel-source /opt/ddk/src/android17-6.18 \
    --kernel-output /opt/ddk/kdir/android17-6.18 \
    --output out/build-matrix/prepared/android17-6.18-5/aarch64/dm-thin-pool
```

The 5.10, 5.15 and 6.6 lines use the same tool with their own identity:

```sh
python3 kernel/dm-thin-pool/prepare.py \
    --branch android12-5.10 --generation 9 --arch aarch64 \
    --kernel-source /opt/ddk/src/android12-5.10 \
    --kernel-output /opt/ddk/kdir/android12-5.10 \
    --output out/build-matrix/prepared/android12-5.10-9/aarch64/dm-thin-pool

python3 kernel/dm-thin-pool/prepare.py \
    --branch android13-5.15 --generation 8 --arch aarch64 \
    --kernel-source /opt/ddk/src/android13-5.15 \
    --kernel-output /opt/ddk/kdir/android13-5.15 \
    --output out/build-matrix/prepared/android13-5.15-8/aarch64/dm-thin-pool

python3 kernel/dm-thin-pool/prepare.py \
    --branch android15-6.6 --generation 8 --arch aarch64 \
    --kernel-source /opt/ddk/src/android15-6.6 \
    --kernel-output /opt/ddk/kdir/android15-6.6 \
    --output out/build-matrix/prepared/android15-6.6-8/aarch64/dm-thin-pool
```

`scripts/build-lkms.sh` runs this step itself and places the staged tree at
`$OUT_DIR/prepared/<branch>-<generation>/<arch>/dm-thin-pool`. It refuses an
existing prepared directory, so a rerun needs a fresh `OUT_DIR`. Run the tool by
hand only to inspect a staged tree.

The staged directory is a complete module directory for
`scripts/kmi_modules.py build --module-dir`. It contains `Kbuild`, `Makefile`,
`stage.mk`, `include/egysk_lkm.h`, the whole `abi/` tree and its own
`PROVENANCE.json`. The staged `abi/` files record the ABI policy that produced
the tree, and their hashes appear in `module_inputs` and `files`. Do not add a
`SOURCE_REVISION` file to it: this module has no pinned source checkout.

The tool writes a new directory. It refuses an existing `--output` path and
stages through a unique temporary sibling that it removes on failure. Remove a
previous stage before a rerun. It creates missing parent directories only.

A pool must load with `skip_block_zeroing`. `pool_ctr` rejects a pool without
it, because an encrypted thin pool must not write zeroes below the encryption
target. Both targets also declare `DM_TARGET_PASSES_CRYPTO`, so a stacked
device keeps its inline-encryption capabilities. Upstream 5.10, 5.15, 6.1 and
6.6 sources do not set that flag on the thin targets, so their ABI files add
it. Upstream 6.18 has it, and the shared required-token check asserts it.

## Build

Prerequisites:

- Exact ACK branch/generation source and complete matching GKI/DDK output with
  the published export whitelist (`Module.symvers`, `System.map`, generated headers).
  `modules_prepare` alone is insufficient.
- a clang/LLVM toolchain matching that kernel (`LLVM=1` is always used).

The commands below build this directory's own sources, which are the verified
6.12 tree. Use the staged directory from `prepare.py` for 5.10, 5.15, 6.1, 6.6
or 6.18.

```sh
KMI_SRC=/path/to/kernel KMI_OUT=/path/to/out KMI_BRANCH=android16-6.12 KMI_GENERATION=6 KMI_ARCH=aarch64 kernel/dm-thin-pool/build.sh
```

or directly:

```sh
make -C kernel/dm-thin-pool KMI_SRC=/path/to/kernel KMI_OUT=/path/to/out KMI_BRANCH=android16-6.12 KMI_GENERATION=6 KMI_ARCH=aarch64 JOBS=4
```

- Each module uses explicit `KMI_SRC`, `KMI_OUT`, `KMI_BRANCH`,
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
| `src/` | device-mapper sources: the verified vendored tree here, or per-line sources staged by `prepare.py` (`dm-thin`, `dm-thin-metadata`, `dm-bufio`, `dm-io`, `dm-kcopyd`, `dm-bio-prison-v1/v2`) |
| `src/persistent-data/` | persistent-data helpers (btree, bitset, array, block/space maps, transaction manager) |
| `private-rename.h` | private `thinpool_private_*` renames for every non-exported symbol |
| `src/subsystems.h` | shared declarations for the subsystem init and exit entry points |
| `abi/<line>/port.py` | per-line ABI policy: profile, edited sources in order and the version-specific edits; shared transformations stay in `prepare.py` |
| `prepare.py` | validates one kernel line, stages its sources with the selected ABI policy, writes `PROVENANCE.json` |
| `Kbuild`, `Makefile` | standalone module definition and exact-identity build wrapper; `Kbuild` reads an optional `stage.mk` for the staged include directory |
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
dmsetup targets                         # thin-pool and thin; version from the staged line
```

The recorded proof covers the 6.12 vendored sources only: arm64 build, valid
modpost and signed `insmod` against ACK `f1bdb13583da85a47fcf1632a78ef52d6e6da651`;
and the full dm-thin behavior matrix in QEMU (snapshots, discard, partial-block
zeroing, `dm-default-key` ciphertext equality, ENOSPC modes, forced-reset
metadata recovery).

The 5.10, 5.15, 6.1, 6.6 and 6.18 sources are staged by `prepare.py` and are
not built, admitted, loaded or exercised yet. A staged tree is a source claim,
not a behavior claim. The 5.10 staging was established against the pinned
`android12-5.10` 5.10.252 DDK image; its `PROVENANCE.json` records the exact
source hashes and all 60 counted edits. The staged 6.18 `src/dm-thin.c` keeps
the upstream `DM_TARGET_PASSES_CRYPTO` flags. The 5.10, 5.15, 6.1 and 6.6 ABI
files add the same flags, because those lines' `dm-table.c` drops
inline-encryption capabilities for a stack whose target lacks the flag and the
thin data path keeps the bio crypt context. The encrypted 5.10, 5.15, 6.1 and
6.6 stacks are unproven until each lane builds and runs the encryption checks.

## Product build gates

`just gate <branch> <generation> <aarch64|x86_64> <source> <complete-output>`
builds both independent kernel modules.
Output follows `OUT_DIR`, which defaults to `out/build-matrix` and must stay
inside the repository's ignored `out/` tree. Each run writes:

| Path | Contents |
| --- | --- |
| `$OUT_DIR/modules/<branch>-<generation>/<arch>/<project>/` | module, build log, build-info JSON and `set.json` |
| `$OUT_DIR/prepared/<branch>-<generation>/<arch>/dm-thin-pool/` | staged dm-thin-pool sources, `abi/` policy files and `PROVENANCE.json` |
| `$OUT_DIR/module-src/<branch>-<generation>/<arch>/<project>/` | staged sources of the other module |

The gate re-admits the exact shipped bytes. No stripping or mutation follows.
The build tools refuse an existing prepared, staged or output directory, so a
rerun needs a fresh `OUT_DIR`.
`just host-contract` runs the ELF, identity, build-info, module-set and KMI
helper tests. It does not build init or daemon products.

CI runs host contract tests and the canonical digest-pinned arm64 DDK lane on pushes and pull requests. Manual dispatch can run the caller-supplied ACK lane on the prepared self-hosted `egysk-kmi` runner. Both lanes use complete matching KMI references. Header-only inputs and `modules_prepare` do not provide admission inputs. CI uploads artifacts only.

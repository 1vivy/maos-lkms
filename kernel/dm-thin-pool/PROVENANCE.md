# Provenance of `dm-thin-pool`

This subtree provides a separate GPL-2.0-only kernel module. It contains vendored Linux device-mapper thin-provisioning sources, adapted to load as an out-of-tree module against the target KMI. The module remains separate from the GPL-3.0 maos core. The repository's top-level `LICENSE` does not cover this subtree.

The source bundle and phone artifact came from a local proof workspace. That workspace was not a product repository. The vendored sources, private rename header, and fork patch remain auditable here.


## 1. Origin

- Upstream sources: Linux kernel 6.12 device-mapper thin family
  (`drivers/md/dm-thin.c`, `dm-thin-metadata.c`, `dm-bufio.c`, `dm-io.c`,
  `dm-kcopyd.c`, `dm-bio-prison-v1.c`, `dm-bio-prison-v2.c` and
  `drivers/md/persistent-data/*`), each file carrying its upstream
  `SPDX-License-Identifier: GPL-2.0-only` and Red Hat/Sistina copyright and
  `MODULE_LICENSE`-style GPLv2 notice.
- Vendored tree: `https://github.com/OnePlusOSS/android_kernel_common_oneplus_sm8850`
  at commit `d9053b907db4bb5da938e9cf947d0ae32302ceaf`
  (kernel release `6.12.23-4k-gd9053b907db4`; see
  `records/20260929T015230Z-stage1/record.md`).
- Independent fork work: commit `9b05293da905d871fd01eefcd31c661f13ab1eee`
  ("fork dm-thin for exported KMI surface", author `1vivy`), exported as
  `patches/0001-fork-dm-thin-for-exported-KMI-surface.patch`.
- ACK build commits the module was built and proven against:
  - `f1bdb13583da85a47fcf1632a78ef52d6e6da651` (`android16-6.12`,
    kernel `6.12.23-4k-gf1bdb13583da`, KMI lineage `android16-6.12-2025-06_r8`):
    arm64 build, valid modpost, signed `insmod`, both targets registered
    (`records/20260929T020200Z-stage2b`, `20260929T030000Z-stage6`,
    `20260929T030100Z-stage7`, `20260929T034000Z-stage7b`).
  - `925a103d123c30a84577f29e1573376aacbde94b` (`android16-6.12`,
    kernel `6.12.58-4k-g925a103d123c`): the phone-matched build
    (`records/20260929T034940Z-phone-build`, `records/20260929T035316Z-phone-ram3`).

## 2. Imported file set

The vendored `.c`/`.h` implementation and private rename header were copied from
the historical proof bundle and verified against the SHA-256 list below:

- `thin-main.c` — the module entry point. Provenance note: it is the imported
  `bundle/bundle-main.c` with the maos changes of section 4; the proven file
  as it existed at import time is patch hunk 1 of
  `patches/0001-fork-dm-thin-for-exported-KMI-surface.patch`.
- `private-rename.h` — the private symbol rename header.
- `src/*.c`, `src/*.h` (10 files: 7 `.c`, 3 `.h`) and
  `src/persistent-data/*.c`, `src/persistent-data/*.h` (21 files: 10 `.c`,
  11 `.h`) — the vendored kernel sources, 31 files in total.

No other file was copied. In particular the proof bundle's build outputs were
deliberately excluded: `*.o`, `.*.o.cmd`, `*.ko`, `*.mod.c`, `*.mod`,
`Module.symvers`, `modules.order` and `Module.symvers.cmd`/`modules.order.cmd`.

SHA-256 of the current source set (the vendored implementation set and
`private-rename.h` remain unchanged from the proven bundle; `thin-main.c`
includes the maos integration changes in section 4):

```
f96c6ebe943403a0e1dfc35c839ccc4ff5955e8c0d56e099df183b21828e3ab0  thin-main.c
8bb7e68195ca466094fb3d64dc9282995dc543a289b6bc54dff1972e287362f9  private-rename.h
d994221868e2f441e88888e377a7aba5836aba126d14ea82a734459095535275  src/dm-bio-prison-v1.c
5cef7b5b636614a691d3782892977265a95f2b9090566e991a182cbebaac61f9  src/dm-bio-prison-v2.c
6740f8e0c0f13b8026d6ba6b30465d170b9386eb56888cb37382d78e4aad478f  src/dm-bufio.c
aa0cb17c1a31abe8249563448a9bdd30aab4952e837c39381c87dceb9e7d7c2c  src/dm-io.c
32488a131fedf157dd3e8c2b5cbf77b80fed6dbc133818457e977cfea4b53521  src/dm-kcopyd.c
b1d40f9086947ce4cff082bf5ac4b65630e2c7a2233369e273b951995eb4d48f  src/dm-thin-metadata.c
aa3fe38bfd29135c133a376b18a55570cd230afa3788465d72f2b1fe6891fd22  src/dm-thin.c
1965f9ebb0274935e78c673569dbf17aefae861fcb28a5662fc515c0c05bd8cf  src/dm-bio-prison-v1.h
0cb32053830b353f54382ca66cb86212a1ec83228491ae000f9e94e4cd73ac74  src/dm-bio-prison-v2.h
d0258a5448e2a35d29792d50992659412a5b08c3501e5bf55e4f3a372c41b597  src/dm-thin-metadata.h
16ca5e76f3023a2b0c9d7e042b0cc953f95066519f611e09e05b2725ab5a063e  src/persistent-data/dm-array.c
aba614f2326be972e86c46df1f3f6c14e0368bfd246c8adce6c9279a1cbbff5e  src/persistent-data/dm-bitset.c
598d5c00778e5e47478681f9b2e3e22486874dbb42a605f596d29c7f54b8c15c  src/persistent-data/dm-block-manager.c
cee3793cc9128677831f1d0c2b0229e64aca54be08136d7b3f5433262f30b40c  src/persistent-data/dm-btree-remove.c
ac79507e0366986ecb78a824d87723dfd3ac92da116f15796afd57bd7f5ed245  src/persistent-data/dm-btree-spine.c
797d4dd002d54705cff6b8e0a6c008272e46fcf6a0aab18281904f623c241333  src/persistent-data/dm-btree.c
263fe7568f7aaa4307ad75089a2593d3d597635e1b822b3a8d755bac56a9eb22  src/persistent-data/dm-space-map-common.c
f52627e7a33fbe44171434d1acc81499332b8473054f6ce0f26985952be3110d  src/persistent-data/dm-space-map-disk.c
8266409840113aa0d9fd8feae868f290d61ecadccc17b34c98379d26feeaf5d7  src/persistent-data/dm-space-map-metadata.c
0aad2725d013252781ba6cc388265484e1f82067b58c19a45c64133386d7425f  src/persistent-data/dm-transaction-manager.c
f23f83b728313ebb735493563d337167436bce1dcbe5d30b6ec714cf6465291a  src/persistent-data/dm-array.h
8c1381125a1ae40f5656441a418c694f0771d28b61221151a84ae08e6cb7d167  src/persistent-data/dm-bitset.h
fac4b0a1cadd294b6ecc6ad77367bd41185e8aa8efc59ff82d1607988478183f  src/persistent-data/dm-block-manager.h
1b3fc2f307a2600e053a894cabb0a6e3cf5c0c4c7fc62e30c9e80776fa349bf5  src/persistent-data/dm-btree-internal.h
24370fec1b1eff612e4b0201a340a73533a82c00c43b9b596a27f0717010432f  src/persistent-data/dm-btree.h
c9d5c51933400d58bf36f57919e5022cc3d282a1d95d90f8b347983e78004758  src/persistent-data/dm-persistent-data-internal.h
2a0a12932038ab1d99479ade2d8f48e8ae81f59701a55a05c2ebdd96a316e517  src/persistent-data/dm-space-map-common.h
6ac14dbee5df2336bc266e7d05cb0ae7b99d91c67d23abe8cfca96a40bb22bc0  src/persistent-data/dm-space-map-disk.h
72afb1bea951a5e886871ecb7e3e3968449d920145680743f5663a8de59777f0  src/persistent-data/dm-space-map-metadata.h
a316ee9bea9bda8e0b8901c3405e749fa4527f2a190da5668ef8ffc48a360e77  src/persistent-data/dm-space-map.h
1480b1d373716f1fd890c7eaa2c0fab452017f20fb92536fc7d2b4eb3fa1f7a2  src/persistent-data/dm-transaction-manager.h
```

`src/subsystems.h` is a project header, not imported source. It declares the
subsystem init and exit entry points that `thin-main.c` calls. `thin-main.c`
and the generated subsystem sources include it, so each definition has a prior
prototype. Kernel 6.18 compiles modules with `-Wmissing-prototypes`, and its
build rejects an undeclared global entry point.

`thin-main.c` includes that header instead of repeating the ten declarations.
It is otherwise the imported `bundle-main.c` with the maos changes of section 4.

`patches/0001-fork-dm-thin-for-exported-KMI-surface.patch` is the proof
workspace's patch file, byte for byte (SHA-256
`54044d93a6918e2908da89a1df3d0ccc2b3307be285c6ce20b23114880a88db0`). Its paths
(`bundle/...`) are relative to the proof workspace, so it documents the fork
against the proof layout rather than applying onto this subtree as a plain
`-p1` patch.

## 3. What the fork changed

`patches/0001-fork-dm-thin-for-exported-KMI-surface.patch` (213 insertions,
116 deletions over `bundle-main.c`, `src/dm-bufio.c`, `src/dm-kcopyd.c`,
`src/dm-thin.c`) makes the bundled code self-contained against the exported KMI:

- `src/dm-bufio.c` replaces module-internal helpers with private equivalents: a
  private `thinpool_errno_to_blk_status()` instead of `errno_to_blk_status()`,
  private `wait_on_bit_io`/`wait_on_bit_lock_io` wrappers instead of
  `bit_wait_io`, and a module-owned `bio_set` (`bio_alloc_bioset()`/`bio_put()`)
  instead of `bio_kmalloc()` with `bio_uninit()`/`kfree()`. That bio set is
  allocated in `thinpool_private_bufio_init()` and released in
  `thinpool_private_bufio_exit()`, including on the init failure path.
- `src/dm-kcopyd.c` makes `dm_get_kcopyd_subjob_size()` read
  `kcopyd_subjob_size_kb` with `READ_ONCE()` and clamp it, instead of calling
  the module-internal `__dm_get_module_param()`.
- `src/dm-thin.c` is reduced to the exported KMI surface: it stops calling
  module-internal helpers such as `dm_table_get_md`, `dm_device_name`,
  `dm_get_md`, `dm_put`, `dm_suspended`, `dm_noflush_suspending`,
  `dm_internal_suspend_noflush` and `dm_internal_resume` (it tracks its own
  `pool->name`), and carries the private pool gate/suspend/resume rework
  described in the proof `README.md`.
- `bundle-main.c` (now `thin-main.c`) adds the `dm_kcopyd_init()` step and the
  matching `dm_kcopyd_exit()` calls that the in-tree `dm-mod.c` performs for the
  `dm-io`, `dm-kcopyd` and `dm-bufio` subsystems, in the init order and in every
  failure-unwind branch and in exit.
- `private-rename.h` renames every dm/persistent-data symbol in the vendored
  copies to `thinpool_private_*`, so the module neither defines nor overrides a
  kernel symbol. The list also covers symbols the matching kernel exports; the
  6.1 line exports `dm_bufio_release_move`, which the vendored 6.12 list did not
  have. The device-mapper target names stay `thin-pool` and `thin`, and the
  proven `thinpool_private_*` symbols are retained.

`records/20260929T030000Z-stage6/record.md` records the resulting import audit:
151 unique undefined imports and a **PASS** on the forbidden-import list, i.e.
none of the removed module-internal symbols remains an undefined symbol.

## Kernel-line porting

The module serves more than one GKI kernel line only when each line contributes
its own device-mapper sources. The dm-thin family changed between lines in its
interfaces and in its data path. One snapshot cannot compile and behave
correctly on all of them.

`prepare.py` implements that rule:

| Line | Device-mapper sources | Profile |
| --- | --- | --- |
| 6.1 | that line's kernel source, ported | generated |
| 6.12 | section 2's vendored tree, byte for byte | verified |
| 6.18 | that line's kernel source, ported | generated |

For a generated line the tool copies
`drivers/md/dm-thin.c`, `dm-thin-metadata.c`, `dm-thin-metadata.h`,
`dm-bufio.c`, `dm-io.c`, `dm-kcopyd.c`, `dm-bio-prison-v1.c/.h`,
`dm-bio-prison-v2.c/.h` and `drivers/md/persistent-data/*.c/*.h` from the
matching source, then applies a fixed edit programme. The programme is more
than a rename list:

- The pool table is keyed by the control target's stable table name and by the
  pool block device `dev_t`. The pool keeps its own name for diagnostics. The
  thin target resolves the pool through that table instead of a mapped device.
- The suspend path uses the private gate described in section 3. It does not
  call `dm_internal_suspend_noflush()` or `dm_internal_resume()`. Suspend and
  resume ordering, retained bios and postsuspend commit stay as the verified
  tree defines them.
- Kernel-internal helpers the module must not import are replaced: the pool and
  thin mapped-device helpers, `dm_suspended()`, `dm_noflush_suspending()`,
  `errno_to_blk_status()`, `wait_on_bit_io()`, `bit_wait_io()`,
  `bio_kmalloc()`/dynamic `bio_init()`, `__dm_get_module_param()` and the
  `KMEM_CACHE` slab names. The buffered I/O path allocates from a module-owned
  `bio_set` that is created in the private bufio init and released in its exit,
  including the workqueue failure path.
- The composed module keeps exactly one `module_init`/`module_exit` pair in
  `thin-main.c`. The subsystem files lose their own module hooks and expose
  `thinpool_private_*` init and exit entry points. `src/subsystems.h` declares
  those entry points once, and each defining source includes it, because 6.18
  rejects a global definition without a prior prototype. The definitions stay
  externally linked: the programme drops an upstream `static` from those
  definitions, and it rejects a static `dm_io_init`/`dm_io_exit` or
  `dm_kcopyd_init`/`dm_kcopyd_exit` that `thin-main.c` calls.
- Every symbol the staged DM family exports needs a rename line in
  `private-rename.h`. The tool reads each `EXPORT_SYMBOL` and `EXPORT_SYMBOL_GPL`
  line in the staged sources and fails staging with the symbol and file when a
  rename is absent. The matching kernel source decides the export set, and the
  count is recorded in `PROVENANCE.json`. Kernel 6.1 exports
  `dm_bufio_release_move`, which the 6.12 list did not cover.
- The private errno-to-status helper follows each line's own `blk_errors[]`
  table in `block/blk-core.c`. The 6.18 line has `BLK_STS_INVAL`, so -EINVAL
  maps to it. The 6.1 line has no such status and maps -EINVAL to
  `BLK_STS_IOERR`, as its own `errno_to_blk_status()` does. The programme
  rejects a mapping that names a status the line lacks.
- Both targets declare `DM_TARGET_PASSES_CRYPTO`, and `pool_ctr` rejects a pool
  that does not set `skip_block_zeroing`. An encrypted thin pool must not write
  zeroes below the encryption target, and a stacked device keeps its
  inline-encryption capabilities only when every member target passes them.
  Upstream 6.1 predates the flag, so its programme adds it. Upstream 6.18 has
  the flag, so its programme asserts it. The 6.12 verified tree already has
  both the flags and the zeroing policy.
- `private-rename.h` still renames the private cross-file symbols. A generated
  tree records which renames the line's sources do not use. A rename the
  header lacks cannot be detected without a build, so modpost and KMI admission
  remain the detection point for a new private symbol.

Each edit must match exactly the number of times the programme declares. A
kernel line that changed one of those regions fails staging with the file, the
edit name and the anchor text. The tool accepts only the lines in the table
above.

### Inputs and recorded provenance

`prepare.py` requires the exact ACK `--branch`, its `--generation`, the
`--arch`, the matching `--kernel-source` and a complete `--kernel-output`
(`.config`, `Module.symvers`, `System.map`, `include/generated/utsrelease.h`).
It checks the following:

- The branch line equals the source `Makefile` version line.
- The output `UTS_RELEASE` is from that same line.
- Every ACK identity declaration that exists matches the call. The 6.1 line
  declares `BRANCH` in `build.config.constants` and generation 11 in
  `build.config.common`. The 6.12 line declares branch and generation 6. The
  6.18 line declares branch and generation 5 through a symlink to
  `bazel/constants.scl`. Absence is recorded, never invented. The repository
  `scripts/kmi_modules.py` reads the same files, so the same triple reaches
  admission.
- The `--output` path does not exist. The tool stages through a unique
  temporary sibling and renames it on success. A failure removes only that
  temporary directory.
- The staged `src/*.c` set equals the `Kbuild` member list.
- The staged tree copies each project header in `PROJECT_HEADERS`
  (`src/subsystems.h`) from this module tree. Generated sources include it, and
  the kernel source has no such file. Its hash appears in `module_inputs` and in
  `files`.
- The staged sources contain the required private tokens and none of the
  replaced internals.
- The staged `dm-thin.c` defines `thin-pool` and `thin` and records its version
  triple.

The staged `PROVENANCE.json` records the kernel source file hashes, the output
file hashes, the module file hashes, every applied edit with its before and
after anchor hashes, the replaced helper inventory, the private rename count
and the target version triples.

### Method source and licence

The practice of a version-keyed kernel patch set per kernel line comes from
Droidspaces, which documents per-line kernel configuration and patches at
<https://www.droidspaces.org/docs/kernel-configuration.html>. That practice
informed this design. No Droidspaces code is copied. Generated sources are
Linux kernel sources from the matching line, under their own `GPL-2.0-only`
notices.

### Line differences and open limits

- Crypto passthrough was reconciled from source, not assumed. The DDK 6.18 and
  6.12 `dm-thin.c` files differ at the feature flags only, apart from version
  bumps and two unrelated cleanups. The 6.1 `dm-table.c` calls
  `dm_target_passes_crypto()` and intersects the stacked device's
  inline-encryption capabilities to none when a member target lacks the flag.
  The thin data path remaps through `bio_set_dev()` and keeps the per-bio crypt
  context. The 6.1 programme therefore adds `DM_TARGET_PASSES_CRYPTO` to both
  targets, which matches the OnePlus 6.12 vendor tree and upstream 6.18. The
  encrypted 6.1 stack stays unproven until that lane runs the encryption
  checks.
- The 6.1 dm-bufio carries two Android vendor trace hook calls
  (`trace_android_vh_dm_bufio_shrink_scan_bypass` and
  `trace_android_vh_cleanup_old_buffers_bypass`). The DDK 6.1 image exports
  those hooks, so the port keeps the vendor behavior.
- No generated tree is built, admitted, loaded or exercised. Snapshots,
  discard, ENOSPC, suspend/resume and metadata recovery behavior on 6.1 and
  6.18 are unproven. A build and the KMI admission of the exact artifact are
  the next required evidence.

## Module integration

The vendored source and private rename header remain auditable in this subtree. Product integration adds the standalone module entry point, build files, and module metadata.
The module builds as `dm-thin-pool.ko` and loads as `dm_thin_pool`. It registers the `thin-pool` and `thin` device-mapper targets. The private rename header prefixes non-exported symbols with `thinpool_private_`.

`thin-main.c` exposes the read-only `ready` parameter. It reports `Y` after all subsystems and both targets initialize. It returns to `N` when unload teardown starts. The module initializes and cleans up its vendored subsystems in order, including every failure path.

The subtree is GPL-2.0-only. Its `LICENSE` file is the verbatim Linux kernel GPL-2.0 license text. Upstream source notices remain in vendored files.

## Build and admission

The standalone build uses explicit matching KMI source and output. The repository gate runs `scripts/kmi_modules.py` on the exact module artifact. Admission requires each import in the target KMI export list or target `System.map` with `CONFIG_KALLSYMS_ALL=y` for private imports. It checks the CRC of a present `module_layout` record against the published KMI CRC. It does not require matching CRCs for other imports. See the repository README for build commands.

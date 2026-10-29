# Provenance and licensing

The current `configfs.c` and `target.c` implement the configfs ABI 6 projection interface. Their base derives from the selected local `mockups/2026-10-09/partformer/kernel` source. Product changes add bounded geometry uploads, per-disk GPT metadata staging, device-mapper targets, and physical namespace ancestry through upstream `device_move`.

`pp-range` follows upstream dm-linear (Sistina Software 2001-2003); its provenance comment remains in source. Device-mapper owns data BIO, queue, and crypto stacking. This module does not provide a standalone gendisk, physical GPT writer, or crypto-profile engine.

The subtree is GPL-2.0-only. `LICENSE` supplies the full GPL v2 text. No binary, extracted firmware code, downstream patch, or third-party GPT module was imported.

Public Linux v6.12 interfaces consulted during implementation:

- [include/linux/blkdev.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/blkdev.h)
  — file-based bdev opens, dynamically allocated bio-based disks, initial disk
  registration/partition scan, partition metadata, atomic per-bdev flags,
  `blk_set_stacking_limits`, `queue_limits_stack_bdev` and exported `submit_bio`.
- [include/linux/blk_types.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/blk_types.h)
  — partition/whole-disk relationship, sector offsets and bio representation.
- [include/linux/blk-crypto-profile.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/blk-crypto-profile.h),
  [include/linux/blk-crypto.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/blk-crypto.h)
  and [block/blk-crypto-profile.c](https://github.com/torvalds/linux/blob/v6.12/block/blk-crypto-profile.c)
  — slotless stacking profile, lower capability intersection and key eviction.
- [block/bio-integrity.c](https://github.com/torvalds/linux/blob/v6.12/block/bio-integrity.c)
  — integrity payload allocation semantics for cloned bios.
- [drivers/block/brd.c](https://github.com/torvalds/linux/blob/v6.12/drivers/block/brd.c)
  — conventional bio-based disk operations and page mapping for RAM metadata.

`bdev.h` selects the block-device open, release, read-only, publication-state
and partition-iteration interface of the target tree. Each supported line has
its own port with the same interface:

`pp_bdev_handle`, `PP_OPEN_READ`, `pp_bdev_open_ro`, `pp_bdev_close`,
`pp_bdev`, `pp_bdev_info`, `pp_bdev_dev`, `pp_disk_ref`, `pp_disk_hold`,
`pp_disk_drop`, `pp_disk_lock`, `pp_disk_unlock`, `pp_disk_openers`,
`pp_disk_dead`, `pp_scan_state`, `pp_disk_scan_suppressed`, `pp_disk_scan_save`,
`pp_disk_scan_restore`, `pp_disk_scan_enable`, `pp_part_ref`, `pp_part_hold`,
`pp_part_put`, `pp_part_read_only`, `pp_part_ro`, `pp_for_each_part`,
`pp_bvec_map`, `pp_bvec_unmap`.

| Port | Used for | Implementation |
| --- | --- | --- |
| `abi/5.10/bdev.h` | 5.10 | `blkdev_get_by_dev`, `blkdev_put`, `hd_struct.info`/`policy`, retained `bdget_disk(disk, 0)` with `bd_mutex` and `bd_openers`, `GENHD_FL_UP`, `GENHD_FL_NO_PART_SCAN`/`GENHD_FL_EXT_DEVT`, `disk_part_iter_*` with `bdget_disk(partno)`, `kmap_atomic` |
| `abi/5.15/bdev.h` | 5.15 | `blkdev_get_by_dev`, `blkdev_put`, `bd_meta_info`, `&bd_device`, `bd_read_only`, `disk->open_mutex`, `part0->bd_openers`, `GD_DEAD`, `GENHD_FL_NO_PART`, `part_tbl`, `bvec_kmap_local` |
| `abi/6.1/bdev.h` | 6.1 | `blkdev_get_by_dev`, `blkdev_put`, `bd_meta_info`, `&bd_device`, `bd_read_only`, `disk->open_mutex`, `disk_openers`, `GD_DEAD`, `GENHD_FL_NO_PART`, `part_tbl`, `bvec_kmap_local` |
| `abi/6.6/bdev.h` | 6.6 | `bdev_open_by_dev`/`bdev_release`, `bd_meta_info`, `&bd_device`, `bd_read_only`, `disk->open_mutex`, `disk_openers`, `GD_DEAD`, `GENHD_FL_NO_PART`, `part_tbl`, `bvec_kmap_local` |
| `abi/6.12/bdev.h` | 6.12 | `abi/file-bdev.h` |
| `abi/6.18/bdev.h` | 6.18 | `abi/file-bdev.h` |

`abi/file-bdev.h` holds the file-based implementation that 6.12 and 6.18 share:
`bdev_file_open_by_dev`, `file_bdev`, `bdev_fput`, `bdev_set_flag`,
`bdev_clear_flag` and `BD_READ_ONLY`. The two lines have no difference in this
boundary, so they share one implementation and keep separate ports for their
own provenance. `bdev.h` selects a port from `LINUX_VERSION_CODE` and stops the
build with an error on any line that has no port. It does not apply one line's
code to another line. `configfs.c` exports the selected line as the
`part_projection_bdev_abi` `.modinfo` entry.

The pinned DDK trees define the supported generations:

- `ghcr.io/ylarod/ddk-min@sha256:272ada1e61c525116032246df2a790d1ccec1804b7a9e0b09203c5e650dcb78e`
  (`/opt/ddk/src/android12-5.10`, 5.10.252, `KMI_GENERATION=9`) supplies
  `blkdev_get_by_dev`, `blkdev_put`, `bdget_disk`, `bdput`, `bdgrab`,
  `bd_openers`, `bd_mutex`, `GENHD_FL_UP`, `GENHD_FL_NO_PART_SCAN`,
  `GENHD_FL_EXT_DEVT`, `disk_part_iter_init`/`disk_part_iter_next`/
  `disk_part_iter_exit`, `set_disk_ro`, `get_disk_ro`, `dm_get_md`,
  `DPM_ORDER_DEV_AFTER_PARENT` (`include/linux/pm.h:833`) and
  `DM_TARGET_PASSES_CRYPTO`. It has no `disk_openers()`, no `GD_DEAD`, no
  `GENHD_FL_NO_PART`, no `bd_meta_info`, no `bd_device` and no
  `kmap_local_page()`/`bvec_kmap_local()`, and it does not export `bdget_part`,
  `get_gendisk` or `dm_open_count`.
- `ghcr.io/ylarod/ddk-min@sha256:9e68cd9fcab748584755d31ba88ef134efc938dbde17f258c2652315f6cd81cd`
  (`/opt/ddk/src/android13-5.15`, 5.15.202) supplies `blkdev_get_by_dev` and
  `blkdev_put` with an `fmode_t` mode, `bd_read_only`, `bd_meta_info`,
  `GENHD_FL_NO_PART`, `GD_DEAD`, `disk_to_dev`, `set_disk_ro`, `get_disk_ro`,
  `part_tbl`, `DPM_ORDER_DEV_AFTER_PARENT` and `DM_TARGET_PASSES_CRYPTO`. It has
  no `bdev_handle`, no `disk_openers()` and no `BD_*` flags.
- `ghcr.io/ylarod/ddk-min@sha256:1dd6ac340b627a90a4031d6d0df6b129d8cc949b139fb56032c898f023d3d5d3`
  (`/opt/ddk/src/android14-6.1`) supplies `blkdev_get_by_dev`, `blkdev_put`,
  `bd_read_only`, `bd_meta_info`, `disk_openers`, `set_disk_ro`,
  `GENHD_FL_NO_PART`, `GD_DEAD` and `DPM_ORDER_DEV_AFTER_PARENT`. It has no
  file-based open helper, no `BLK_OPEN_READ` and no `BD_*` flags.
- `ghcr.io/ylarod/ddk-min@sha256:51159bc935c75a282fc65bc87e02f16bd098d1cdf55dc558c4fdd0fcf7a132e2`
  (`/opt/ddk/src/android15-6.6`, 6.6.127) supplies `bdev_open_by_dev`,
  `bdev_release`, `blk_mode_t` open modes, `bd_read_only`, `bd_meta_info`,
  `disk_openers`, `set_disk_ro` and `GENHD_FL_NO_PART`. It has no
  `bdev_file_open_by_dev`, no `bdev_set_flag` and no `BD_*` flags.
- `ghcr.io/ylarod/ddk-min@sha256:fd3ec5cc71d7f2716212e9df8d5674a9afe68fb769282fcac87b83f207f949ee`
  (`android16-6.12`) and
  `ghcr.io/ylarod/ddk-min@sha256:fb8b66200bf402cf65a751060fc1aa29524b9fa8840feef16c7b196a4f3f0e6e`
  (`android17-6.18`) supply `bdev_file_open_by_dev`, `file_bdev`, `bdev_fput`,
  `bdev_set_flag`, `bdev_clear_flag` and `BD_READ_ONLY`.

### 5.10 sources

The port implements these contracts from the pinned 5.10.252 tree:

- A reference is not an opener. `bd_openers` and `bd_part_count` increase only
  after the driver open succeeds (`fs/block_dev.c:1568-1570`). `bdget_disk()`
  resolves the partition dev_t with `bdget()` and returns an unopened bdev
  (`block/genhd.c:1048-1060`, `fs/block_dev.c:948-951`); `bdev_alloc()`
  initializes its `bd_mutex` (`fs/block_dev.c:818`). Holding that reference
  therefore cannot make a disk busy or block DM teardown.
- Partition openers reach the whole device. A partition's first open recurses
  into the whole device with `for_part=1`, and later opens of that partition
  skip the recursion (`fs/block_dev.c:1496`, `1537-1543`). `whole->bd_openers`
  is nonzero whenever any whole or partition opener exists; `bd_part_count`
  counts open partitions separately (`include/linux/blk_types.h:40`).
- The whole device's `bd_mutex` (`include/linux/blk_types.h:28`) is the
  open/close serialization. `__blkdev_get()` holds it across the open callback
  and the counter update (`fs/block_dev.c:1496-1568`); `__blkdev_put()` holds it
  across the release callback and the decrement (`fs/block_dev.c:1771-1806`).
  A partition reread reopens the whole device under that same lock
  (`block/ioctl.c:100-120`).
- The retained reference is only a lock and counter handle. `bd_part` is set on
  the first open and cleared, together with `bd_disk` and `bd_contains`, on the
  last close (`fs/block_dev.c:1505-1506`, `1543`, `1802-1806`). Partition
  metadata and policy therefore come from the `hd_struct` that
  `disk_part_iter_next()` returns with a device reference
  (`include/linux/genhd.h:292-303`), or from an endpoint the module keeps open.
- Deadness is `GENHD_FL_UP`. `del_gendisk()` invalidates every partition and
  part0, then clears the flag (`block/genhd.c:906-919`, flag at 918). 5.10 has
  no `GD_DEAD`.
- Partition scanning needs `GENHD_FL_EXT_DEVT` on this line. `disk_max_parts()`
  returns `disk->minors` unless that flag is set, and
  `disk_part_scan_enabled()` additionally requires `GENHD_FL_NO_PART_SCAN` to be
  clear (`include/linux/genhd.h:245-255`). `disk_expand_part_tbl()` rejects a
  partno at or beyond `disk_max_parts()` (`block/genhd.c:1515-1517`), and
  `blk_alloc_devt()` switches to `ext_devt_idr` beyond `disk->minors`
  (`block/genhd.c:574-598`). DM allocates its disk with one minor and sets no
  scan flag (`drivers/md/dm.c:1849`). The port therefore records
  `GENHD_FL_NO_PART_SCAN`/`GENHD_FL_EXT_DEVT`, expresses suppression as
  `!disk_part_scan_enabled()`, enables scanning by setting `GENHD_FL_EXT_DEVT`
  and clearing the scan flag, and restores only those two bits, never
  `GENHD_FL_UP`.
- Partition read-only policy is `hd_struct.policy`: `bdev_read_only()` returns
  it and `set_device_ro()` stores it (`block/genhd.c:1850-1882`). The port
  stores the same field.
- Teardown race. `__dm_destroy()` sets `DMF_FREEING` and `MINOR_ALLOCED` under
  `_minor_lock` (`drivers/md/dm.c:2236-2241`) before `cleanup_mapped_device()`
  runs `del_gendisk()` and `put_disk()` (`drivers/md/dm.c:1769-1771`).
  `dm_blk_open()` returns `-ENXIO` while `DMF_FREEING` is set or the device is
  being deleted (`drivers/md/dm.c:297-319`), and it runs inside the `bd_mutex`
  section that increments `bd_openers`, so a zero read under that lock cannot be
  followed by an increment. `invalidate_partition()` unhashes the bdev inode
  (`block/genhd.c:854-873`), so a fresh `bdget_disk()` after death would create a
  new bdev with a zero count; the retained reference is the only valid source.
- Symbols. `bdget_disk`, `bdgrab`, `bdput`, `set_device_ro`, `bdev_read_only`,
  `disk_part_iter_*`, `put_disk` and `dm_get_md` are exported by this tree;
  `bdget_part`, `get_gendisk` and `dm_open_count` are not, and the port does not
  use them.

Every port holds one open reference per handle and releases it once. No line
rejects a write open at open time. All six enforce read-only state in
`blkdev_write_iter()` and in mmap through `bdev_read_only()`. On 5.10 the port
stores `hd_struct.policy`, the field `bdev_read_only()` returns and
`set_device_ro()` writes (`block/genhd.c:1850-1882`). On 5.15, 6.1 and 6.6 the
module assigns `bd_read_only`, which is the field that the same line's
`BLKROSET` handler writes with the same plain store (`block/ioctl.c`,
`blkdev_roset`). On 6.12 and 6.18 the module sets and clears `BD_READ_ONLY`.
5.10 and 5.15 expose `bd_openers` as a plain `int`, so their ports read it while
holding the lock that guards it: the whole device's `bd_mutex` on 5.10 and
`disk->open_mutex` on 5.15. On both lines the count includes every open
partition, because a partition's first open takes one whole-device open and only
its final close drops it (`fs/block_dev.c:1537-1543` in 5.10, `block/bdev.c` in
5.15.202). Lines that have no port are not claimed, and `bdev.h` stops their
build with an error.

### Build and admission evidence (2026-10-29)

Each check ran from the repository root into a fresh `--output-dir` under the
ignored `out/` tree, with `--arch aarch64`, `--jobs 4`, the image's clang
directory first on `PATH` and repeated in `DDK_CLANG_DIR`, against the image's
own `/opt/ddk/src/<branch>` and `/opt/ddk/kdir/<branch>`:

```
docker run --rm --user $(id -u):$(id -g) -v "$PWD:$PWD" -w "$PWD" \
  -e PATH=<clang>/bin:/usr/local/bin:/usr/bin:/bin -e DDK_CLANG_DIR=<clang> \
  --entrypoint python3 <image> scripts/kmi_modules.py build \
  --module-dir kernel/part-projection --module part-projection \
  --branch <branch> --generation <n> --arch aarch64 \
  --kmi-src /opt/ddk/src/<branch> --kmi-out /opt/ddk/kdir/<branch> \
  --output-dir out/part-projection-<line>-final --jobs 4
```

| Line | Image digest (prefix) | clang | gen | Result | Emitted ABI |
| --- | --- | --- | --- | --- | --- |
| android12-5.10 | `272ada1e61c5` | r416183b | 9 | accepted (build and verify) | `5.10` |
| android13-5.15 | `9e68cd9fcab7` | r450784e | 8 | accepted (build) | `5.15` |
| android14-6.1 | `1dd6ac340b62` | r487747c | 11 | accepted (build and verify) | `6.1` |
| android15-6.6 | `51159bc935c7` | r510928 | 8 | accepted (build) | `6.6` |
| android16-6.12 | `fd3ec5cc71d7` | r536225 | 6 | accepted (build and verify) | `6.12` |
| android17-6.18 | `fb8b66200bf4` | r584948c | 5 | accepted (build) | `6.18` |

`verify` used the same image, `--branch`, `--generation`, `--arch`,
`--kmi-src` and `--kmi-out`, plus
`--module out/part-projection-<line>-final/part-projection.ko`; it printed
`"status": "accepted"` for 5.10, 6.1 and 6.12.

Two 5.10 build inputs are explicit. First, the pinned image packages no
`/opt/ddk/src/android12-5.10/build.config.constants`, and the admission CLI
requires exactly one declared `CLANG_VERSION`. The run bind-mounted a one-line
file with `CLANG_VERSION=r416183b`, the revision the image's own
`build.config.common` names in `CLANG_PREBUILT_BIN`, and the compiler guard then
compared it with `Android (7284624, based on r416183b) clang version 12.0.5`.
Second, 5.10's CFI kallsyms post-link step writes `part-projection.lds` in the
module directory and `make clean` does not remove it, so `Kbuild` lists
`clean-files += part-projection.lds`; the build's source-evidence check fails
otherwise.

Observed artifact facts (`llvm-readelf -p .modinfo`, `llvm-nm -u`):

- `5.10`: `part_projection_bdev_abi=5.10`, vermagic
  `5.10.252-dirty SMP preempt mod_unload modversions aarch64`, 61 undefined
  symbols, no versioned records.
- `5.15`, `6.1`, `6.6`, `6.12`, `6.18`: 58, 57, 57, 60 and 60 undefined
  symbols, each with the matching `part_projection_bdev_abi` value and no
  versioned records.

For 5.10, each of the 61 undefined names appears in both
`/opt/ddk/kdir/android12-5.10/Module.symvers` and
`/opt/ddk/kdir/android12-5.10/System.map`; the artifact imports neither
`bdget_part`, `get_gendisk` nor `dm_open_count`. No import of this artifact
depends on assisted loading: every symbol is a real export of the target KMI.

These checks establish compile, modpost, source-evidence and import admission
only. They do not establish load, runtime or device behavior.


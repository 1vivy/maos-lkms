# Upstream efivarfs frontend provenance

The module builds one pinned ACK frontend per kernel generation. Kbuild selects
the frontend from `$(VERSION).$(PATCHLEVEL)` of the target kernel source. The
6.12 import is the module root. The 6.1 and 6.18 imports are separate pins under
`ack/`.

The kernel version names the VFS, inode, file-attribute and EFI interfaces. The
KMI generation names the published ABI. Kbuild therefore selects on the kernel
version and never on the KMI generation.

Each generation changed these interfaces in different places. A translation
layer would have to reproduce the 6.1 superblock, statfs, mount-option and
notifier code and the 6.18 file-attribute and inode code. That copy would carry
the same interfaces as the pinned source and add a second implementation. The
module keeps the ACK source instead.

## Pinned frontends

| Kernel | ACK branch | Source identity | Local path |
| --- | --- | --- | --- |
| 6.12 | `android16-6.12` | KMI generation 6, commit `925a103d123c30a84577f29e1573376aacbde94b`, `https://android.googlesource.com/kernel/common` | module root |
| 6.1 | `android14-6.1` | image `ghcr.io/ylarod/ddk-min@sha256:1dd6ac340b627a90a4031d6d0df6b129d8cc949b139fb56032c898f023d3d5d3`, kernel 6.1.166 | `ack/android14-6.1/` |
| 6.18 | `android17-6.18` | image `ghcr.io/ylarod/ddk-min@sha256:fb8b66200bf402cf65a751060fc1aa29524b9fa8840feef16c7b196a4f3f0e6e`, kernel 6.18.32 | `ack/android17-6.18/` |

The 6.1 and 6.18 pins are unmodified copies of the five files this module
compiles: `super.c`, `inode.c`, `file.c`, `vars.c` and `internal.h`, taken from
`<image>:/opt/ddk/src/<branch>/fs/efivarfs/`. These images carry no Git
metadata. The image digest and the kernel version are the recorded source
identity. The upstream `Kconfig` and `Makefile` of those directories are not
imported, because this module's own `Kbuild` replaces them.

The 6.18 `super.c` also includes `../internal.h` from the kernel's `fs/`
directory. That private header declares `find_next_child`, which the thaw
callback uses to traverse variable dentries. Kbuild sets
`CFLAGS_ack/android17-6.18/super.o` to `-I$(srctree)/fs/efivarfs`, so only that
object gains the base directory. The unchanged relative include then resolves
to the matching target kernel's `fs/internal.h`. This keeps the upstream
declaration and the pinned include. It adds no copied header and no replacement
prototype. The 6.1 and 6.12 compile flags are unchanged.

The 6.12 files remain pristine ACK `android16-6.12`, KMI generation 6, commit
`925a103d123c30a84577f29e1573376aacbde94b`, from
`https://android.googlesource.com/kernel/common` (`fs/efivarfs/`). Original SPDX
notices, authorship and `MODULE_IMPORT_NS` are retained in every pin.

| Upstream path (6.12 pin) | SHA-256 |
| --- | --- |
| fs/efivarfs/super.c | 671773f9b0cd9b5ee05bfd7a55608039d67075decc998327cf22078fe38424d0 |
| fs/efivarfs/inode.c | 7ba69dd1ad51af11525a89977e1748855861e9153782f95d2b8926600f190159 |
| fs/efivarfs/file.c | 5fbdf4d179358134c999480f7522b227813c22cef3b822781e4238d3922b7b96 |
| fs/efivarfs/vars.c | 50bf38c3267bc7da8961780acba7ca7516d605d18b4f7a89b253dc007f1baf1f |
| fs/efivarfs/internal.h | ff7818298d360324f9e104f903a1b3073047049dea3a23f89f0c95d3907e38d6 |

| Imported path | SHA-256 |
| --- | --- |
| ack/android14-6.1/super.c | 7dc2e0c4b062d621bd3cda9e3838b7e123c446e31cbcfed19fd823fedc9f1f92 |
| ack/android14-6.1/inode.c | 5b63e2f192f57a720bf2ef07aab5ef34b364358fa83e2291438470b5fe2b803f |
| ack/android14-6.1/file.c | 117deedda21bbb5d7876aab591d4966d79fd593fc2afeb41776b1e8e8b024644 |
| ack/android14-6.1/vars.c | 963078576c87621fbd172912a571d22ad467f55f386175c4f78fce98385d4ab5 |
| ack/android14-6.1/internal.h | 167cad484da4a51017f1e7cb22f009694d4d21531962a6b7023466418d517054 |
| ack/android17-6.18/super.c | 9ff6869ca6c74248b1e7695fd1e6e6794a1494635e8ddea20ad26ebd660ee7ed |
| ack/android17-6.18/inode.c | a34c93e732d2134b056120b173f75f0e0987a3cf81a5005d12ccf2961579dc14 |
| ack/android17-6.18/file.c | 0b043a061086790dba2bcef05c156cf5c56119ae25e4e2bf9665f674a55e10a1 |
| ack/android17-6.18/vars.c | af1ef1bad1f62344cdddd542cd013e4d141450e6602464e09e9c77d2042f5afd |
| ack/android17-6.18/internal.h | f8d8fd090e9068ba82f7ba24e31018dc82a7868948a05b34814f71a7728358a4 |

## Named patches

Kbuild applies two named patches to the selected pristine `vars.c`. Both are
plain unified diffs with no generator and no hidden source.

1. `patches/0001-maos-project-guid.patch` adds the maos project GUID to the
   removable-variable allowlist. It applies to every generation.
2. `patches/0002-efivarfs-return-get-status.patch` applies the upstream error
   propagation fix. It applies only to the 6.12 pin.

Kbuild writes `vars-guid.c` after the first patch and `vars-patched.c` after the
second patch, beside the selected `vars.c`. The 6.1 and 6.18 pins already
contain the second fix, so there `vars-patched.c` is an unmodified copy of
`vars-guid.c`. Both generated files are build products. They are not tracked,
and `make clean` removes them.

### Project GUID

The first patch adds this entry after `LINUX_EFI_CRASH_GUID` and before the
`NULL_GUID` sentinel:

`EFI_GUID(0x7a5e4b1c, 0x0d3f, 0x4e62, 0x9b, 0x8a, 0x1c, 0x2d, 0x3e, 0x4f, 0x5a, 0x6b)`

All three pins carry the same allowlist table at the same position, so this
patch applies to each `vars.c` with `--fuzz=0`.

The patch keeps one GUID policy for every generation:

- A variable in the maos project GUID is removable. Its inode has no
  `S_IMMUTABLE` flag, so `create` and `unlink` can change it.
- `LINUX_EFI_RANDOM_SEED_TABLE_GUID` stays refused for create and is skipped
  during enumeration.
- Every other variable keeps the ACK immutability rule.

### Audited 6.12 error-propagation fix

The 6.12 pin returns `0` from `efivar_entry_get` and discards the converted EFI
status of `__efivar_entry_get`. `efivarfs_file_read` then treats a failed
`GetVariable` as success and copies an unfilled `kmalloc` buffer to userspace.
The pin therefore has a real defect, not a difference in style.

The independent source for the fix is upstream commit
`4b22ec1685ce1fc0d862dcda3225d852fb107995`, "efivarfs: fix error propagation in
efivar_entry_get()". A stable backport record lists it as a mainline v6.19-rc8
inclusion, names Kohei Enju as author and Ard Biesheuvel as sign-off, records
`Fixes: 2d82e6227ea1 ("efi: vars: Move efivar caching layer into efivarfs")`,
and assigns CVE-2026-23156. The change is one line, `return 0` to `return err`.
The commit URL is
`https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=4b22ec1685ce1fc0d862dcda3225d852fb107995`.

`patches/0002-efivarfs-return-get-status.patch` carries that change with the
same context. Kbuild applies it to the generated `vars-guid.c` of the 6.12 pin
only. The pinned `vars.c` keeps its recorded bytes and hash. The 6.1 and 6.18
pins already return the converted status, so this patch does not apply to them
and their bytes are unchanged.

The applied state also matches the DDK `android16-6.12` source (6.12.76), whose
`fs/efivarfs/vars.c` has SHA-256
`a244be80a03cf432942c65f024fe7700f7157d5651f08d783fcad25bff82fe1f`.

After the fix, a failed `GetVariable` returns an error to
`efivarfs_file_read`, which frees the buffer and returns that error. It does not
copy the unfilled buffer.

## Generation differences

| Kernel | Frontend difference |
| --- | --- |
| 6.1 | `create` and `fileattr_set` take `struct user_namespace`. There are no mount options, so `uid` and `gid` cannot be set. Statfs is `simple_statfs`. One global `efivarfs_list` serves the mount, and the mount keeps no private state. There is no firmware read-only notifier. `efivarfs_init` registers only when `efivars_kobject()` is non-NULL. Inode times use `current_time`. |
| 6.12 | `create` and `fileattr_set` take `struct mnt_idmap`. Mount options accept `uid` and `gid` with `fsparam_uid` and `fsparam_gid`. Statfs uses `efivar_query_variable_info` and `efivar_reserved_space`. A notifier follows firmware read-only state. Per-superblock state holds the entry list. |
| 6.18 | File attributes use `struct file_kattr`. The superblock has no `.drop_inode` and no `s_d_op`. `MODULE_IMPORT_NS` takes a string. File operations track `open_count` and `removed`, and `release` removes the dentry with `simple_recursive_removal`. |

## Build

Build with the existing command:

`make -C kernel/efivarfs KMI_SRC=... KMI_OUT=... JOBS=4 KMI_BRANCH=android16-6.12 KMI_GENERATION=6 KMI_ARCH=aarch64`

Standalone Kbuild accepts configured ACK/GKI/DDK outputs for arm64 and x86_64.
`KMI_BRANCH` and `KMI_GENERATION` identify the kernel output for admission. They
do not select the frontend. Kbuild reads `$(VERSION).$(PATCHLEVEL)` from the
target kernel source. A kernel other than 6.1, 6.12 or 6.18 stops with an
explicit error. Add a pinned ACK source for a new generation. Do not reuse
another generation. Object and generated-file paths include the generation
directory, so two generations do not share an object path.

The shared admission checks the built module against the exact configured kernel
output and writes `<module>.ko.build.json` beside it as release information only.
Private imports require a relocating loader if not exported.
`metadata.c` only adds descriptive common `.modinfo` fields, not another init
entrypoint or fake ready flag. Successful mount/read is frontend readiness.

The product build driver stages the module directory under its output root
before Kbuild. That staged copy includes `ack/`, so each generation's pinned
sources travel with the module. Direct `scripts/kmi_modules.py` builds use the
module directory itself.

Load this frontend then independent `efivar_store.ko` using `partuuid=<unique
partition GUID>` or `dev=major:minor` (mutually exclusive), or its DT selector.
Mount filesystem type **`efivarfs`** at **`/sys/firmware/efi/efivars`**.
Directory presence alone is not a successful mount. Native EFI ownership and
mountpoint cleanup belong to the independent backend, never the pristine
frontend. See `../efivar_store/PROVENANCE.md` for the pending exact-source pin.

## Checks and limits

Source checks:

- `patch --dry-run --fuzz=0` applied `0001-maos-project-guid.patch` to the 6.1,
  6.12 and 6.18 `vars.c` without a reject or an offset warning.
- `patch --fuzz=0` applied `0002-efivarfs-return-get-status.patch` to the 6.12
  file after the first patch and produced `return err`. The hunk position
  refers to that generated file.
- The resulting 6.12 `vars-patched.c` differs from the DDK `android16-6.12`
  (6.12.76) `fs/efivarfs/vars.c` only by the project GUID line.
- The second patch is rejected by the 6.1 and 6.18 file after the first patch.
  Those pins already return the converted status, and their bytes stay
  unchanged.
- Each target `Module.symvers` exports the EFI helpers the frontend imports:
  `efivar_lock`, `efivar_unlock`, `efivar_get_variable`,
  `efivar_get_next_variable`, `efivar_set_variable_locked` and
  `efivar_supports_writes`. The EFIVAR namespace is present where used.
  `efivar_reserved_space` is a header inline on non-x86 targets.
- The 6.1, 6.12 and 6.18 kernel `Makefile` files export `VERSION` and
  `PATCHLEVEL` to the module build.
- `ack/android17-6.18/super.c` is the only pinned file with a quoted include
  that starts with `../`. The other pins and the generated `vars-patched.c` use
  only `"internal.h"`, which resolves beside the file.
- For the 6.18 `super.o`, no `internal.h` exists in any earlier search
  location. The checked parents are `ack/`, `$(src)/../..`, and the parents of
  every `LINUXINCLUDE` directory under both trees: `src/`, `include/`,
  `arch/arm64/`, `arch/arm64/include/`, `arch/arm64/include/generated/`,
  `include/generated/` and `include/uapi` relatives. The target
  `fs/internal.h` exists and declares `find_next_child`.
- Kbuild appends `CFLAGS_<target-stem>.o` after `ccflags-y`, so the new
  directory is searched last and cannot shadow the module's own `internal.h`.
- The 6.18 `super.c` bytes are unchanged
  (`9ff6869ca6c74248b1e7695fd1e6e6794a1494635e8ddea20ad26ebd660ee7ed`).

Limits:

- The three pinned arm64 DDK builds compile and pass the assisted-loader
  admission check. This includes the 6.18 `fs/internal.h` include path.
- The DDK configs do not enable `CONFIG_EFIVAR_FS`; standalone module builds
  compile the pinned frontend sources.
- No module was loaded. Runtime behavior on a phone is unverified.
- On x86_64 the 6.12 and 6.18 frontends import `efivar_reserved_space` as an
  external symbol. This record does not verify that export. The 6.12 pin has
  the same import.
- The 6.12 pin keeps its recorded bytes. The generated `vars-patched.c`
  applies both the project GUID change and the error-propagation fix.

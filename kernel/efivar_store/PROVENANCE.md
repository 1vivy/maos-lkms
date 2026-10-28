# EFVS backend provenance and build

Source: https://github.com/1vivy/efivar-store.
`SOURCE_REVISION` records the exact commit.
The build materializes that revision in the ignored `.source` directory.
It requires the checked-out HEAD to equal the pin and rejects tracked changes
before Kbuild compiles the module.
The build checks the module against the configured kernel output.

The pinned revision is `dfcc94b7c418e825a0904c2bb4f9a91193effa64`. ODP uses the same revision for its firmware store. The source uses Rust edition 2024 and Rust 1.88. Its `EFVS_ROOT` and `EFVS_OUTPUT_DIR` settings let this repository include the pinned upstream Kbuild rules.

`EFIVAR_STORE_REPO` may select a local clone, but the build requires the recorded revision. See the ODP [EFVS contract](https://github.com/1vivy/odp-platform-qcom/blob/main/docs/src/capabilities/efvs.md) for the shared format.


```sh
export PATH="$HOME/.cargo/bin:$PATH"
export KMI_SRC=/path/to/android16-6.12/source
export KMI_OUT=/path/to/matching/gki-out
# Optional local clone; the build requires SOURCE_REVISION.
export EFIVAR_STORE_REPO=/path/to/efivar-store
python3 scripts/kmi_modules.py build \
  --module-dir kernel/efivar_store --module efivar_store \
  --branch android16-6.12 --generation 6 --arch aarch64 \
  --kmi-src "$KMI_SRC" --kmi-out "$KMI_OUT" \
  --output-dir out/modules/android16-6.12-6/aarch64/efivar_store
python3 scripts/kmi_modules.py verify --kmi-out "$KMI_OUT" \
  --branch android16-6.12 --generation 6 --arch aarch64 \
  --module out/modules/android16-6.12-6/aarch64/efivar_store/efivar_store.ko
```

## Design

The C Kbuild module (`linux/efivar_store.c`) links the allocation-free Rust
EFVS engine as a freestanding `no_std` object through a small C ABI. It imports
no Rust-mangled symbols and does not require `CONFIG_RUST` or kernel Rust crates.
The Rust object uses pinned `nightly-2026-08-08` with
`-Z build-std=core,compiler_builtins`. It targets aarch64 softfloat or the
generated x86 kernel target. C compilation and native linking use the pinned
DDK clang from `scripts/bootstrap-ddk-clang.sh` or `DDK_CLANG_DIR`.

Private imports require an ELF relocating loader or real kernel exports.
Load `efivarfs`, then `efivar_store` with an explicit selector. Mount `efivarfs`
at `/sys/firmware/efi/efivars` and verify a read. `PolicyNone` refuses
authenticated enrollment. Firmware owns blank-store initialization and
compaction. The pinned source provides the VM harness and symbol inventory in
`docs/linux.md`.

### Credentials

Every `kernel_read`, `kernel_write`, `vfs_fsync`, and final `fput` uses
`override_creds(store_file->f_cred)` / `revert_creds`. The opener's file credential
is the sole I/O credential: no helper provider, `symbol_get`/`symbol_put`, private
credential symbol or fallback to a HAL's current credentials. Load during rdinit
before policy; module rules must permit the opener domain's access to the store
block device. UID 0 alone is not a SELinux authorization.

Native EFI objects are referenced, not removed. Only the module-created mountpoint
and EFI object are released on failure/unload. `ready` means validated store plus
registered callbacks, not merely directory existence. Native EFI discovery uses
exported sysfs/kobject operations, not the private `efi_kobj` global. UUID discovery
requires mounted `/sys`, scans canonical block uevents for exactly one PARTUUID,
validates MAJOR/MINOR and rechecks the opened partition's UUID. Missing, ambiguous,
malformed or unreadable candidates fail closed. No `block_class` global, udev
symlink, root helper or relocating DKMS loader is required. Explicit `dev=` remains
supported without UUID enumeration; the standalone Makefile leaves undefined
modpost imports fatal.
The standalone source Kbuild selects arm64 softfloat or x86_64 Rust targets and
supports configured ACK/GKI/DDK and conventional DKMS packaging; all retain the
same engine and opener-credential C glue. The product Kbuild in this directory
sets `EFVS_ROOT` and includes that file. It copies no rule and no C source.

The x86 engine target derives code generation from the kernel configuration.
The pinned source generates a softfloat target with configured mitigation and
CFI features. Kbuild adds the target's configured hardening flags. The build
does not require `CONFIG_RUST` or disable kernel mitigations.

Every emitted helper must resolve to a kernel implementation through
ELF/import admission. The build provides no panic substitutes, no-op
definitions, sanitizer ABI overrides, or unresolved-symbol exemptions.
Custom targets retain `-Zjson-target-spec`. The x86 target uses direct PLT32
calls. Admission rejects unsupported allocated-section relocations.

The builder records compiler output and refuses admission when objtool reports
diagnostics, even if make exits successfully. Private imports must appear in
the target `System.map` and require `CONFIG_KALLSYMS_ALL=y` for the configured
loader's kallsyms resolver. A present `module_layout` version record must match
its published KMI CRC. Other import CRCs are not compared. The host test and
build commands are in the repository README.

Build and VM checks do not establish enforcing Android credential acceptance
or physical-device behavior. Do not treat them as permission to load a module
on a phone or block device.

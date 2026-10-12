# EFVS backend provenance and build

Source: https://github.com/1vivy/efivar-store; the exact commit is recorded in
`SOURCE_REVISION`. Source is materialized only at that revision in ignored
`.source`, checked for tracked changes, built with standalone Kbuild, and admitted
with a schema-2 artifact/KMI receipt.

The reconciled source is pinned to
`3cdd1d84f80046c68261ee51fd8e11bb02b58dcc` (`linux: claim the backing device for
the backend lifetime`), retaining the credential, DKMS and x86 call-relocation
cutovers. It holds an exclusive block claim until callback removal and final
`fput`, so live EFI storage is not treated as an unowned raw partition.
It removes the provider ABI and includes the configured freestanding runtime,
sysfs UUID discovery and native EFI ownership.
The commit currently exists in the isolated source clone; publication is a
separate owner-controlled operation. `EFIVAR_STORE_REPO` may supply that local
clone for integration, but never changes the recorded revision.

```sh
export PATH="$HOME/.cargo/bin:$PATH"
export KMI_SRC=/path/to/android16-6.12/source
export KMI_OUT=/path/to/matching/gki-out
# Local integration before publication of the pin:
export EFIVAR_STORE_REPO=/path/to/efivar-store
make -C kernel/efivar_store JOBS=4 KMI_BRANCH=android16-6.12 KMI_GENERATION=6 KMI_ARCH=aarch64
python3 scripts/kmi_modules.py verify --kmi-out "$KMI_OUT" \
  --branch android16-6.12 --generation 6 --arch aarch64 \
  --module kernel/efivar_store/efivar_store.ko
```

## Design

The module is a C kbuild module (`linux/efivar_store.c`) that links the audited
allocation-free Rust EFVS engine as a freestanding `no_std` object through a small C
ABI. It imports no Rust-mangled symbol and needs neither `CONFIG_RUST` nor the kernel's
Rust crates. This is deliberate: the first backend, written against the kernel `rust`
crates, was refused on the phone because the running GKI exports different `core`/`kernel`
crate hashes and no `core::fmt::Formatter` methods (`20261008T055846Z-phone-efvs-lkm-test`).
The Rust object is built offline with `nightly-2026-08-08`, `-Z build-std=core,compiler_builtins`
for `aarch64-unknown-none-softfloat` and `panic=immediate-abort`; x86 uses the
generated softfloat kernel target. C compilation and native-object linking use
the same `LLVM=1` toolchain selected on PATH as the other ACK modules. Rust emits
no LLVM bitcode, so the former mixed-version bitcode-linking workaround is gone.

Where private imports are not kernel exports, use an ELF relocating loader;
otherwise normal finit_module is sufficient. There is no core/root-runtime
dependency. Load efivarfs, then efivar_store with an explicit selector, then mount
filesystem type `efivarfs` at `/sys/firmware/efi/efivars` and verify a read.
PolicyNone refuses authenticated enrollment; firmware alone formats blank storage and
compacts. The VM harness and symbol inventory are in the pinned source's `docs/linux.md`.

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
same engine and opener-credential C glue.

Both source and product Kbuilds derive x86 engine codegen from the actual kernel
configuration. The pinned source's `linux/rust-target.py` generates a softfloat
target with configured external retpoline/indirect-branch features and SLS
hardening; Kbuild adds external return thunks, IBT/no jump tables, call padding,
frame pointers and enabled CFI normalization. No CONFIG_RUST dependency or
global mitigation disablement is introduced. The source pin includes the target
generator, `linux/rustc-wrapper.py`, `linux/compiler-builtins.rs`, and credential
changes. The freestanding build remains separate from host
and firmware release profiles. The wrapper replaces only the designated
compiler-runtime crate's source operand, retaining all target codegen flags and
compatible configured sanitizer instrumentation/metadata. The descriptor has
zero function definitions: emitted helpers must resolve to genuine kernel
implementations through normal ELF/import/CRC admission. Unavailable helpers
fail closed, without panic substitutes, no-op definitions, sanitizer ABI
overrides or unresolved-symbol exemptions. Historic accepted ARM runtime
definitions were limited to `bcmp`, `memcmp`, `memcpy`, `memmove`, `memset`;
the configured x86 kernel exports all five with genuine CRCs. Each newly built
module still requires actual compile/objtool/import admission. Custom targets
retain `-Zjson-target-spec`.
The x86 target explicitly enables direct PLT32 calls (`plt-by-default=true`);
the bare-metal no-PLT default emitted GOTPCREL memory-helper calls that ACK
cannot load. Admission now rejects unsupported allocated-section relocations,
not only unresolved imports and CRC mismatches.

The general builder streams complete compiler output to `<module>.build.log`
and refuses admission for objtool diagnostics even when make returns zero.
Private-import modpost warnings are not suppressed; their System.map/CRC checks
remain mandatory. The source passed native Clang 7.2.8 and GCC 6.18.52 header
builds with fatal modpost and no objtool diagnostics; ACK generation-6 builds
passed on ARM and x86. ARM and corrected x86 backends passed VM PARTUUID success,
missing/duplicate refusal, write/update/delete, reboot, compaction, torn-tail and
blank-refusal checks through the production loader, including rejected-disk and
partition-boundary byte comparisons. Enforcing Android credential acceptance is
not established by those policy-free VMs.
The actual DKMS 3.4.3 wrapper also built and signed the GCC 6.18.52 module in
isolated unprivileged source/state/output trees. Quoting the leading `make`
prevents DKMS from incorrectly injecting KERNELRELEASE into the outer wrapper.
No system installation, key enrollment or host module loading was performed.

## Historical device evidence (before this source pin)

Loaded by hand on the real phone kernel in passthrough recovery, then exercised through
efivarfs: firmware-written `Slot-rom1`/`MergeStatus-rom1`/`BootedRom` read back
byte-identical, a probe variable was set, updated and deleted with the physical store
parsing cleanly after each step, and the next firmware boot replayed and compacted the
Linux-written records (`20261008T063318Z-phone-efvs-lkm-test`,
`20261008T063449Z-phone-efvs-efivarfs-test`, `20261008T063532Z-phone-efvs-store-read`).

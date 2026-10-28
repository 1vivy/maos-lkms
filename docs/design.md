# Design rationale

## Independent modules

The repository builds each kernel module as a separate artifact. This keeps module source, licensing, and KMI admission explicit. A module does not include product PID 1 orchestration or a root runtime.

The shared header carries descriptive name, version, ABI, criticality, and readiness metadata. The loader and consumer own authorization and lifecycle decisions. Module metadata is not an authorization mechanism.

## KMI admission

The admission tool checks each undefined import against the target KMI exports or its `System.map`. A private import requires `CONFIG_KALLSYMS_ALL=y` because the configured loader resolves private symbols through kallsyms and prebinds them before `init_module`.

The kernel checks `module_layout` independently. Admission therefore checks a present `module_layout` CRC against the published target KMI value. It does not require CRC equality for other imports. This admission contract does not claim that a module loads or behaves correctly on a device.

## Part projection

The projection module uses upstream device-mapper for data BIO handling, queue stacking, and crypto. It publishes per-disk GPT metadata through configfs and uses shared endpoint protection. It does not implement a standalone gendisk or physical GPT writer. Its `sealed` state describes owned read-only changes, not a cryptographic boundary.

## EFI variable storage

The EFI store uses a small C ABI between its kernel module and pinned freestanding Rust engine. It does not link against Rust symbols from the running kernel. The engine therefore does not require `CONFIG_RUST` or the kernel Rust crates.

The backend uses the backing file's opener credentials for I/O. It preserves native EFI objects and refuses blank storage without writing. Firmware owns initialization and compaction.

## Source of current contracts

See [architecture](architecture.md), [build and admission](build.md), and [runtime contracts](runtime.md). Module-specific source pins and upstream notices remain in each module's provenance file.

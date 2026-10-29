# Design rationale

## Independent modules

The repository builds each kernel module as a separate artifact. This keeps module source, licensing, and KMI admission explicit. A module does not include product PID 1 orchestration or a root runtime.

The shared header carries descriptive name, version, ABI, criticality, and readiness metadata. The loader and consumer own authorization and lifecycle decisions. Module metadata is not an authorization mechanism.

## KMI admission

The admission tool checks each undefined import against the target KMI exports or its `System.map`. A private import requires `CONFIG_KALLSYMS_ALL=y` because the configured loader resolves private symbols through kallsyms and prebinds them before `init_module`.

The kernel checks `module_layout` independently. Admission therefore checks a present `module_layout` CRC against the published target KMI value. It does not require CRC equality for other imports. This admission contract does not claim that a module loads or behaves correctly on a device.

## Part projection

The projection module uses upstream device-mapper for data BIO handling, queue stacking, and crypto. It publishes per-disk GPT metadata through configfs and uses shared endpoint protection. It does not implement a standalone gendisk or physical GPT writer. Its `sealed` state describes owned read-only changes, not a cryptographic boundary.

## Kernel-line ports

Each module keeps the interfaces of one kernel line apart from the interfaces of another line. A line port states its own interfaces and quirks. Shared logic stays in one place, and a build for an unported line fails instead of reusing another line's code.

`part-projection` selects its block-device port from the kernel version at compile time. `dm-thin-pool` applies a port programme to that line's own device-mapper sources, because its differences are source edits and not one include boundary. Both arrangements keep one copy of the shared behavior per module.

## Source of current contracts

See [architecture](architecture.md), [build and admission](build.md), and [runtime contracts](runtime.md). Module-specific source pins and upstream notices remain in each module's provenance file.

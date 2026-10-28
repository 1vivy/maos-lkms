# Runtime contracts

The contracts below describe module interfaces. They do not replace consumer-owned startup, policy, or device qualification.

## Part projection

`/config/part-projection` exposes root `abi`, `state`, `commit`, and `reset`.
It also exposes shared `endpoints/NAME/{dev,hide,writable}` attributes.
Each disk has `disks/NAME/{dev,anchor,metadata}` attributes.

ABI 6 preserves 512, 1024, 2048, and 4096-byte geometry per disk. Device-mapper
units remain 512-byte sectors. `pp-meta NAME OFFSET` freezes target-owned GPT
snapshots.

The shared commit pins participants and validates every disk and anchor. It
owns physical hiding and sealing. It enables partition scanning only after all
anchor moves succeed. A partial move failure retains ownership until userspace
removes every mapping normally.

Reset refuses while any publication is live, registered, or open. It refuses
even if userspace already removed another disk. Userspace must reread every GPT.
See the [part-projection ABI](../kernel/part-projection/README.md).

## EFI variables

Mount filesystem type `efivarfs` at `/sys/firmware/efi/efivars`. A successful
mount and read establish frontend readiness. Directory presence alone does not.

The backend accepts one selector: `partuuid=<unique-GPT-UUID>`,
`dev=<major>:<minor>`, or `/chosen/efivar-store,partuuid`. Do not substitute a
label or fixed unique GUID. Linux refuses blank stores without writing.
Firmware owns store initialization and compaction.

## Backing-file credentials

Backing-file reads, writes, fsync, and final `fput` use the retained opener
credentials through `override_creds` and `revert_creds`. Load before Android
policy. Permit the opener domain to access the backing block device. UID 0 alone
does not grant SELinux access.

The backend uses no ESP credential or provider ABI. It removes only EFI sysfs
objects that it created. It does not remove native EFI objects.



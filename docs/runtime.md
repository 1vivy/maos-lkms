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

The module reports the kernel-line port it was compiled with as the
`part_projection_bdev_abi` `.modinfo` entry (`5.10`, `5.15`, `6.1`, `6.6`, `6.12`, or
`6.18`). A consumer can read it with `modinfo`. It describes the build, not the
running kernel.

## dm-thin-pool

`dm-thin-pool` registers the `thin-pool` and `thin` device-mapper targets under
its private symbol names. Consumers create these targets through normal
device-mapper tables.

The module exposes two read-only parameters under the kernel's standard module
parameter path. `ready` reads `Y` only after every subsystem and both
device-mapper targets initialize. It reads `N` before the first initialization
step and as soon as unload teardown starts. The maos PID 1 self-check uses this
value. `private_names` defaults to `N`. With `private_names=1` at load, the
targets register as `thin-private` and `thin-pool-private` instead of the
upstream names. See the [dm-thin-pool interface](../kernel/dm-thin-pool/README.md)
for target parameters and the metadata layout.


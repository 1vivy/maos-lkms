# Independent part-projection (configfs ABI 6)

GPL-2.0-only. Artifact `part-projection.ko`, internal module name
`part_projection`. Requires upstream device-mapper and configfs, not the Egysk
helper or an EFI module. It registers `pp-range`, `pp-meta`, and `pp-hole`.

DM owns the disk, data BIO splitting and completion, queue intersection, and crypto. There is no standalone projection gendisk or data-copy/crypto-profile engine. Each virtual disk has its own GPT, queue geometry, and crypto-capability intersection. File-backed image views must not share the disk that carries hardware-wrapped userdata. Endpoint pinning, physical-name hiding, and sealing remain shared. No target invents capabilities that its backings lack.


## Configfs and geometry

Mount configfs independently. `/config/part-projection` exposes read-only `abi`
(`6`), `state` (`idle`, `active`, `sealed`, `failed`), and shared `commit`/`reset`.
`endpoints/NAME/{dev,hide,writable}` stages pinned participants, including every
possible reload backing. Create `disks/NAME` for each DM mapping; its `dev`,
`anchor` and `metadata` belong to that disk. Unset dev/anchor read `none`.
An anchor selects physical ancestry only, never endpoint access rights.

Each disk's metadata accepts bounded text writes, one complete record per write:

```text
GENERATION_HEX32 LOGICAL_BLOCK_BYTES CHUNK_INDEX HEX1024\n
```

A chunk is always 512 bytes, and indexes start at zero and advance sequentially.
Logical block bytes must be 512, 1024, 2048 or 4096, constant with the generation
throughout the upload. Mixed, malformed, incomplete or out-of-order uploads
cannot commit; invalid writes discard that disk's staging progress. After such
an error, restart at index zero. Total chunks are respectively 67, 70, 76 or 88:
primary `(2 + ceil(16384/LBS)) * (LBS/512)` followed by backup
`(1 + ceil(16384/LBS)) * (LBS/512)`.

DM table starts, lengths and backing offsets always use 512-byte sectors.
`pp-range BACKING OFFSET ro|rw` remaps through upstream DM.
`pp-meta DISK_NAME CHUNK_OFFSET` copies its target segment from that disk's complete
staging. The first snapshot freezes that source's generation and geometry until
reset. Metadata target boundaries are logical-block aligned; io_hints preserve
the staged geometry. `pp-hole` has no parameters: ordinary reads return zeroes,
including GPT cache-page padding, while data writes and crypto-context reads
are rejected. Empty flushes complete locally. Inactive image switches remain
separate `error` targets, not zero-filled gaps.

DM flush fan-out reaches these targets as empty `REQ_OP_WRITE | REQ_PREFLUSH`
bios, not request-level `REQ_OP_FLUSH`. Metadata and holes complete only those
empty flushes locally; ranges forward them to their real backing and preserve
its completion status. A data-bearing write, including one carrying PREFLUSH,
must still be rejected by metadata, holes and read-only ranges.

## Publication, reload and teardown

`commit` accepts `1` or `seal`. It validates every mapped disk's geometry,
scan suppression and initial ancestry, rejects duplicate publication dev_t
identities, and pins all disk config items, endpoints and containing disks.
It retains physical PARTNAME/read-only rollback records, optionally seals shared
participants, adopts each optional anchor parent and hides selected names.
Partition scanning is enabled only after all anchor moves succeed. Each
composite is a sibling of its anchor disk, not nested beneath it. Android needs
recognized boot-device ancestry for global `by-name` links; the phone adapter
selects the physical ESP device on that controller. An anchor with no physical
parent, the composite itself, or a descendant is refused.

Multiple `device_move` calls are not atomic. A move error retains all ownership
in `failed` state; it does not restore shared protection beneath partially moved
live disks. Transient DM holders protect moves against concurrent unregistration
and are released before return so ordinary removal can proceed. Reset never
moves a deleted device. Userspace must reread and verify every GPT; stock
ueventd sanitizes slash names. No physical GPT is rewritten.
`sealed` describes owned read-only changes, not a cryptographic security boundary.

Reload uses upstream DM inactive tables and suspend/resume with unchanged layout
and predeclared participants, never remove/recreate. On publication failure,
remove every mapping normally before reset. A busy disk prevents shared cleanup
even after another disk was removed; no force or deferred removal is used.
`reset=1` refuses until every owned disk is dead, unregistered and has no openers.
It then restores only owned PARTNAME/read-only/flags changes and releases pins.
Disk/endpoint mutation is refused in active, sealed and failed states.
There is no privileged unseal shortcut.

## Build and evidence

`bdev.h` selects a block-device port per kernel line under `abi/`: `abi/5.15`
and `abi/6.1` use the legacy `block_device` open, `abi/6.6` uses
`bdev_open_by_dev`/`bdev_release`, and `abi/6.12` and `abi/6.18` select the
shared file-based port in `abi/file-bdev.h`. A build against an unported line
stops with an error. The selected line appears as the
`part_projection_bdev_abi` `.modinfo` entry (`5.15`, `6.1`, `6.6`, `6.12` or
`6.18`).

The root exact-KMI admission checks imports against the target `System.map` and KMI export list. Private imports require a compatible loader that prebinds them or real kernel exports. A present `module_layout` version record must match the published KMI CRC. Other `Module.symvers` CRCs are not compared. See the root README for admission and build commands.

Build and admission checks do not qualify phone behavior. They do not establish multi-disk busy teardown, reload, reset, enforcing policy, or physical-device safety. No physical GPT write is part of this module's contract.


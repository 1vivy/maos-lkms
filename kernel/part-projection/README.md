# Independent part-projection (configfs ABI 5)

GPL-2.0-only. Artifact `part-projection.ko`, internal module name
`part_projection`. Requires upstream device-mapper and configfs, not the Egysk
helper or an EFI module. It registers `pp-range`, `pp-meta`, `pp-hole`; upstream
DM owns the disk, data BIO splitting/completion, queue intersection and crypto.
There is no standalone projection gendisk or data-copy/crypto-profile engine.

## Configfs and geometry

Mount configfs independently. `/config/part-projection` exposes read-only `abi`
(`5`) and `state` (`idle`, `active`, `sealed`); `dev` is the composite DM device
major:minor. `endpoints/NAME/{dev,hide,writable}` stages each pinned participant.
The owner must prepare all endpoints, including every possible reload backing.
`anchor` is a physical disk/partition major:minor, or `none` for ordinary virtual
DM publication. It selects namespace ancestry only, never endpoint access rights.
`metadata` accepts bounded text writes, one complete record per write:

```text
GENERATION_HEX32 LOGICAL_BLOCK_BYTES CHUNK_INDEX HEX1024\n
```

A chunk is always 512 bytes, and indexes start at zero and advance sequentially.
Logical block bytes must be 512, 1024, 2048 or 4096, constant with the generation
throughout the upload. Mixed, malformed, incomplete or out-of-order uploads
cannot commit; invalid writes discard staging progress. After such an error,
restart at index zero. Total chunks are respectively 67, 70, 76 or 88:
primary `(2 + ceil(16384/LBS)) * (LBS/512)` followed by backup
`(1 + ceil(16384/LBS)) * (LBS/512)`.

DM table starts, lengths and backing offsets always use 512-byte sectors.
`pp-range BACKING OFFSET ro|rw` remaps through upstream DM; `pp-meta CHUNK_OFFSET`
copies only its target segment from complete staging. The first target snapshot
freezes generation and geometry until reset. Metadata target boundaries must be
logical-block aligned; metadata io_hints preserve the staged logical geometry.
`pp-hole` takes no parameters and rejects access except flush.

## Publication, reload and teardown

`commit` accepts `1` or `seal`. It checks the actual composite queue logical
block size against the uploaded geometry before namespace mutation, pins every
endpoint and its containing disk, retains PARTNAME rollback records, optionally
seals non-writable disks/partitions, adopts the anchor disk's parent device,
hides selected PARTNAMEs, then enables DM partition scanning. The composite is
a sibling of the anchor disk, not nested beneath it. Stock Android requires a
recognized boot-device ancestor to create global partition `by-name` links;
the platform adapter selects the physical ESP device on that boot controller.
An anchor with no physical parent, the composite itself, or a descendant is
refused. The anchor does not enter the hide/seal endpoint set.

The upstream `device_move` is the last fallible commit operation. Nothing after
it may fail without restoring the live device's ancestry first. Reset never
moves a deleted device; it releases the retained anchor-parent reference.
Userspace must issue a real partition-table reread and verify GPT PARTNAME
discovery; stock ueventd sanitizes slash names. No physical GPT is rewritten.
`sealed` describes owned read-only changes, not a cryptographic security boundary.

Reload only via upstream DM inactive table plus suspend/resume, with unchanged
layout and predeclared participants. No remove/recreate switch. On publication
failure remove the mapping normally before reset. Ordinary busy DM removal must
fail without restoring namespace/seal state: no force or deferred removal.
`reset=1` refuses while the published disk is alive or has openers. After ordinary
removal it restores only owned PARTNAME/read-only/flags changes and releases pins.
Endpoint mutation is refused while active. No privileged unseal shortcut exists.

## Build and evidence

Use the root exact-KMI producer and schema-2 receipts. Private DM/configfs imports
are admitted only against the supplied System.map and require the product's
compatible prebinding loader or real exports; namespace and exported CRC gates
remain mandatory. ABI5 passed exact generation-6 admission on aarch64 and x86_64.
The phone mounted projected `/metadata` and encrypted `/data` with stock init
and reached `sys.boot_completed=1` in permissive mode
(`20261010T232708Z-egysk-cutover`). Anchored multi-LUN sealing, reload and busy
teardown/reset still require device qualification; host geometry tests do not
establish those lifecycle properties.

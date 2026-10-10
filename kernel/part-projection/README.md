# Independent part-projection (configfs ABI 4)

GPL-2.0-only. Artifact `part-projection.ko`, internal module name
`part_projection`. Requires upstream device-mapper and configfs, not the Egysk
helper or an EFI module. It registers `pp-range`, `pp-meta`, `pp-hole`; upstream
DM owns the disk, data BIO splitting/completion, queue intersection and crypto.
There is no standalone projection gendisk or data-copy/crypto-profile engine.

## Configfs and geometry

Mount configfs independently. `/config/part-projection` exposes read-only `abi`
(`4`) and `state` (`idle`, `active`, `sealed`); `dev` is the composite DM device
major:minor. `endpoints/NAME/{dev,hide,writable}` stages each pinned participant.
The owner must prepare all endpoints, including every possible reload backing.
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
seals non-writable disks/partitions, hides selected PARTNAMEs, then enables DM
partition scanning. Userspace must issue a real partition-table reread and verify
GPT PARTNAME discovery; stock ueventd sanitizes slash names. No physical GPT is
rewritten. `sealed` describes those owned read-only changes, not a cryptographic
security boundary.

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
remain mandatory. This ABI4 source cutover has not yet passed the parent build
or device gate. Parent checks must exercise 512/1024/2048/4096 uploads, malformed
ordering/generation/geometry rejection, target-owned snapshots, queue limits,
real GPT scanning, reload, busy removal/reset refusal and endpoint restoration.

# Independent part-projection (configfs ABI 3)

GPL-2.0-only; source license and historical provenance are preserved. Artifact
`part-projection.ko`, internal module name `part_projection`. No core module,
root runtime, daemon, or credential provider is required.

## ABI

Mount configfs at `/config`; after loading, the subsystem is:

```
/config/part-projection/
  abi                 read-only: 3
  format              read-only: gpt
  state               read-only: idle | staged | active | failed
  last_error          read-only: 0 or negative lifecycle-operation errno
  commit              write-only: 1 or seal (optional final newline)
  destroy             write-only: 1, unsealed active whole-view teardown only
  projections/<label>/dev   decimal major:minor, initially 0:0 (unset)
  projections/<label>/ro    0 or 1, initially 0
  hide/<major>:<minor>/     canonical decimal device name, no attributes
```

Construction and writes require `CAP_SYS_ADMIN`; configfs owns directory access
permissions. Create one projection directory per printable ASCII GPT label (1–36
bytes, no slash), write its backend `dev`, optionally write `ro=1`. Create hide
items using canonical decimal device numbers (no leading zeros). There are at
most 128 projections and 256 hidden partitions. Duplicate labels are rejected by
configfs; duplicate projection devices and hidden devices return `EEXIST`.
Physical partitions may intentionally appear in both projection and hide sets.
Device encoding must round-trip through `dev_t`, and zero is invalid.

Creating/editing/removing an entry transitions idle/staged/failed to `staged`
(or `idle` when no entries remain) and clears `last_error`. Commit requires at
least one fully configured projection. Invalid numbers, unset/nonexistent
backends, non-partition hide devices, empty/unaligned/overflowing capacities,
and writable views of read-only backends fail with the actual kernel errno.
Construction limits return `ENOSPC`; malformed input returns `EINVAL`.

A commit snapshots construction under the configfs subsystem and control locks,
dependency-pins every item against removal, acquires all backing handles, creates
and verifies the GPT view, hides physical PARTNAMEs, and optionally seals.
`state=active` and `/sys/module/part_projection/parameters/ready=Y` are published
only after the entire operation succeeds. Failure unwinds the disk, hides, seal,
I/O pools and handles, releases item dependencies, reports `state=failed` and
negative `last_error`, and leaves construction entries available for correction.
Corrected configuration can be committed again. Invalid/repeated commits cannot
clear an existing active view's readiness; all active writes and mkdir return
`EBUSY`, and dependency-pinned entries refuse rmdir with `EBUSY`.

Abort is userspace removal of all staged/failed child directories; no special
abort attribute or compatibility ioctl exists. An active view cannot be mutated.
Root `destroy=1` removes an **unsealed** active view as a whole after checking all
synthetic disk/partition openers and holders under the disk open mutex. It closes
the open gate under that same mutex before withdrawing the disk, so concurrent
opens cannot race successful teardown. Busy refusal (`EBUSY`) preserves active
state/readiness/dependencies; a sealed view refuses destroy with `EPERM`, and no
active view returns `ENODEV`. Success clears readiness, restores only owned state,
drains I/O, releases backing handles then configfs dependencies, and leaves
definitions `staged` for reapply/removal. Remove definitions before ordinary
unload because configfs items pin the module. A sealed active view is intentionally
boot-lifetime: no destroy-on-rmdir, forced unload, or unseal backdoor.
`/dev/gptctl`, APPLY/QUERY ioctls and their old UAPI are removed.

## Data path and seal

The dynamic block disk is named `part-projection`. Protective MBR and independent
primary/backup GPT CRCs are RAM-backed; physical GPT sectors are never written.
Each whole backend is projected at a 1-MiB-aligned virtual start. Logical block
size is the stacked backend maximum (up to 4096/PAGE_SIZE); offsets/capacities must
align, fit sector/byte bounds, and remain within the acquired whole device.
Metadata/page padding permit only unencrypted reads; gaps reject I/O.

Partition backends retain both partition and whole-disk file handles. Clones
route through the whole disk plus original start offset, preserve integrity and
inline encryption context/DUNs, and use a slotless stacking crypto profile that
intersects lower capabilities. Key eviction fans out; secret derivation delegates
to a capable lower. Queue limits stack discard/write-zeroes and normal mapped
operations use `submit_bio`. Empty flushes fan out to writable backends. RO views
reject non-read/non-flush I/O and mark synthetic partitions read-only.

After verifying every scanned synthetic partition, hide saves and clears each
physical partition's PARTNAME under its disk open mutex. It does not hide raw
parent disks or revoke open descriptors. Hiding is namespace isolation, not a
storage firewall; caller-owned activation/exclusion is still necessary.

`commit=seal` runs last and applies to exactly referenced disks/partitions, never
unreferenced storage. Disks not backing writable projections become read-only;
on writable disks, non-writable-backend partitions without exclusive holders
become read-only. Existing native read-only flags and dm-held PVs are preserved.
Every owned change is recorded and reversed on failed commit or teardown.
`sealed=Y` reports a completed requested seal. `BD_READ_ONLY` can be cleared by
root via BLKROSET; already-open clients are not revoked and bio_check_ro only
warns. This is not a security firewall.

## Build and admission

```
make -C kernel/part-projection KMI_SRC=/path/to/ack KMI_OUT=/path/to/output \
  KMI_BRANCH=android16-6.12 KMI_GENERATION=6 KMI_ARCH=aarch64 JOBS=4
python3 scripts/kmi_modules.py verify --kmi-out /path/to/output \
  --branch android16-6.12 --generation 6 --arch aarch64 \
  --module kernel/part-projection/part-projection.ko
```

Use exact configured ACK/GKI/DDK outputs, not modules_prepare alone. Standalone
Kbuild also accepts `make -C <kernel> O=<output> M=<absolute-source-dir>
ARCH=arm64|x86_64 LLVM=1 modules`. Release layout is a packaging choice, not this
source path. Copy the schema-2 `.ko.compat.json` with the exact artifact.

Private block imports still require an ELF prebinding loader when absent from
exports; this module exports nothing. CRCs/import versions, ELF architecture,
internal name, vermagic flags, private imports in System.map and input/artifact
hashes remain admission gates. Configfs adds normal kernel API imports; no
root-runtime symbols are imported.

Integration verification must use disposable RAM backends: idle/staged/active
transitions, failed/corrected commits, empty/unset/invalid device errors,
duplicates, 128/256 limits, 36-byte labels, RO I/O, seal/failed-commit rollback with pre-existing RO
flags and exclusive holders, active mkdir/write/rmdir rejection, disk scans,
flush forwarding, rollback handle release, busy/racing destroy refusal, successful
unsealed destroy/reapply and removal/unload, and sealed destroy refusal. Historical ioctl
proof is recorded in PROVENANCE.md; it is not proof of this configfs cutover.
Physical hiding/crypto and enforcing device gates require separate owner approval.

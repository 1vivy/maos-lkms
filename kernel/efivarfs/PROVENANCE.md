# Upstream efivarfs frontend provenance

The filesystem sources are pristine ACK android16-6.12, KMI generation 6,
commit `925a103d123c30a84577f29e1573376aacbde94b`, from
`https://android.googlesource.com/kernel/common` (`fs/efivarfs/`).
Original SPDX notices, authorship and `MODULE_IMPORT_NS(EFIVAR)` are retained.

| Upstream path | SHA-256 |
| --- | --- |
| fs/efivarfs/super.c | 671773f9b0cd9b5ee05bfd7a55608039d67075decc998327cf22078fe38424d0 |
| fs/efivarfs/inode.c | 7ba69dd1ad51af11525a89977e1748855861e9153782f95d2b8926600f190159 |
| fs/efivarfs/file.c | 5fbdf4d179358134c999480f7522b227813c22cef3b822781e4238d3922b7b96 |
| fs/efivarfs/vars.c | 50bf38c3267bc7da8961780acba7ca7516d605d18b4f7a89b253dc007f1baf1f |
| fs/efivarfs/internal.h | ff7818298d360324f9e104f903a1b3073047049dea3a23f89f0c95d3907e38d6 |

Exactly one named patch, `patches/0001-maos-project-guid.patch`, adds the
maos project GUID to the removable-variable allowlist. Kbuild applies it to
ignored/generated `vars-patched.c`; `vars.c` remains byte-identical upstream.
There is no combined backend, registration wrapper, C format engine or host
shim. The filesystem's own upstream module entry point remains unchanged.

Build with `make -C kernel/efivarfs KMI_SRC=... KMI_OUT=... JOBS=4
KMI_BRANCH=android16-6.12 KMI_GENERATION=6 KMI_ARCH=aarch64`.
Standalone Kbuild works with configured ACK/GKI/DDK outputs, arm64 and x86_64.
The shared admission checks the built module against the exact configured kernel
output and writes `<module>.ko.build.json` beside it as release information only;
private imports require a relocating loader if not exported.
`metadata.c` only adds descriptive common `.modinfo` fields, not another init
entrypoint or fake ready flag. Successful mount/read is frontend readiness.
Load this frontend then independent `efivar_store.ko` using `partuuid=<unique
partition GUID>` or `dev=major:minor` (mutually exclusive), or its DT selector.
Mount filesystem type **`efivarfs`** at **`/sys/firmware/efi/efivars`**.
Directory presence alone is not a successful mount. Native EFI ownership and
mountpoint cleanup belong to the independent backend, never the pristine
frontend. See `../efivar_store/PROVENANCE.md` for the pending exact-source pin.

# Module architecture

`maos-lkms` builds four independent Linux kernel modules. Each module has its own Kbuild files and provenance.

| Module | Kernel interface | Boundary |
| --- | --- | --- |
| `dm-thin-pool.ko` | Device-mapper `thin-pool` and `thin` targets | Vendored thin-provisioning implementation with private symbol names |
| `part-projection.ko` | Configfs ABI 6 and `pp-range`, `pp-meta`, `pp-hole` targets | Device-mapper owns data BIO handling, queue stacking, and crypto |
| `efivarfs.ko` | EFI variable filesystem | Upstream efivarfs with the project GUID patch |
| `efivar_store.ko` | Block-backed EFI variable service | C kernel module plus the pinned freestanding Rust EFVS engine |

The modules do not depend on the Egysk helper, daemon, credential provider, or root runtime. The shared header `include/egysk_lkm.h` defines descriptive module metadata and readiness parameters. This metadata does not authorize a caller.

This repository owns module source, build, and KMI admission. It does not own PID 1 orchestration, module activation, product packaging, or Android lifecycle scripts. Consumers load and configure modules through their own runtime contracts. A module's admission result does not establish runtime loading or device qualification.

## References

- [Build and KMI admission](build.md)
- [Design rationale](design.md)
- [Runtime contracts](runtime.md)
- [Verification boundaries](build.md#verification-boundary)
- [`dm-thin-pool`](../kernel/dm-thin-pool/README.md)
- [`part-projection`](../kernel/part-projection/README.md)
- [`efivarfs` provenance](../kernel/efivarfs/PROVENANCE.md)
- [`efivar_store` provenance](../kernel/efivar_store/PROVENANCE.md)

# maos-lkms contributor guidance

Use the shared `asd-ste100` skill for documentation and the shared `engineering-evidence` skill for investigations and behavior claims. Describe only contracts supported by the current source. Separate build/admission evidence from runtime and physical-device qualification.

## Build and host checks

- Host admission contracts: `python3 -m unittest scripts.test_kmi_modules`
- Canonical arm64 DDK build and admission: `sh scripts/build-ddk-lkms.sh android16-6.12 6`
- Caller-supplied exact-kernel build and admission: `sh scripts/build-lkms.sh <branch> <generation> <aarch64|x86_64> <kernel-source> <complete-kernel-output>`
- Pinned clang bootstrap for the caller-supplied lane: `sh scripts/bootstrap-ddk-clang.sh`
- Owned shell entrypoint check: `shellcheck scripts/build-lkms.sh scripts/build-ddk-lkms.sh scripts/bootstrap-ddk-clang.sh kernel/dm-thin-pool/build.sh`

The canonical lane needs Docker and the pinned Rust nightly with `rust-src`. The caller-supplied lane also needs complete matching kernel source and output, the pinned DDK clang, and the same Rust prerequisites. See the root README for required output files and inputs. Generated files belong under ignored `out/`.

Never load modules or write to a phone, physical disk, partition, or block device. Do not run deployment or device commands as a documentation/build check. Report host, build, VM, and physical-device evidence as separate claims.

Use `docs/architecture.md` for module boundaries, `docs/design.md` for rationale, `docs/build.md` for build and admission, and `docs/runtime.md` for module interfaces.

Keep the root README concise. Put module boundaries in `docs/architecture.md`, rationale in `docs/design.md`, build details in `docs/build.md`, and interfaces in `docs/runtime.md`.

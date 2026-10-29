# Extracts the compiler selected by the pinned DDK target into OUT_DIR.
bootstrap branch="android16-6.12" generation="6":
    sh scripts/bootstrap-ddk-clang.sh "{{branch}}" "{{generation}}"

# Build one module without writing into its checked-out source directory.
build module branch generation arch kmi_src kmi_out jobs="4":
    JOBS="{{jobs}}" sh scripts/build-lkms.sh "{{branch}}" "{{generation}}" "{{arch}}" "{{kmi_src}}" "{{kmi_out}}" "{{module}}"

verify artifact branch generation arch kmi_out:
    python3 scripts/kmi_modules.py verify --module "{{artifact}}" --branch "{{branch}}" --generation "{{generation}}" --arch "{{arch}}" --kmi-out "{{kmi_out}}"

# Build the complete two-module product set.
gate branch generation arch kmi_src kmi_out:
    sh scripts/build-lkms.sh "{{branch}}" "{{generation}}" "{{arch}}" "{{kmi_src}}" "{{kmi_out}}"

# Build one module inside the matching digest-pinned DDK image.
gate-ddk-module branch generation module:
    sh scripts/build-ddk-lkms.sh "{{branch}}" "{{generation}}" "{{module}}"

# Build the full arm64 module set inside the matching digest-pinned DDK image.
gate-ddk branch generation:
    sh scripts/build-ddk-lkms.sh "{{branch}}" "{{generation}}"

# Create a build-and-admission-only bundle for a complete module set.
package-candidate branch generation arch:
    python3 scripts/module_set.py package --directory "${OUT_DIR:-out/build-matrix}/modules/{{branch}}-{{generation}}/{{arch}}" --out "${OUT_DIR:-out/build-matrix}/release/{{branch}}-{{generation}}/{{arch}}"

# Source-and-binary candidate archive with deterministic checksums and notices.
release-candidate branch generation arch:
    python3 scripts/module_set.py package --release --directory "${OUT_DIR:-out/build-matrix}/modules/{{branch}}-{{generation}}/{{arch}}" --out "${OUT_DIR:-out/build-matrix}/release/{{branch}}-{{generation}}/{{arch}}"

host-contract:
    python3 -m unittest scripts.test_kmi_modules scripts.test_module_set scripts.test_source_manifest

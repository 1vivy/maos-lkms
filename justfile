# Independent source layout, exact configured ACK/DDK artifacts, no daemon/init builds.
build module branch generation arch kmi_src kmi_out jobs="4":
    python3 scripts/kmi_modules.py build --module-dir "kernel/{{module}}" --module "{{module}}" --branch "{{branch}}" --generation "{{generation}}" --arch "{{arch}}" --kmi-src "{{kmi_src}}" --kmi-out "{{kmi_out}}" --jobs "{{jobs}}"

verify artifact branch generation arch kmi_out:
    python3 scripts/kmi_modules.py verify --module "{{artifact}}" --branch "{{branch}}" --generation "{{generation}}" --arch "{{arch}}" --kmi-out "{{kmi_out}}"

# Builds all four LKMs and standalone efivar_store; verifies the exact outputs.
gate branch generation arch kmi_src kmi_out:
    sh scripts/build-lkms.sh "{{branch}}" "{{generation}}" "{{arch}}" "{{kmi_src}}" "{{kmi_out}}"

host-contract:
    python3 -m unittest scripts.test_kmi_modules

# Reporting Security Issues

These are independent privileged kernel modules, not a root provider or a hostile-root isolation boundary. Report memory-safety defects, callback/reference lifetime errors, invalid state transitions, unauthorized configfs operations, incorrect read-only enforcement, or KMI admission errors.

`part-projection` changes the visible partition view without writing physical GPT metadata. Privileged raw whole-device access is outside that view's enforcement boundary. Destroy must preserve active mappings when sealed or busy. Metadata/readiness fields do not authorize a caller or repair incompatible kernel layouts.

`dm-thin-pool` presents device-mapper thin-provisioning targets. Report metadata corruption, leaked device or pool references, incorrect teardown order, or readiness that reports ready before every subsystem initialized.

Report privately through the owner's [Egysk security advisory form](https://github.com/1vivy/egysk/security/advisories/new).
Include the exact source revision, module hash and build info, kernel
source/configuration/KMI, architecture, operation sequence and observed failure.
Keep reports and exploits private until coordinated disclosure.

Report defects demonstrably present in an upstream component to that component's maintainers as well. Product-specific reports should not be attributed to upstream without reproducing them there. Preserve each project's license and provenance; the inherited root license does not relicense separately licensed kernel sources.

# Reporting Security Issues

These are independent privileged kernel modules, not a root provider or a hostile-root isolation boundary. Report memory-safety defects, callback/reference lifetime errors, invalid state transitions, unauthorized configfs operations, incorrect read-only enforcement, KMI admission errors, EFI backing-store corruption, or incorrect credential overrides.

`part-projection` changes the visible partition view without writing physical GPT metadata. Privileged raw whole-device access is outside that view's enforcement boundary. Destroy must preserve active mappings when sealed or busy. Metadata/readiness fields do not authorize a caller or repair incompatible kernel layouts.

`efivar_store` retains only its backing file opener credentials for narrowly bracketed I/O. It must restore caller credentials on every path, preserve native EFI sysfs ownership, and refuse blank storage without writes. No root-runtime credential provider is involved. A build or permissive VM round-trip does not establish enforcing Android HAL access or safe device deployment.

The current private reporting route remains the owner's existing [GitHub security advisory form](https://github.com/1vivy/kernelesp/security/advisories/new); repository renames and new remote reporting endpoints are owner-controlled. Include the exact source revision, module hash and receipt, kernel source/configuration/KMI, architecture, operation sequence and observed failure. Keep reports and exploits private until coordinated disclosure.

Report defects demonstrably present in an upstream component to that component's maintainers as well. Product-specific reports should not be attributed to upstream without reproducing them there. Preserve each project's license and provenance; the inherited root license does not relicense separately licensed kernel sources.

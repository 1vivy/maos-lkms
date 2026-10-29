#!/usr/bin/env python3
"""Build and admit ACK KMI modules (arm64 phones, x86_64 Cuttlefish).

Admission runs at build time against the supplied kernel output (`--kmi-out`)
and, for the pinned DDK arm64 lane, the published KMI ABI (`--kmi-abi`,
`gki/<arch>/abi.stg`): vermagic flags, optional relocation kinds, and every
undefined symbol present in the target export/symbol list. CRCs are not
compared against `Module.symvers`, because the product's loader
(`egysk/modules/lkm-loader`, a KernelSU `ksuinit` derivative) prebinds every
undefined symbol to its running-kernel address (`SHN_ABS`) before
`init_module`, so the kernel never evaluates their version records. The one
exception is `module_layout`, which the kernel checks itself
(`check_modstruct_version`) independent of prebinding: a present record for it
must match the target KMI's published CRC, or the kernel refuses the module.
An absent or empty `__versions` table loads with a taint warning on a kernel
built without `CONFIG_MODULE_FORCE_LOAD` (the GKI default); this is the
expected shape of a module built through the DDK's patched modpost. Each
build additionally writes `<module>.ko.build.json` release information
beside the artifact. That file is descriptive output for release readers:
nothing admits, re-checks or packages it, and the admission check itself
reads no side file.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, NotRequired, TypedDict

try:
    from . import source_manifest
except ImportError:
    import source_manifest

PathInput = str | os.PathLike[str]
SymbolCrcs = dict[str, int]
SectionHeader = tuple[int, int, int, int, int, int, int, int, int, int]
RawSymbol = tuple[int, int, int, int, int, int]
class Symbol(NamedTuple):
    name: str
    info: int
    shndx: int
    value: int


class Kmi(TypedDict):
    branch: str
    generation: int


class Imports(TypedDict):
    versioned: int
    kallsyms: list[str]


class Modinfo(TypedDict):
    name: str
    vermagic: str


class ModuleFacts(TypedDict):
    """What admission observed in one module: the release-relevant ELF facts."""

    imports: Imports
    modinfo: Modinfo


class BuildInfo(TypedDict):
    """Release information written beside a built module (never an admission input)."""

    schema_version: int
    kmi: Kmi
    kmi_out_inputs: dict[str, str]
    kmi_abi: NotRequired[dict[str, str]]
    module_sha256: str
    imports: Imports
    modinfo: Modinfo
    compiler: NotRequired[dict[str, str]]
    debug_artifact: NotRequired[dict[str, str]]
    module_provenance: NotRequired[dict[str, str]]
    source_evidence: NotRequired[dict[str, dict[str, str]]]


class ModuleReport(TypedDict):
    module: str
    kmi: Kmi
    imports: Imports

#: ELF machine -> (kbuild ARCH, vermagic flags after the release). x86_64 defines
#: no MODULE_ARCH_VERMAGIC, so its vermagic ends at `modversions`.
ARCHES = {183: ("arm64", "SMP preempt mod_unload modversions aarch64"),
          62: ("x86_64", "SMP preempt mod_unload modversions")}
CONFIG_ARCHES = {"CONFIG_ARM64=y": "arm64", "CONFIG_X86_64=y": "x86_64"}
INPUTS = ("Module.symvers", "System.map", "include/generated/utsrelease.h")
CONFIG_FLAGS = ("CONFIG_MODULE_FORCE_LOAD=y", "CONFIG_KALLSYMS_ALL=y")
IDENTITY_FILES = ("build.config.constants", "build.config.common", "bazel/constants.scl")
class CompatibilityError(ValueError):
    pass


def require(condition: object, reason: str) -> None:
    if not condition:
        raise CompatibilityError(reason)


def digest(path: PathInput) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Elf:
    """Bounded ELF64 little-endian section/symbol reader (no host tool parsing)."""

    path: Path
    data: bytes
    kind: int
    machine: int
    headers: list[SectionHeader]
    sections: dict[str, SectionHeader]

    def __init__(self, path: PathInput) -> None:
        self.path = Path(path)
        self.data = self.path.read_bytes()
        require(len(self.data) >= 64 and self.data[:7] == b"\x7fELF\x02\x01\x01", "elf: expected little-endian ELF64")
        self.kind, self.machine = struct.unpack_from("<HH", self.data, 16)
        offset = struct.unpack_from("<Q", self.data, 40)[0]
        size, count, names_index = struct.unpack_from("<HHH", self.data, 58)
        require(size == 64 and count > 0 and names_index < count, "elf: invalid section table")
        table = self.slice(offset, size * count)
        self.headers = list(struct.iter_unpack("<IIQQQQIIQQ", table))
        names_header = self.headers[names_index]
        names = self.slice(names_header[4], names_header[5])
        self.sections = {}
        for header in self.headers[1:]:
            name = self.string(names, header[0])
            require(name not in self.sections, f"elf: duplicate section {name}")
            self.sections[name] = header
            if header[1] != 8:  # SHT_NOBITS has no file contents.
                _ = self.slice(header[4], header[5])

    def slice(self, offset: int, size: int) -> bytes:
        require(offset <= len(self.data) and size <= len(self.data) - offset, "elf: truncated section")
        return self.data[offset:offset + size]

    @staticmethod
    def string(data: bytes, offset: int) -> str:
        require(offset < len(data), "elf: invalid string offset")
        end = data.find(b"\0", offset)
        require(end >= 0, "elf: unterminated string")
        return data[offset:end].decode("ascii")

    def section(self, name: str) -> bytes:
        header = self.sections.get(name)
        return self.slice(header[4], header[5]) if header else b""

    def symbols(self) -> list[Symbol]:
        require(".symtab" in self.sections, "elf: missing symbol table")
        header = self.sections[".symtab"]
        require(header[9] == 24 and header[5] % 24 == 0 and header[6] < len(self.headers), "elf: malformed symbol table")
        strings = self.headers[header[6]]
        names = self.slice(strings[4], strings[5])
        records: Iterator[RawSymbol] = struct.iter_unpack("<IBBHQQ", self.section(".symtab"))
        return [Symbol(self.string(names, name), info, shndx, value)
                for name, info, _, shndx, value, _ in records]

    def verify_x86_relocations(self) -> None:
        # arch/x86/kernel/module.c applies only these types. In particular,
        # a freestanding target must not emit userspace GOT references.
        supported = {0, 1, 2, 4, 10, 11, 24}
        for name, header in self.sections.items():
            if header[1] not in (4, 9):  # SHT_RELA, SHT_REL
                continue
            require(header[7] < len(self.headers), f"relocations: invalid target in {name}")
            if not self.headers[header[7]][2] & 2:  # Only SHF_ALLOC targets are loaded.
                continue
            require(header[1] == 4 and header[9] == 24 and header[5] % 24 == 0,
                    f"relocations: malformed x86_64 RELA table {name}")
            for _, info, _ in struct.iter_unpack("<QQq", self.section(name)):
                kind = info & 0xffffffff
                require(kind in supported, f"relocations: unsupported x86_64 type {kind} in {name}")


def symvers(path: PathInput) -> SymbolCrcs:
    result: SymbolCrcs = {}
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        require(len(fields) >= 4, f"symvers: malformed line in {path}")
        crc, name = int(fields[0], 16), fields[1]
        require(name not in result, f"symvers: duplicate {name}")
        require(0 <= crc <= 0xffffffff, f"symvers: invalid CRC for {name}")
        result[name] = crc
    return result


def version_records(elf: Elf) -> SymbolCrcs:
    """Parse `__versions`/`__version_ext_*` if present. Absence is a distinct,
    load-relevant fact from `verify_module`, not an error here: the loader
    prebinds every undefined symbol and the kernel only re-checks
    `module_layout` on its own, so a record's CRC is informational except for
    that one name."""
    normal = elf.section("__versions")
    crcs, names = elf.section("__version_ext_crcs"), elf.section("__version_ext_names")
    tables: list[list[tuple[int, str]]] = []
    if normal:
        require(len(normal) % 64 == 0, "import-versions: malformed __versions records")
        tables.append([(crc, Elf.string(name, 0)) for crc, name in struct.iter_unpack("<Q56s", normal)])
    if crcs:
        require(len(crcs) % 4 == 0 and names.endswith(b"\0"), "import-versions: malformed extended versions")
        strings = names[:-1].split(b"\0")
        # modpost emits concatenated C strings with explicit per-name NULs,
        # followed by the C initializer's implicit final NUL.
        if strings and strings[-1] == b"":
            _ = strings.pop()
        require(len(strings) == len(crcs) // 4, "import-versions: extended count mismatch")
        tables.append([(crc[0], name.decode("ascii")) for crc, name in zip(struct.iter_unpack("<I", crcs), strings)])
    versions: SymbolCrcs = {}
    for records in tables:
        seen: set[str] = set()
        for crc, name in records:
            require(name and name not in seen and 0 <= crc <= 0xffffffff, "import-versions: invalid or duplicate record")
            require(name not in versions or versions[name] == crc, f"import-versions: basic/extended CRC mismatch for {name}")
            seen.add(name)
            versions[name] = crc
    return versions


def abi_symbols(path: PathInput) -> SymbolCrcs:
    """The published KMI's exported symbols and CRCs from a `gki/<arch>/abi.stg`
    ABI monitoring dump (`elf_symbol { name: "..." is_defined: true crc: 0x... }`
    records). Not every real export of a build against this branch is
    necessarily listed here (the ABI snapshot can lag the branch tip); callers
    combine it with the target `Module.symvers`/`System.map`, not use it alone."""
    result: SymbolCrcs = {}
    name: str | None = None
    defined = False
    crc: int | None = None
    in_record = False
    for line in Path(path).read_text().splitlines():
        text = line.strip()
        if text == "elf_symbol {":
            require(not in_record, "abi: nested elf_symbol record")
            in_record, name, defined, crc = True, None, False, None
        elif in_record and text == "}":
            if defined and name is not None:
                require(crc is not None, f"abi: {name} is_defined with no crc")
                require(name not in result, f"abi: duplicate {name}")
                result[name] = crc
            in_record = False
        elif in_record and text.startswith("name: "):
            name = text[len("name: "):].strip('"')
        elif in_record and text.startswith("is_defined: "):
            defined = text[len("is_defined: "):] == "true"
        elif in_record and text.startswith("crc: "):
            crc = int(text[len("crc: "):], 16)
    require(not in_record, "abi: unterminated elf_symbol record")
    require("module_layout" in result, "abi: missing module_layout; not a KMI ABI dump")
    return result


def config_flags(output: Path) -> set[str]:
    """The `.config` lines this admission cares about, or an empty set without one."""
    config = output / ".config"
    if not config.is_file():
        return set()
    return {line for line in config.read_text().splitlines() if line in CONFIG_FLAGS}


def kernel_arch(output: Path) -> str | None:
    """The kbuild ARCH of a KMI output tree from its `.config`, or None without one."""
    config = output / ".config"
    if not config.is_file():
        return None
    found = {CONFIG_ARCHES[line] for line in config.read_text().splitlines() if line in CONFIG_ARCHES}
    require(len(found) == 1, "kmi-out: .config names neither or both of CONFIG_ARM64 and CONFIG_X86_64")
    return found.pop()


def kmi_identity(source: Path, branch: str, generation: int) -> Kmi:
    require(re.fullmatch(r"android\d+-\d+\.\d+", branch), "kmi: specify an exact ACK branch")
    require(generation >= 0, "kmi: specify an exact nonnegative generation")
    constants = "\n".join((source / name).read_text() for name in IDENTITY_FILES if (source / name).is_file())
    generations = {int(value) for value in re.findall(r"^KMI_GENERATION=[\"']?(\d+)[\"']?\s*$", constants, re.MULTILINE)}
    require(generations == {generation}, "kmi: source generation mismatch or ambiguity")
    branches = set(re.findall(r"^BRANCH=[\"']?([a-z0-9.-]+)[\"']?\s*$", constants, re.MULTILINE))
    require(branches == {branch}, "kmi: missing, mismatched or ambiguous source branch")
    return {"branch": branch, "generation": generation}


def clang_version(source: Path) -> str:
    """Return the exact compiler revision declared by the ACK source."""
    constants = "\n".join((source / name).read_text()
                          for name in IDENTITY_FILES if (source / name).is_file())
    versions = set(re.findall(r"^CLANG_VERSION=[\"']?([A-Za-z0-9._-]+)[\"']?\s*$",
                              constants, re.MULTILINE))
    require(len(versions) == 1, "compiler: source has missing or ambiguous CLANG_VERSION")
    return versions.pop()


def verify_module(path: PathInput, name: str, output: Path, architecture: str | None = None,
                  abi: Path | None = None) -> ModuleFacts:
    """Admit one built module against the exact kernel output and, on the DDK
    arm64 lane, the published KMI ABI; no side file is read.

    Every undefined symbol must be exported by the target KMI (`abi`, when
    given, or `Module.symvers`) or present in the target `System.map` on a
    kernel that makes every symbol visible to the loader's kallsyms resolver
    (`CONFIG_KALLSYMS_ALL=y`): the loader itself resolves imports this way,
    not modversion CRCs. A present `module_layout` version record must match
    the target KMI's published CRC regardless, because the kernel checks that
    one itself (`check_modstruct_version`), independent of prebinding. An
    absent or empty `__versions` table is only admitted on a target that does
    not set `CONFIG_MODULE_FORCE_LOAD` (the GKI default); on a force-load
    kernel the loader's unflagged `init_module` would be refused outright.
    """
    elf = Elf(path)
    require(elf.kind == 1 and elf.machine in ARCHES, "elf: expected ET_REL aarch64 or x86_64")
    arch, flags = ARCHES[elf.machine]
    requested = {"aarch64": "arm64", "x86_64": "x86_64"}.get(architecture) if architecture else None
    require(architecture is None or requested == arch, "elf: requested architecture mismatch")
    tree = kernel_arch(output)
    require(tree is None or tree == arch, f"elf: {arch} module for a {tree} KMI tree")
    if elf.machine == 62:
        elf.verify_x86_relocations()
    imports = {s.name for s in elf.symbols() if s.name and s.shndx == 0}
    versions = version_records(elf)
    exported = symvers(output / "Module.symvers")
    layout_crc = exported.get("module_layout")
    target = set(exported)
    if abi is not None:
        abi_exported = abi_symbols(abi)
        layout_crc = abi_exported["module_layout"]
        target |= abi_exported.keys()
    if "module_layout" in versions:
        require(layout_crc is not None, "import-versions: module_layout CRC unknown for this target; pass --kmi-abi")
        require(versions["module_layout"] == layout_crc,
                "import-versions: module_layout CRC does not match the target KMI (the kernel checks this one itself)")
    flags_present = config_flags(output)
    if not versions:
        require("CONFIG_MODULE_FORCE_LOAD=y" not in flags_present,
                "import-versions: empty __versions is refused by this target's CONFIG_MODULE_FORCE_LOAD=y")
    private = imports - target
    if private:
        kernel_symbols = {line.split()[2] for line in (output / "System.map").read_text().splitlines() if len(line.split()) >= 3}
        missing = private - kernel_symbols
        require(not missing, "imports: absent from the target KMI export/symbol list: " + ", ".join(sorted(missing)))
        require("CONFIG_KALLSYMS_ALL=y" in flags_present,
                "imports: private imports require this target's CONFIG_KALLSYMS_ALL=y for the loader's kallsyms resolver: "
                + ", ".join(sorted(private)))
    modinfo = elf.section(".modinfo").split(b"\0")
    vermagic = [entry[9:].decode("ascii") for entry in modinfo if entry.startswith(b"vermagic=")]
    tokens = vermagic[0].split() if len(vermagic) == 1 else []
    require(len(tokens) == 1 + len(flags.split()) and tokens[1:] == flags.split(), "vermagic: expected release followed by " + flags)
    names = [entry[5:].decode("ascii") for entry in modinfo if entry.startswith(b"name=")]
    require(names == [name.replace("-", "_")], "modinfo: module name mismatch")
    return {"imports": {"versioned": len(versions), "kallsyms": sorted(imports)},
            "modinfo": {"name": names[0], "vermagic": vermagic[0]}}


def build_info_path(module: PathInput) -> Path:
    return Path(str(module) + ".build.json")


def strip_debug(path: Path, name: str, env: Mapping[str, str]) -> dict[str, str]:
    """Remove only debug sections, before admission and byte hashing.

    The separate debug artifact keeps the original bytes. Signed modules are
    refused because stripping would invalidate the signature.
    """
    elf = Elf(path)
    require(".module_sig" not in elf.sections and b"~Module signature appended~" not in elf.data,
            "strip: refusing to alter signed module bytes")
    strip = os.environ.get("LLVM_STRIP")
    if not strip:
        clang_dir = env.get("DDK_CLANG_DIR")
        candidate = Path(clang_dir) / "llvm-strip" if clang_dir else None
        strip = str(candidate) if candidate is not None and candidate.is_file() else shutil.which(
            "llvm-strip", path=env.get("PATH"))
    require(strip is not None, "strip: target-matched llvm-strip is unavailable")
    debug = path.with_name(name + ".ko.debug")
    shutil.copyfile(path, debug)
    subprocess.run([strip, "--strip-debug", str(path)], check=True)
    return {"name": debug.name, "sha256": digest(debug)}


def capture_source_evidence(directory: Path) -> dict[str, dict[str, str]]:
    """Hash the exact staged source inputs before Kbuild runs."""
    evidence = {"module": source_manifest.inventory(directory)}
    repo = Path(__file__).resolve().parents[1]
    tools = repo / "scripts"
    if tools.is_dir():
        evidence["tools"] = source_manifest.inventory(tools)
    if not (directory / "include").is_dir():
        for candidate in (directory.parents[1] / "include", directory.parents[2] / "include"):
            if candidate.is_dir():
                evidence["include"] = source_manifest.inventory(candidate)
                break
    return evidence


def verify_source_evidence(evidence: dict[str, dict[str, str]], directory: Path,
                           name: str) -> None:
    source_manifest.verify(directory, evidence.get("module"))
    repo = Path(__file__).resolve().parents[1]
    if "tools" in evidence:
        source_manifest.verify(repo / "scripts", evidence["tools"])
    if "include" in evidence:
        for candidate in (directory.parents[1] / "include", directory.parents[2] / "include"):
            if candidate.is_dir():
                source_manifest.verify(candidate, evidence["include"])
                break
        else:
            raise ValueError(f"source evidence: shared include disappeared for {name}")


def build_info(output: Path, module: PathInput, identity: Kmi, facts: ModuleFacts,
               abi: Path | None = None,
               compiler: dict[str, str] | None = None,
               module_provenance: dict[str, str] | None = None,
               debug_artifact: dict[str, str] | None = None,
               source_evidence: dict[str, dict[str, str]] | None = None) -> BuildInfo:
    """Release information for the artifact. Input hashes are keyed by basename, not host path."""
    result: BuildInfo = {"schema_version": 2, "kmi": identity,
                         "kmi_out_inputs": {Path(name).name: digest(output / name) for name in INPUTS},
                         "module_sha256": digest(module), "imports": facts["imports"],
                         "modinfo": facts["modinfo"]}
    if abi is not None:
        result["kmi_abi"] = {Path(abi).name: digest(abi)}
    if compiler is not None:
        result["compiler"] = compiler
    if module_provenance is not None:
        result["module_provenance"] = module_provenance
    if debug_artifact is not None:
        result["debug_artifact"] = debug_artifact
    if source_evidence is not None:
        result["source_evidence"] = source_evidence
    return result


def verify_payload(output: PathInput, modules: Sequence[PathInput], branch: str,
                   generation: int, architecture: str, abi: PathInput | None = None) -> list[ModuleReport]:
    """Admit already-built modules against the exact kernel output and, on the
    DDK arm64 lane, the published KMI ABI; nothing is read or written."""
    output = Path(output).resolve(strict=True)
    abi_path = Path(abi).resolve(strict=True) if abi else None
    require(re.fullmatch(r"android\d+-\d+\.\d+", branch) and generation >= 0,
            "kmi: exact branch and generation required")
    identity: Kmi = {"branch": branch, "generation": generation}
    reports: list[ModuleReport] = []
    for module in modules:
        name = Path(module).stem
        facts = verify_module(module, name, output, architecture, abi_path)
        source = output / "source"
        if any((source / identity_file).is_file() for identity_file in IDENTITY_FILES):
            # The output's own source tree must claim the identity being admitted.
            _ = kmi_identity(source, branch, generation)
        reports.append({"module": name, "kmi": identity, "imports": facts["imports"]})
    return reports


def run_kbuild(command: Sequence[str], env: Mapping[str, str], log: Path,
               append: bool = False) -> None:
    """Stream complete build logs, rejecting objtool diagnostics even on exit 0."""
    diagnostic: str | None = None
    overlap = ""
    with log.open("a" if append else "w") as stream:
        stream.write("command: " + repr(list(command)) + "\n")
        with subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors="replace") as process:
            assert process.stdout is not None
            while chunk := process.stdout.readline(65536):
                stream.write(chunk)
                stream.flush()
                print(chunk, end="", file=sys.stderr)
                # Bounded overlap catches a diagnostic split across long output
                # chunks; do not buffer the entire compiler output in memory.
                window = overlap + chunk
                if diagnostic is None and re.search(r"\bobjtool:\s", window, re.IGNORECASE):
                    diagnostic = window[-2048:].strip()
                overlap = window[-128:]
            status = process.wait()
    if status:
        raise subprocess.CalledProcessError(status, command)
    require(diagnostic is None, f"objtool: diagnostic rejects module admission; log {log}: {diagnostic}")


def build(args: argparse.Namespace) -> ModuleReport:
    require(len(args.module) == 1 and args.module_dir, "build: specify one --module and --module-dir")
    require(args.kmi_src, "build: --kmi-src or KMI_SRC is required")
    source, output = Path(args.kmi_src).resolve(strict=True), Path(args.kmi_out).resolve(strict=True)
    identity = kmi_identity(source, args.branch, args.generation)
    output_source = output / "source"
    if any((output_source / name).is_file() for name in IDENTITY_FILES):
        require(identity == kmi_identity(output_source, args.branch, args.generation),
                "kmi: build source/output identity mismatch")
    require(1 <= args.jobs <= 13, "build: jobs must be 1..13")
    name = args.module[0]
    require(re.fullmatch(r"[A-Za-z0-9_-]+", name), "build: invalid module artifact name")
    directory = Path(args.module_dir).resolve(strict=True)
    require((directory / "Kbuild").is_file(), "build: module directory has no standalone Kbuild")
    module_output = Path(args.output_dir).resolve() if args.output_dir else directory
    module_output.mkdir(parents=True, exist_ok=True)
    module = module_output / (name + ".ko")
    build_info_path(module).unlink(missing_ok=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("CONFIG_", "KBUILD_")) and key not in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "KCFLAGS", "KCPPFLAGS", "CFLAGS_MODULE", "LDFLAGS_MODULE")}
    clang = shutil.which("clang", path=env.get("PATH"))
    require(clang is not None, "compiler: clang is absent from PATH")
    expected_clang = clang_version(source)
    clang_line = subprocess.check_output([clang, "--version"], text=True).splitlines()[0]
    require(expected_clang in clang_line,
            f"compiler: expected {expected_clang} from kernel source, got {clang_line}")
    compiler = {"version": expected_clang, "version_line": clang_line,
                "sha256": digest(clang)}
    module_provenance = None
    provenance_path = directory / "PROVENANCE.json"
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text())
        require(isinstance(provenance, dict) and provenance.get("module") == name,
                "provenance: missing or mismatched module identity")
        require(provenance.get("kmi") == {"branch": args.branch,
                "generation": args.generation, "arch": args.arch},
                "provenance: KMI identity mismatch")
        kernel = provenance.get("kernel")
        require(isinstance(kernel, dict), "provenance: missing kernel identity")
        profile = provenance.get("profile")
        release = kernel.get("release")
        require(profile in ("verified", "generated") and isinstance(release, str),
                "provenance: missing profile or kernel release")
        module_provenance = {"sha256": digest(provenance_path),
                             "profile": profile, "kernel_release": release}
    arch = kernel_arch(output)
    require(arch == {"aarch64": "arm64", "x86_64": "x86_64"}[args.arch],
            "build: KMI output architecture mismatch or missing .config")
    command = ["make", "-C", str(source), "O=" + str(output), "M=" + str(directory), "ARCH=" + str(arch), "LLVM=1", "KBUILD_GENDWARFKSYMS_STABLE=1", "KBUILD_MODPOST_WARN=1"]
    log = module_output / (name + ".build.log")
    run_kbuild(command + ["clean"], env, log)
    source_evidence = capture_source_evidence(directory)
    run_kbuild(command + ["modules", f"-j{args.jobs}"], env, log, append=True)
    if module_output != directory:
        # Kernels before 6.13 have no MO=, so kbuild writes the module into the
        # external module directory. Move the shipped bytes into the output
        # directory and clean the intermediates: no artifact stays behind.
        shutil.move(str(directory / (name + ".ko")), str(module))
        run_kbuild(command + ["clean"], env, log, append=True)
    verify_source_evidence(source_evidence, directory, name)
    abi_path = Path(args.kmi_abi).resolve(strict=True) if args.kmi_abi else None
    debug_artifact = strip_debug(module, name, env) if args.strip_debug else None
    facts = verify_module(module, name, output, args.arch, abi_path)
    build_info_path(module).write_text(json.dumps(
        build_info(output, module, identity, facts, abi_path,
                   compiler, module_provenance, debug_artifact, source_evidence),
        indent=2, sort_keys=True) + "\n")
    return {"module": name, "kmi": identity, "imports": facts["imports"]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--kmi-src", default=os.environ.get("KMI_SRC"))
    parser.add_argument("--kmi-out", default=os.environ.get("KMI_OUT"), required=not os.environ.get("KMI_OUT"))
    parser.add_argument("--kmi-abi", default=os.environ.get("KMI_ABI"))
    parser.add_argument("--module", action="append", required=True)
    parser.add_argument("--module-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--arch", choices=("aarch64", "x86_64"), required=True)
    parser.add_argument("--jobs", type=int, default=13)
    parser.add_argument("--strip-debug", action="store_true",
                        help="run target-matched llvm-strip --strip-debug before final admission")
    args = parser.parse_args(argv)
    try:
        result = build(args) if args.action == "build" else verify_payload(args.kmi_out, args.module, args.branch, args.generation, args.arch, args.kmi_abi)
        print(json.dumps({"status": "accepted", "kmi": {"branch": args.branch, "generation": args.generation}, "result": result}, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, struct.error, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "rejected", "reason": str(error)}, sort_keys=True))
        print(f"kmi-modules: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

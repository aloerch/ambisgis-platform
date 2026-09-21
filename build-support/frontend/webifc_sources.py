#!/usr/bin/env python3
"""Verify web-ifc 0.0.50 inputs and create a private notice/source stage offline."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

HERE = Path(__file__).resolve().parent
REVISION = "b55d8bde10067415d4536b23c27edcc13acf217c"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_record(path, root):
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
            "sha256": digest(path.read_bytes())}


def safe_path(value):
    p = PurePosixPath(value)
    require(value and str(p) == value and not p.is_absolute() and ".." not in p.parts,
            "unsafe path: " + value)
    return p


def verified_file(root, row):
    p = root / safe_path(row["path"])
    require(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()), "input symlink/escape")
    require(p.is_file() and p.stat().st_size == row["bytes"] and digest(p.read_bytes()) == row["sha256"],
            "input changed: " + row["path"])
    return p


def archive_files(data):
    """Reject escaping/duplicate/special members before producing any stage."""
    files, prefix, seen = {}, None, set()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            name = member.name.rstrip("/")
            p = safe_path(name)
            require(name not in seen, "duplicate archive member")
            seen.add(name)
            prefix = prefix or p.parts[0]
            require(prefix == p.parts[0], "multiple archive roots")
            require(member.isfile() or member.isdir(), "special archive member")
            if member.isfile():
                require(len(p.parts) > 1, "archive file without root directory")
                files[PurePosixPath(*p.parts[1:]).as_posix()] = archive.extractfile(member).read()
    require(files, "empty source archive")
    return files


def cmake_pins(text):
    pattern = r'FetchContent_Declare\((\w+) GIT_REPOSITORY "(https://github.com/[^" ]+)" GIT_TAG "([a-f0-9]{40})"'
    rows = []
    for line in text.splitlines():
        if not line.lstrip().startswith("#"):
            found = re.search(pattern, line)
            if found:
                rows.append(found.groups())
    require(len(rows) == 8 and len({row[0] for row in rows}) == 8, "expected eight distinct active CMake pins")
    return rows


def verify_tree(files, tree):
    require(tree.get("truncated") is False, "truncated publisher tree")
    rows = [row for row in tree["tree"] if row["type"] == "blob"]
    require(not any(row["type"] == "commit" for row in tree["tree"]), "unretained main-source gitlink")
    require({row["path"] for row in rows} == set(files), "publisher/source membership mismatch")
    for row in rows:
        data = files[row["path"]]
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(row["sha"] == actual, "publisher blob mismatch: " + row["path"])


def verify_pins(cmake, dependencies):
    expected = {(row["name"], row["repository"], row["revision"]) for row in dependencies}
    require(set(cmake_pins(cmake)) == expected, "CMake/dependency lock mismatch")


def verify_package_assets(frontend, npm):
    actual = list(frontend.rglob("*"))
    require(not any(p.is_symlink() for p in actual), "frontend symlink")
    require({p.relative_to(frontend).as_posix() for p in actual if p.is_file()} == set(npm), "frontend package membership changed")
    for name, data in npm.items():
        require((frontend / name).read_bytes() == data, "frontend package bytes changed: " + name)


def verify_wasm_bindings(cpp, npm):
    bindings = re.findall(r'emscripten::function\("([^"\n]+)"', cpp)
    require(len(bindings) == 35, "unexpected C++ binding inventory")
    wasm = {name: data for name, data in npm.items() if name.endswith(".wasm")}
    require(len(wasm) == 3 and all(data.startswith(b"\0asm\1\0\0\0") for data in wasm.values()), "WASM membership/header mismatch")
    for name, data in wasm.items():
        require(all(symbol.encode() + b"\0" in data for symbol in bindings), "C++/WASM binding mismatch: " + name)
    return bindings


def prepare(retained, stage, frontend, lock_path=HERE / "webifc-sources.json"):
    require(not stage.exists() and not stage.is_symlink(), "fresh stage required")
    require(retained.is_dir() and not retained.is_symlink(), "retained directory required")
    require(frontend.is_dir() and not frontend.is_symlink(), "frontend package directory required")
    lock = json.loads(lock_path.read_text())
    require(lock["schema_version"] == 1 and lock["version"] == "0.0.50" and
            lock["main"]["revision"] == REVISION, "unsupported source selection")
    sources = [lock["main"], *lock["dependencies"]]
    require(len(sources) == 9 and len({s["name"] for s in sources}) == 9, "source selection cardinality")
    records = [s["archive"] for s in sources] + [lock["npm_package"], *lock["metadata"]]
    require(len({r["path"] for r in records}) == len(records), "duplicate locked input")
    retained_files = {row["path"]: verified_file(retained, row) for row in records}
    files = {s["name"]: archive_files(retained_files[s["archive"]["path"]].read_bytes()) for s in sources}
    main = files["webifc"]
    tree = json.loads(retained_files["publisher-tree.json"].read_text())
    commit = json.loads(retained_files["publisher-commit.json"].read_text())
    require(commit["sha"] == REVISION and commit["commit"]["tree"]["sha"] == tree["sha"], "publisher revision mismatch")
    verify_tree(main, tree)
    cmake = main["src/wasm/CMakeLists.txt"].decode()
    verify_pins(cmake, lock["dependencies"])
    npm = archive_files(retained_files[lock["npm_package"]["path"]].read_bytes())
    metadata = json.loads(retained_files["npm-web-ifc-0.0.50.json"].read_text())
    require(metadata["gitHead"] == REVISION and metadata["version"] == "0.0.50", "npm revision mismatch")
    require(all(npm[p] == main[p] for p in ("package.json", "README.md")), "publisher/package source mismatch")
    verify_package_assets(frontend, npm)
    bindings = verify_wasm_bindings(main["src/wasm/web-ifc-api.cpp"].decode(), npm)
    stage.mkdir(parents=True)
    (stage / "source-lock.json").write_bytes(lock_path.read_bytes())
    (stage / "executed-recipe.py").write_bytes(Path(__file__).read_bytes())
    for row in records:
        target = stage / "retained" / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(retained_files[row["path"]], target)
    notices = []
    for source in sources:
        for name, data in files[source["name"]].items():
            base = PurePosixPath(name).name.lower()
            if any(token in base for token in ("license", "copying", "notice")):
                target = stage / "notices" / source["name"] / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                notices.append(file_record(target, stage))
    (stage / "SOURCE-AVAILABILITY.txt").write_text(
        "PRIVATE REVIEW STAGE: web-ifc 0.0.50; no distribution or adoption approval.\n"
        "retained/ contains actual complete historical sources and publisher evidence.\n"
        "notices/ preserves historical terms; source headers remain in archives.\n"
        "Before delivery, include applicable MPL source availability and copyright notices\n"
        "and offer these exact usable covered sources through the controlled delivery channel.\n"
        "Review archive fixtures/examples and all third-party terms before public source\n"
        "redistribution; local custody does not permit every archive member to be published.\n"
        "MPL and all exact per-source notice terms/alternatives, including bundled fmt,\n"
        "remain distribution gates. No new license is applied to old code.\n"
        "Emscripten 3.1.44 is declared in historical Dockerfile/workflows; compiler/runtime\n"
        "custody and independent generated-code rebuilding remain FND-08/release work.\n"
        "These unchanged assets are not independently byte-identical rebuilt WASM.\n")
    source_members = {name: [{"path": p, "bytes": len(data), "sha256": digest(data)}
                            for p, data in sorted(members.items())] for name, members in files.items()}
    (stage / "source-members.json").write_text(json.dumps(source_members, indent=2) + "\n")
    compile_inputs = [name for name in main if name.endswith(".cpp") and
                      any(name.startswith("src/wasm/" + part) for part in ("parsing/", "geometry/", "schema/", "utility/"))]
    compile_inputs.append("src/wasm/web-ifc-api.cpp")
    build_paths = ["src/wasm/CMakeLists.txt", "src/wasm/web-ifc-api.cpp", "src/wasm/version.h", "src/web-ifc-api.ts",
                   "src/ifc-schema.ts", "src/schema-generator/gen_functional_types.ts", "src/schema-generator/IFC2X3.exp",
                   "src/schema-generator/IFC4.exp", "src/schema-generator/IFC4X3.exp", "package.json", "package-lock.json",
                   "Dockerfile", ".github/workflows/publish.yml", ".github/workflows/jest.yml"]
    index = {"status": "inventory-requires-success-receipt", "version": "0.0.50", "source_revision": REVISION,
             "source_tree": tree["sha"], "lock_sha256": digest(lock_path.read_bytes()), "sources": sources,
             "source_members_manifest": file_record(stage / "source-members.json", stage),
             "notices": notices, "source_blob_count": len(main),
             "wasm_compile_inputs": sorted(compile_inputs), "bindings": bindings,
             "build_evidence": [{"path": p, "sha256": digest(main[p])} for p in build_paths],
             "package_assets": [{"path": name, "bytes": len(data), "sha256": digest(data),
                                  "identical_package_paths": sorted(n for n, other in npm.items() if other == data)}
                                for name, data in sorted(npm.items())],
             "limits": ["Publisher source/byte/binding evidence supports correspondence, not a byte-identical WASM rebuild.",
                        "Native probe compiles parser/geometry dependencies, not Emscripten-only web-ifc-api.cpp.",
                        "Browser/Node WASM paths have identical bytes; compilation origins cannot be distinguished by filename.",
                        "MT bindings are checked but multithreaded browser behavior is not accepted here.",
                        "Distribution/source delivery and full generated-runtime/toolchain closure remain unaccepted."]}
    (stage / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    inventory = [file_record(p, stage) for p in sorted(stage.rglob("*")) if p.is_file()]
    (stage / "stage-manifest.json").write_text(json.dumps(inventory, indent=2) + "\n")
    for row in records:
        verified_file(retained, row)
    for row in inventory:
        verified_file(stage, row)
    require((stage / "executed-recipe.py").read_bytes() == Path(__file__).read_bytes(), "recipe changed during execution")
    require((stage / "source-lock.json").read_bytes() == lock_path.read_bytes(), "lock changed during execution")
    success = {"status": "passed", "index": file_record(stage / "index.json", stage),
               "stage_manifest": file_record(stage / "stage-manifest.json", stage),
               "recipe": file_record(stage / "executed-recipe.py", stage),
               "source_lock": file_record(stage / "source-lock.json", stage)}
    with (stage / "success.json").open("x") as output:
        json.dump(success, output, indent=2)
        output.write("\n")
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retained", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--frontend-package", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.retained, args.stage, args.frontend_package)
    print(json.dumps({"status": result["status"], "sources": len(result["sources"]),
                      "notices": len(result["notices"]), "assets": len(result["package_assets"])}))


if __name__ == "__main__":
    main()

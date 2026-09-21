#!/usr/bin/env python3
"""Bounded offline native/source usability plus unchanged WASM geometry probe."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import webifc_sources as source

HERE = Path(__file__).resolve().parent


def run(stage, output, frontend, node):
    source.require(not output.exists(), "fresh output required")
    success = json.loads((stage / "success.json").read_text())
    source.require(success["status"] == "passed", "source stage did not pass")
    for key in ("index", "stage_manifest", "recipe", "source_lock"):
        source.verified_file(stage, success[key])
    for row in json.loads((stage / "stage-manifest.json").read_text()):
        source.verified_file(stage, row)
    index = json.loads((stage / "index.json").read_text())
    lock = json.loads((stage / "source-lock.json").read_text())
    npm_archive = source.verified_file(stage / "retained", lock["npm_package"])
    npm = source.archive_files(npm_archive.read_bytes())
    source.verify_package_assets(frontend, npm)
    output.mkdir(parents=True)
    scripts = output / "executed-tooling"
    scripts.mkdir()
    offline = HERE.parents[1] / "build-support/postgis/offline_exec.py"
    for path in (Path(__file__), HERE / "webifc_sources.py", HERE / "webifc_probe.cjs", HERE / "webifc-box.ifc", offline):
        shutil.copyfile(path, scripts / path.name)
    frozen_tooling = [source.file_record(p, scripts) for p in sorted(scripts.iterdir())]
    source_inputs = []
    for row in index["sources"]:
        archive = source.verified_file(stage / "retained", row["archive"])
        dest = output / ("source" if row["name"] == "webifc" else "dependencies/" + row["name"])
        for path, data in source.archive_files(archive.read_bytes()).items():
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            original = target.relative_to(output).as_posix()
            compiled = original.replace("dependencies/fuzzy/src/", "dependencies/fuzzy/fuzzy/", 1) if original.startswith("dependencies/fuzzy/src/") else original
            source_inputs.append({"path": compiled, "archive_member": path, "source": row["name"],
                                  "bytes": len(data), "sha256": source.digest(data)})
    (output / "source-input-manifest.json").write_text(json.dumps(source_inputs, indent=2) + "\n")
    build = output / "build"
    cmake = ["cmake", "-S", str(output / "source/src/wasm"), "-B", str(build),
             "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
             "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"]
    cmake += ["-DFETCHCONTENT_SOURCE_DIR_" + row["name"].upper() + "=" + str(output / "dependencies" / row["name"])
              for row in lock["dependencies"]]
    commands = [("configure", cmake), ("build", ["cmake", "--build", str(build), "--parallel", "2"]),
                ("native-tests", ["ctest", "--test-dir", str(build), "-VV", "-L", "web-ifc"]),
                ("wasm-probe", [str(node), str(scripts / "webifc_probe.cjs"), str(frontend), str(scripts / "webifc-box.ifc")])]
    results = []
    for name, command in commands:
        argv = [sys.executable, str(scripts / "offline_exec.py"), "--evidence", str(output / (name + "-network.json")), "--", *command]
        start = time.monotonic()
        with (output / (name + ".log")).open("xb") as log:
            result = subprocess.run(argv, cwd=output, stdout=log, stderr=subprocess.STDOUT,
                                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        row = {"argv": argv, "cwd": str(output), "exit_code": result.returncode, "elapsed_seconds": time.monotonic() - start}
        (output / (name + "-command.json")).write_text(json.dumps(row, indent=2) + "\n")
        results.append(row)
        source.require(result.returncode == 0, name + " failed; retained evidence: " + str(output))
        proof = json.loads((output / (name + "-network.json")).read_text())
        source.require(proof["status"] == "completed" and proof["command_exit_code"] == 0, "network proof failed")
    # JSON parse rejects diagnostics before the result even if an engine exited zero.
    wasm = json.loads((output / "wasm-probe.log").read_text())
    source.require(wasm["status"] == "passed" and set(index["bindings"]) <= set(wasm["bindings"]), "WASM source binding probe failed")
    text = (output / "native-tests.log").read_text()
    source.require("Finished running 6 tests." in text and "100% tests passed" in text, "native test inventory changed")
    source.verify_package_assets(frontend, npm)
    for row in json.loads((stage / "stage-manifest.json").read_text()):
        source.verified_file(stage, row)
    for row in frozen_tooling:
        source.verified_file(scripts, row)
    expected = {row["path"] for row in source_inputs}
    actual = set()
    for root in (output / "source", output / "dependencies"):
        for path in root.rglob("*"):
            source.require(not path.is_symlink(), "symlink introduced into extracted source")
            if path.is_file():
                actual.add(path.relative_to(output).as_posix())
    source.require(actual == expected, "extracted source membership changed")
    for row in source_inputs:
        source.verified_file(output, row)
    used = set()
    for path in build.rglob("*.o.d"):
        for name in re.findall(r"/[^\s\\]+", path.read_text()):
            p = Path(name)
            if p.is_relative_to(output / "dependencies"):
                used.add(p.relative_to(output / "dependencies").as_posix())
    (output / "selected-native-headers.json").write_text(json.dumps(sorted(used), indent=2) + "\n")
    artifact_paths = [build / "web-ifc", build / "web-ifc-test", build / "compile_commands.json",
                      output / "selected-native-headers.json", output / "source-input-manifest.json", *sorted(scripts.iterdir())]
    artifact_paths += sorted(output.glob("*.log")) + sorted(output.glob("*-command.json")) + sorted(output.glob("*-network.json"))
    receipt = {"status": "passed", "source_stage_success_sha256": source.digest((stage / "success.json").read_bytes()),
               "source_revision": index["source_revision"], "native_tests": 6, "wasm_geometry_probe": wasm,
               "source_integrity": {"verified_files": len(source_inputs), "allowed_mutation": "Historical CMake fuzzy src/ to fuzzy/ directory rename only; all file bytes unchanged"},
               "commands": results, "files": [source.file_record(p, output) for p in artifact_paths],
               "limits": ["Native C++ compiles parser/geometry, not Emscripten-only web-ifc-api.cpp.",
                          "Unchanged Node WASM geometry probe is not browser/MT or byte-identical source-WASM rebuild acceptance."]}
    (output / "success.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "passed", "native_tests": 6, "wasm_triangles": wasm["triangles"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-stage", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frontend-package", required=True, type=Path)
    parser.add_argument("--node", required=True, type=Path)
    args = parser.parse_args()
    run(args.source_stage, args.output, args.frontend_package, args.node)

#!/usr/bin/env python3
"""Build retained libxml2 with its HTTP ABI for the selected SpatiaLite runtime.

This builds source unchanged into a fresh prefix; HTTP support restores symbols,
while build and ABI probes keep the existing offline syscall restrictions.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import common
from common import environment, inventory, require, run, save, sha, tools_record, verify_inventory, verify_selected


def build(custody, native, spatial, support, output, jobs):
    require(1 <= jobs <= 6, "Parallelism must be 1..6")
    require(not output.exists() and not output.is_symlink(), "Fresh output required")
    authority = verify_selected(native, spatial, support)
    manifest = common.PLATFORM / "build-support/postgis/inputs.json"
    item = next(x for x in json.loads(manifest.read_text())["inputs"] if x["name"] == "libxml2")
    require(item["version"] == "2.14.6", "Unexpected libxml2 source version")
    helpers = {
        "xml_profile.py": Path(__file__).resolve(),
        "common.py": Path(common.__file__).resolve(),
        "postgis_acquisition.py": common.PLATFORM / "build-support/postgis/acquisition.py",
        "offline_exec.py": common.PLATFORM / "build-support/postgis/offline_exec.py",
    }
    output.mkdir(parents=True)
    try:
        recipe = output / "recipe"
        recipe.mkdir()
        script_records = {}
        for name, source in helpers.items():
            shutil.copyfile(source, recipe / name)
            script_records[name] = {"source": str(source), "sha256": sha(recipe / name)}
        extraction_spec = importlib.util.spec_from_file_location("xml_profile_extraction", recipe / "postgis_acquisition.py")
        extraction = importlib.util.module_from_spec(extraction_spec)
        extraction_spec.loader.exec_module(extraction)
        baselines = {"native": inventory(native), "spatial": inventory(spatial), "support": inventory(support)}
        env = environment(output, native)
        save(output / "recipe.json", {"state": "xml-profile-building", "input": item,
             "native_inputs_manifest": {"path": str(manifest), "sha256": sha(manifest)},
             "authority": authority, "scripts": script_records, "tools": tools_record(env),
             "reason": "Selected SpatiaLite requires xmlNanoHTTPCleanup, omitted by the previous libxml2 HTTP-OFF build.",
             "source_changes": [], "global_installation": False,
             "network_policy": "Existing offline_exec restrictions apply to configure, compilation, install and every ABI probe; enabling the library API does not waive runtime network controls."})
        source = extraction.extract_input(custody, output / "sources", item)
        source_rows = inventory(source)
        save(output / "source-manifest.json", {"source": str(source), "archive_sha256": item["sha256"], "files": source_rows})
        prefix, builddir = output / "prefix", output / "build"
        flags = ["-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_C_FLAGS_RELEASE=-O1 -DNDEBUG",
                 "-DCMAKE_C_COMPILER=/usr/bin/gcc-15", "-DCMAKE_CXX_COMPILER=/usr/bin/g++-15",
                 "-DCMAKE_INSTALL_LIBDIR=lib", f"-DCMAKE_INSTALL_PREFIX={prefix}",
                 f"-DCMAKE_PREFIX_PATH={native}", f"-DCMAKE_INSTALL_RPATH={prefix}/lib;{native}/lib",
                 "-DBUILD_SHARED_LIBS=ON", "-DLIBXML2_WITH_HTTP=ON", "-DLIBXML2_WITH_PYTHON=OFF",
                 "-DLIBXML2_WITH_LZMA=OFF", "-DLIBXML2_WITH_ICONV=OFF", "-DLIBXML2_WITH_ZLIB=ON",
                 "-DLIBXML2_WITH_TESTS=OFF", "-DLIBXML2_WITH_PROGRAMS=ON",
                 f"-DZLIB_INCLUDE_DIR={native}/include", f"-DZLIB_LIBRARY_RELEASE={native}/lib/libz.so",
                 "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF", "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF"]
        run(["cmake", "-S", source, "-B", builddir, *flags], output, env, output, "configure")
        cache = (builddir / "CMakeCache.txt").read_text()
        for option, value in {"LIBXML2_WITH_HTTP": "ON", "LIBXML2_WITH_PYTHON": "OFF", "LIBXML2_WITH_LZMA": "OFF", "LIBXML2_WITH_ICONV": "OFF", "LIBXML2_WITH_ZLIB": "ON"}.items():
            require(f"{option}:BOOL={value}" in cache, "Unexpected effective option: " + option)
        run(["cmake", "--build", builddir, "--parallel", str(jobs)], output, env, output, "compile")
        run(["cmake", "--install", builddir], output, env, output, "stage")
        env = environment(output, native, support=support, spatial=spatial)
        env["LD_LIBRARY_PATH"] = str(prefix / "lib") + ":" + env["LD_LIBRARY_PATH"]
        run(["nm", "-D", "--defined-only", prefix / "lib/libxml2.so"], output, env, output, "symbols")
        require("xmlNanoHTTPCleanup" in (output / "symbols.log").read_text(), "Required HTTP ABI missing")
        probe = output / "abi_probe.py"
        probe.write_text(ABI_PROBE)
        run([sys.executable, "-B", probe, prefix, spatial, support, native], output, env, output, "spatialite-abi")
        result = json.loads((output / "spatialite-abi.log").read_text())
        require(result["http_symbol"] and result["spatialite_version"] == "5.1.0", "SpatiaLite ABI probe failed")
        for name, path in {"native": native, "spatial": spatial, "support": support}.items():
            verify_inventory(path, baselines[name])
        verify_inventory(source, source_rows)
        for name, path in helpers.items():
            require(sha(path) == script_records[name]["sha256"], "Recipe/helper changed during production: " + name)
        save(output / "output-manifest.json", {"prefix": str(prefix), "files": inventory(prefix)})
        save(output / "success.json", {"state": "xml-profile-built", "manifest_sha256": sha(output / "output-manifest.json"),
             "recipe_sha256": sha(output / "recipe.json"), "source_manifest_sha256": sha(output / "source-manifest.json"),
             "abi_probe_sha256": sha(probe), "abi_result_sha256": sha(output / "spatialite-abi.log"),
             "http_symbol": True, "spatialite_rtld_now": True,
             "test_scope": "Restored symbol and complete SpatiaLite RTLD_NOW binding; QGIS/provider product tests remain separate."})
    except Exception as exc:
        save(output / "failure.json", {"type": type(exc).__name__, "message": str(exc)})
        raise


ABI_PROBE = r'''import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
xml, spatial, support, native = map(Path, sys.argv[1:])
mode = os.RTLD_NOW | os.RTLD_GLOBAL
libxml = ctypes.CDLL(str(xml / "lib/libxml2.so"), mode=mode)
assert hasattr(libxml, "xmlNanoHTTPCleanup")
lib = ctypes.CDLL(str(support / "usr/lib64/libspatialite.so"), mode=mode)
lib.spatialite_version.restype = ctypes.c_char_p
version = lib.spatialite_version().decode()
paths = sorted({line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines() if "/" in line and any(token in line for token in ("libxml2.so", "libspatialite.so", "libsqlite3.so", "libproj.so", "libgeos_c.so", "libgeos.so", "libz.so"))})
expected = {"libxml2.so": xml / "lib", "libspatialite.so": support / "usr/lib64", "libsqlite3.so": spatial / "lib", "libproj.so": spatial / "lib", "libgeos_c.so": native / "lib", "libgeos.so": native / "lib", "libz.so": native / "lib"}
for token, directory in expected.items():
    found = [Path(p) for p in paths if token in Path(p).name]
    assert found and all(p.is_relative_to(directory) for p in found), (token, found, directory)
rows = []
for path in paths:
    p = Path(path)
    with p.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    rows.append({"path": path, "sha256": digest})
print(json.dumps({"http_symbol": True, "spatialite_version": version, "loaded_origins": rows}, indent=2))
'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("custody", "native", "spatial", "support", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    build(*(getattr(args, name).resolve() for name in ("custody", "native", "spatial", "support", "output")), args.jobs)

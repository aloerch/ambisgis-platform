#!/usr/bin/env python3
"""Run owned frontend lint/native assertions; retain logs and exact suite selection."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

FRAMEWORK_TESTS = (
    "utils/__tests__/ConfigUtils-test.js",
    "utils/__tests__/SecurityUtils-test.js",
    "utils/__tests__/ResourcesUtils-test.js",
    "utils/__tests__/WMSUtils-test.js",
    "utils/__tests__/WFSLayerUtils-test.js",
    "actions/__tests__/security-test.js",
    "reducers/__tests__/security-test.js",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_inventory(client: Path) -> dict[str, str]:
    return {
        str(path.relative_to(client)): digest(path)
        for path in sorted((client / "js").rglob("*"))
        if path.is_file()
    }


def run(command: list[str], client: Path, env: dict[str, str],
        output: Path, timeout: int) -> dict:
    started = time.monotonic()
    timed_out = False
    with output.open("w") as log:
        process = subprocess.Popen(command, cwd=client, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            returncode = process.returncode
    return {"command": command, "exit_code": returncode, "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "log": str(output), "log_sha256": digest(output)}


def junit_counts(path: Path) -> dict:
    if not path.is_file():
        return {"available": False}
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    return {"available": True, "cases": len(cases),
            "failures": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
            "sha256": digest(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--chrome", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suites", nargs="+", choices=("lint", "client", "framework"),
                        default=["lint", "client", "framework"])
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--port", type=int, default=19876)
    args = parser.parse_args()
    client, node, chrome, output = (
        value.resolve(strict=True) for value in (args.client, args.node, args.chrome, args.output.parent)
    )
    output = output / args.output.name
    output.mkdir(exist_ok=False)
    for executable in (node, chrome):
        if not os.access(executable, os.X_OK):
            parser.error(f"Not executable: {executable}")
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:4])
    before = source_inventory(client)
    framework = (client / "node_modules/mapstore/web/client").resolve(strict=True)
    env = os.environ.copy()
    env["PATH"] = str(node.parent) + os.pathsep + str(client / "node_modules/.bin") + os.pathsep + env.get("PATH", "")
    env["CHROME_BIN"] = str(chrome)
    env["AMBISGIS_NATIVE_CLIENT"] = str(client)
    env["AMBISGIS_NATIVE_PORT"] = str(args.port)
    env["BABEL_ENV"] = "test"
    # Deliberately do not add browser flags that disable sandbox or web security.
    config = Path(__file__).with_name("native-karma.cjs").resolve()
    results = {"schema_version": 1, "scope": "bounded native frontend checks",
               "client": str(client), "node": str(node), "node_sha256": digest(node),
               "chrome": str(chrome), "chrome_sha256": digest(chrome),
               "sandbox_disabled": False,
               "network_denial_claimed": False,
               "native_config": str(config), "native_config_sha256": digest(config),
               "checks": {}, "framework_selection": list(FRAMEWORK_TESTS)}
    for suite in args.suites:
        suite_dir = output / suite
        suite_dir.mkdir()
        if suite == "lint":
            command = [str(node), str(client / "node_modules/eslint/bin/eslint.js"),
                       "js", "--ext", ".jsx,.js"]
            result = run(command, client, env, suite_dir / "run.log", args.timeout)
            result["passed"] = result["exit_code"] == 0 and not result["timed_out"]
        else:
            selected = (sorted(p for p in (client / "js").rglob("*")
                               if p.is_file() and p.name.endswith(("-test.js", "-test.jsx")))
                        if suite == "client" else [framework / name for name in FRAMEWORK_TESTS])
            if not selected or any(not path.is_file() for path in selected):
                raise RuntimeError(f"Missing native tests for {suite}")
            (suite_dir / "entry.js").write_text(
                "\n".join(f"require({json.dumps(str(path))});" for path in selected) + "\n")
            env["AMBISGIS_NATIVE_OUTPUT"] = str(suite_dir)
            result = run([str(node), str(client / "node_modules/karma/bin/karma"),
                          "start", str(config), "--no-colors"],
                         client, env, suite_dir / "run.log", args.timeout)
            result["test_files"] = [{"path": str(path), "sha256": digest(path)} for path in selected]
            result["junit"] = junit_counts(suite_dir / "junit.xml")
            result["passed"] = (result["exit_code"] == 0 and not result["timed_out"]
                                and (result["junit"].get("cases", 0) - result["junit"].get("skipped", 0)) > 0
                                and result["junit"].get("failures", 0) == 0
                                and result["junit"].get("errors", 0) == 0)
        results["checks"][suite] = result
        (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    after = source_inventory(client)
    results["client_sources_unchanged"] = before == after
    results["client_source_inventory_sha256"] = hashlib.sha256(
        json.dumps(before, sort_keys=True).encode()).hexdigest()
    results["passed"] = results["client_sources_unchanged"] and all(
        result["passed"] for result in results["checks"].values())
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"results": str(output / "results.json"), "passed": results["passed"]}))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

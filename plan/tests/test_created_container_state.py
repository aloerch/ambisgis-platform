"""Inert native-inspect fixtures; no engine, services or process reads."""
import copy
import json
import unittest
from unittest.mock import patch
import test_development_installer as fixtures

runtime = fixtures.runtime
InstallError = fixtures.InstallError


class CreatedContainerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.InstallerStateTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.init()
        self.selected = runtime.Runtime(self.fixture.root)

    def created(self):
        row = self.fixture.inspection(self.selected)
        row.pop("OCIConfigPath")
        row["State"] = {"Status": "created", "Running": False, "Paused": False,
            "Dead": False, "OOMKilled": False, "Restarting": False, "Error": "", "Pid": 0, "ExitCode": 0,
            "StartedAt": "0001-01-01T00:00:00Z", "FinishedAt": "0001-01-01T00:00:00Z"}
        row["HostConfig"]["Sysctls"] = {
            "net.ipv6.conf.all.disable_ipv6": "1", "net.ipv6.conf.default.disable_ipv6": "1"}
        return row

    def test_created_intent_without_realized_file_is_verified(self):
        row = self.created()
        self.assertEqual(self.selected.container_security(row, "catalog"), "created_intent")
        row["OCIConfigPath"] = ""
        self.assertEqual(self.selected.container_security(row, "catalog"), "created_intent")

    def test_created_is_distinguished_from_stopped_and_running(self):
        row = self.created()
        def engine(*args, **kwargs):
            if args[:2] == ("container", "exists"):
                return (0 if args[-1].endswith("-catalog") else 1), b""
            if args[:2] == ("container", "inspect"):
                return 0, json.dumps([row]).encode()
            self.fail("unexpected native command")
        with patch.object(self.selected, "engine", side_effect=engine):
            value = self.selected.processes()["catalog"]
        self.assertEqual(value["process"], "created")
        self.assertEqual(value["configuration_validation"], "created_intent")

    def test_created_requires_complete_exact_sysctls(self):
        for value in (None, [], {}, {"net.ipv6.conf.all.disable_ipv6": "1"},
                      {"net.ipv6.conf.all.disable_ipv6": 1, "net.ipv6.conf.default.disable_ipv6": "1"},
                      {"net.ipv6.conf.all.disable_ipv6": "0", "net.ipv6.conf.default.disable_ipv6": "1"},
                      {"net.ipv6.conf.all.disable_ipv6": "1", "net.ipv6.conf.default.disable_ipv6": "1", "extra": "1"}):
            with self.subTest(value=value):
                row = self.created(); row["HostConfig"]["Sysctls"] = value
                with self.assertRaises(InstallError): self.selected.container_security(row, "catalog")
        row = self.created(); del row["HostConfig"]["Sysctls"]
        with self.assertRaises(InstallError): self.selected.container_security(row, "catalog")

    def test_only_exact_never_started_created_state_can_lack_oci(self):
        changes = [("Status", value) for value in ("initialized", "running", "stopped", "exited", "paused", "unknown", None)]
        changes += [("Running", True), ("Running", 0), ("Paused", True), ("Dead", True),
                    ("OOMKilled", True), ("Restarting", True), ("Error", "failed"), ("Checkpointed", True), ("Restored", True), ("Pid", 1), ("Pid", False), ("ConmonPid", 1),
                    ("ConmonPid", None), ("ExitCode", 1), ("ExitCode", False),
                    ("StartedAt", "2026-10-04T00:00:00Z"), ("FinishedAt", "2026-10-04T00:00:00Z")]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                row = self.created(); row["State"][key] = value
                with self.assertRaises(InstallError): self.selected.container_security(row, "catalog")
        for key in ("Status", "Running", "Paused", "Dead", "OOMKilled", "Restarting", "Error", "Pid", "ExitCode", "StartedAt", "FinishedAt"):
            row = self.created(); del row["State"][key]
            with self.subTest(missing=key), self.assertRaises(InstallError): self.selected.container_security(row, "catalog")

    def test_created_does_not_bypass_existing_security_checks(self):
        changes = [lambda x: x["Config"]["Env"].append("LD_PRELOAD=/tmp/other"),
                   lambda x: x["Config"].update(User="0:0"),
                   lambda x: x["Config"].update(Cmd=["catalog-init"]),
                   lambda x: x["HostConfig"].update(ReadonlyRootfs=False),
                   lambda x: x["HostConfig"].update(SecurityOpt=[]),
                   lambda x: x["HostConfig"].update(PidMode="host"),
                   lambda x: x.update(EffectiveCaps=["CAP_NET_RAW"]),
                   lambda x: x["HostConfig"].update(Tmpfs={}),
                   lambda x: x["NetworkSettings"]["Networks"].update(other={}),
                   lambda x: x["Mounts"][0].update(RW=True)]
        for change in changes:
            row = self.created(); change(row)
            with self.subTest(change=changes.index(change)), self.assertRaises((InstallError, ValueError)):
                self.selected.container_security(row, "catalog")

    def test_present_oci_never_falls_back_and_other_states_keep_file_check(self):
        for state in ("created", "initialized", "running", "stopped", "exited"):
            row = self.fixture.inspection(self.selected); row["State"]["Status"] = state
            row["HostConfig"]["Sysctls"] = self.created()["HostConfig"]["Sysctls"]
            self.assertEqual(self.selected.container_security(row, "catalog"), "realized_oci")
            row["OCIConfigPath"] = str(self.fixture.base/"missing")
            with self.subTest(state=state), self.assertRaises(InstallError): self.selected.container_security(row, "catalog")
        row = self.created(); row["OCIConfigPath"] = None
        with self.assertRaises(InstallError): self.selected.container_security(row, "catalog")


if __name__ == "__main__": unittest.main()

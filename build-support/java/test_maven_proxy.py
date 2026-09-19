#!/usr/bin/env python3
"""Acquisition safety tests with injected bytes; no public network access."""
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import Request

from maven_proxy import (AcquisitionError, FetchResult, MavenCustodyProxy,
                         REPOSITORIES, _GuardedRedirect)


PATH = "org/example/sample/1.2/sample-1.2.jar"


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ambisgis-maven-proxy-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "custody"
        self.calls = []

    def fetcher(self, url):
        self.calls.append(url)
        return FetchResult(b"retained fixture bytes", url)

    def proxy(self, **kwargs):
        return MavenCustodyProxy(self.root, fetcher=kwargs.pop("fetcher", self.fetcher), **kwargs)

    def events(self):
        return [json.loads(line) for line in (self.root / "events.jsonl").read_text().splitlines()]

    def test_acquisition_retains_bytes_identity_hash_and_reuses(self):
        proxy = self.proxy()
        first = proxy.fetch(PATH)
        self.assertEqual(first.path.read_bytes(), b"retained fixture bytes")
        self.assertEqual(first.record["sha256"], hashlib.sha256(first.path.read_bytes()).hexdigest())
        self.assertEqual(first.record["size"], first.path.stat().st_size)
        self.assertEqual(first.record["original_url"], REPOSITORIES["central"] + "/" + PATH)
        self.assertEqual(first.record["final_url"], first.record["original_url"])
        self.assertEqual(proxy.fetch(PATH), first)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual([event["event"] for event in self.events()], ["session", "acquired", "reused"])

    def test_changed_custody_bytes_fail_without_network_or_overwrite(self):
        proxy = self.proxy()
        artifact = proxy.fetch(PATH)
        artifact.path.write_bytes(b"tampered")
        with self.assertRaisesRegex(AcquisitionError, "bytes changed"):
            proxy.fetch(PATH)
        self.assertEqual(artifact.path.read_bytes(), b"tampered")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.events()[-1]["event"], "error")

    def test_changed_record_identity_is_rejected(self):
        proxy = self.proxy()
        proxy.fetch(PATH)
        record_path = self.root / "records" / "central" / (PATH + ".json")
        record = json.loads(record_path.read_text())
        record["maven_path"] = "other"
        record_path.write_text(json.dumps(record))
        with self.assertRaisesRegex(AcquisitionError, "identity mismatch"):
            proxy.fetch(PATH)
        self.assertEqual(len(self.calls), 1)

    def test_missing_retained_blob_is_not_reacquired(self):
        proxy = self.proxy()
        artifact = proxy.fetch(PATH)
        artifact.path.unlink()
        with self.assertRaisesRegex(AcquisitionError, "cannot read"):
            proxy.fetch(PATH)
        self.assertEqual(len(self.calls), 1)

    def test_traversal_queries_userinfo_and_encoded_paths_are_rejected(self):
        proxy = self.proxy()
        for path in ("../escape.jar", "/absolute.jar", "org/../escape.jar", "org/./x.jar",
                     "org//x.jar", "org/%2e%2e/x.jar", "org/%252e%252e/x.jar",
                     "org/x.jar?token=secret", "https://user:password@example.com/x.jar",
                     "org\\x.jar", "org/x.jar#fragment", "org/\x00/x.jar"):
            with self.subTest(path=path), self.assertRaises(AcquisitionError):
                proxy.fetch(path)
        self.assertEqual(self.calls, [])
        self.assertNotIn("secret", (self.root / "events.jsonl").read_text())
        self.assertNotIn("password", (self.root / "events.jsonl").read_text())

    def test_snapshot_latest_and_release_aliases_are_rejected(self):
        proxy = self.proxy()
        for version in ("1.0-SNAPSHOT", "1.0-snapshot", "LATEST", "RELEASE"):
            with self.subTest(version=version), self.assertRaises(AcquisitionError):
                proxy.fetch(f"org/example/sample/{version}/sample-{version}.pom")
        self.assertEqual(self.calls, [])

    def test_owned_binaries_and_binary_checksum_requests_are_rejected(self):
        proxy = self.proxy()
        for prefix in ("org/geotools", "org/geotools/x", "org/geowebcache", "org/geoserver"):
            for suffix in (".jar", "-sources.jar", ".war", ".jar.sha1"):
                with self.subTest(prefix=prefix, suffix=suffix), self.assertRaises(AcquisitionError):
                    proxy.fetch(f"{prefix}/sample/34.5/sample-34.5{suffix}")
        self.assertEqual(self.calls, [])

    def test_owned_pom_and_metadata_are_explicitly_classified(self):
        proxy = self.proxy()
        pom = proxy.fetch("org/geotools/gt-main/34.5/gt-main-34.5.pom")
        metadata = proxy.fetch("org/geotools/gt-main/maven-metadata.xml")
        self.assertEqual(pom.record["classification"], "upstream-pom-metadata")
        self.assertEqual(metadata.record["classification"], "mutable-discovery-metadata")

    def test_exact_geofence_exception_and_configured_reactor_block(self):
        proxy = self.proxy()
        proxy.fetch("org/geoserver/geofence/geofence-core/3.8.3/geofence-core-3.8.3.jar")
        with self.assertRaises(AcquisitionError):
            proxy.fetch("org/geoserver/geofence/geofence-core/3.8.4/geofence-core-3.8.4.jar")
        blocked = self.proxy(forbidden_gavs={"org.example:sample:1.2"})
        with self.assertRaises(AcquisitionError):
            blocked.fetch(PATH)
        allowed = self.proxy(forbidden_gavs={"org.example:sample:2.0"})
        allowed.fetch(PATH)

    def test_metadata_first_response_is_frozen_and_offline_replays(self):
        path = "org/example/sample/maven-metadata.xml"
        proxy = self.proxy()
        retained = proxy.fetch(path)
        offline = self.proxy(offline=True, fetcher=lambda url: self.fail("offline attempted network"))
        self.assertEqual(offline.fetch(path), retained)
        with self.assertRaises(AcquisitionError) as caught:
            offline.fetch(PATH)
        self.assertEqual(caught.exception.status, 404)
        self.assertTrue(any(event["event"] == "offline-missing" for event in self.events()))

    def test_missing_central_falls_back_and_retains_error(self):
        def fetch(url):
            if url.startswith(REPOSITORIES["central"]):
                raise AcquisitionError("upstream returned HTTP 404", 404)
            return FetchResult(b"osgeo", url)
        artifact = self.proxy(fetcher=fetch).fetch(PATH)
        self.assertEqual(artifact.record["repository"], "osgeo")
        self.assertEqual(self.events()[1]["status"], 404)
        self.assertEqual(self.events()[1]["original_url"], REPOSITORIES["central"] + "/" + PATH)
        offline = self.proxy(offline=True, fetcher=lambda url: self.fail("offline network"))
        self.assertEqual(offline.fetch(PATH), artifact)

    def test_non404_errors_do_not_fall_back(self):
        def fetch(url):
            self.calls.append(url)
            raise AcquisitionError("upstream returned HTTP 503", 503)
        with self.assertRaises(AcquisitionError):
            self.proxy(fetcher=fetch).fetch(PATH)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.events()[-1]["status"], 503)

    def test_non_loopback_and_unapproved_repository_are_rejected(self):
        for host in ("0.0.0.0", "::", "example.org", "localhost"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                self.proxy(host=host)
        for url in ("http://repo.maven.apache.org/maven2", "https://example.org/repository",
                    "https://user:secret@repo.maven.apache.org/maven2",
                    "https://repo.osgeo.org/repository/snapshot"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.proxy(repositories={"other": url})
        self.assertFalse(self.root.exists())

    def test_symlink_root_and_parent_are_rejected(self):
        target = Path(self.tmp.name) / "target"
        target.mkdir()
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaises(AcquisitionError):
            self.proxy()
        self.assertEqual(list(target.iterdir()), [])

    def test_symlink_blob_record_and_event_are_rejected(self):
        proxy = self.proxy()
        artifact = proxy.fetch(PATH)
        outside = Path(self.tmp.name) / "outside"
        outside.write_bytes(b"outside unchanged")
        for path in (artifact.path, self.root / "records" / "central" / (PATH + ".json"),
                     self.root / "events.jsonl"):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.unlink()
                path.symlink_to(outside)
                with self.assertRaises(AcquisitionError):
                    proxy.fetch(PATH)
                self.assertEqual(outside.read_bytes(), b"outside unchanged")
                path.unlink()
                path.write_bytes(original)

    def test_external_and_snapshot_redirects_rejected_before_following(self):
        proxy = self.proxy()
        handler = _GuardedRedirect(proxy._url)
        request = Request(REPOSITORIES["central"] + "/" + PATH)
        for url in ("https://evil.example/x.jar", "http://repo.maven.apache.org/maven2/x.jar",
                    "https://repo.maven.apache.org/maven2/../private/x.jar",
                    "https://repo.maven.apache.org/maven2/x.jar?token=secret",
                    "https://user:secret@repo.maven.apache.org/maven2/x.jar",
                    "https://repo.osgeo.org/repository/snapshot/x.jar"):
            with self.subTest(url=url), self.assertRaises(AcquisitionError):
                handler.redirect_request(request, None, 302, "Found", {}, url)

    def test_fetcher_final_url_cannot_bypass_redirect_policy(self):
        proxy = self.proxy(fetcher=lambda url: FetchResult(b"bad", "https://evil.example/x.jar"))
        with self.assertRaises(AcquisitionError):
            proxy.fetch(PATH)
        self.assertEqual(list((self.root / "blobs" / "sha256").iterdir()), [])

    def test_oversized_artifact_is_not_retained(self):
        proxy = self.proxy(max_bytes=2)
        with self.assertRaises(AcquisitionError):
            proxy.fetch(PATH)
        self.assertEqual(list((self.root / "blobs" / "sha256").iterdir()), [])

    def test_http_get_head_and_shutdown(self):
        with self.proxy() as proxy:
            host = proxy.base_url.split("//")[1].rstrip("/")
            connection = http.client.HTTPConnection(host)
            connection.request("HEAD", "/all/" + PATH)
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"")
            self.assertEqual(int(response.getheader("Content-Length")), len(b"retained fixture bytes"))
            connection.close()
            connection = http.client.HTTPConnection(host)
            connection.request("GET", "/all/" + PATH)
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"retained fixture bytes")
            connection.close()
            self.assertEqual(len(self.calls), 1)
            server_thread = proxy._thread
        self.assertFalse(server_thread.is_alive())
        with self.assertRaises(RuntimeError):
            _ = proxy.base_url

    def test_http_upload_credentials_and_host_are_rejected(self):
        with self.proxy() as proxy:
            host = proxy.base_url.split("//")[1].rstrip("/")
            for method, headers, expected in (("PUT", {}, 405), ("POST", {}, 405),
                                             ("GET", {"Authorization": "secret"}, 403),
                                             ("GET", {"Host": "evil.example"}, 403)):
                with self.subTest(method=method, headers=headers):
                    connection = http.client.HTTPConnection(host)
                    connection.request(method, "/all/" + PATH, headers=headers)
                    response = connection.getresponse()
                    self.assertEqual(response.status, expected)
                    response.read()
                    connection.close()
        self.assertEqual(self.calls, [])
        self.assertNotIn("secret", (self.root / "events.jsonl").read_text())


if __name__ == "__main__":
    unittest.main()

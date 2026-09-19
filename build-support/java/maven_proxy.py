#!/usr/bin/env python3
"""Retain Maven inputs before serving them to a task-local resolver.

This is an acquisition aid, not a source-build claim or a production repository.
Use ``with MavenCustodyProxy(root) as proxy`` and Maven's ``mirrorOf=*`` with
``proxy.base_url + 'all/'``. ``fetch(path)`` also supports explicit classifiers.
The first retained response freezes each repository/path, including discovery
metadata. ``offline=True`` forbids upstream access and replays verified bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import stat
import threading
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


REPOSITORIES = {
    "central": "https://repo.maven.apache.org/maven2",
    "osgeo": "https://repo.osgeo.org/repository/release",
}
_SEGMENT = re.compile(r"[A-Za-z0-9_.+~-]+\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MAX_BYTES = 1024 * 1024 * 1024


class AcquisitionError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class FetchResult:
    data: bytes
    final_url: str
    status: int = 200
    content_type: str = "application/octet-stream"


@dataclass(frozen=True)
class RetainedArtifact:
    path: Path
    record: dict


class _GuardedRedirect(HTTPRedirectHandler):
    def __init__(self, validate: Callable[[str], None]):
        self.validate = validate

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class MavenCustodyProxy:
    """A loopback-only GET/HEAD proxy with immutable, checked acquisition custody.

    ``forbidden_gavs`` is an optional iterable of ``group:artifact:version``;
    those exact reactor coordinates are blocked in addition to owned namespaces.
    POMs and discovery metadata are allowed and explicitly classified. The only
    default owned-namespace binary exception is Class B GeoFence version 3.8.3.
    ``fetcher`` is an injectable offline fixture; production uses guarded HTTPS.
    """

    def __init__(self, custody: Path | str, repositories: Mapping[str, str] | None = None,
                 forbidden_gavs=None, offline: bool = False, host: str = "127.0.0.1",
                 fetcher: Callable[[str], FetchResult] | None = None,
                 max_bytes: int = _MAX_BYTES, timeout: float = 90):
        if host != "127.0.0.1":
            raise ValueError("custody proxy must bind to 127.0.0.1")
        self.root = Path(os.path.abspath(custody))
        self.repositories = dict(REPOSITORIES if repositories is None else repositories)
        if not self.repositories:
            raise ValueError("at least one approved repository is required")
        for key, base in self.repositories.items():
            if not _SEGMENT.fullmatch(key) or key in {".", "..", "all"}:
                raise ValueError("invalid repository name")
            if base not in REPOSITORIES.values():
                raise ValueError("repository is outside the approved HTTPS release bases")
        self.forbidden_gavs = set(forbidden_gavs or ())
        for gav in self.forbidden_gavs:
            if len(gav.split(":")) != 3 or any(not part for part in gav.split(":")):
                raise ValueError("forbidden GAV must be group:artifact:version")
        if max_bytes <= 0 or timeout <= 0:
            raise ValueError("acquisition bounds must be positive")
        self.offline, self.host = offline, host
        self.max_bytes, self.timeout = max_bytes, timeout
        self._fetcher = fetcher or self._download
        self._lock = threading.RLock()
        self._server = None
        self._thread = None
        self._directory(self.root)
        self._directory(self.root / "blobs" / "sha256")
        self._directory(self.root / "records")
        self._event("session", offline=offline, repositories=self.repositories,
                    forbidden_gavs=sorted(self.forbidden_gavs),
                    metadata_policy="first response frozen; discovery does not establish a fixed version lock")

    @staticmethod
    def _directory(path: Path) -> None:
        """Create directories without following existing symlink components."""
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            try:
                current.mkdir()
            except FileExistsError:
                pass
            mode = current.lstat().st_mode
            if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
                raise AcquisitionError("custody directory is not a real directory")

    def _safe_file(self, path: Path) -> None:
        if not path.is_relative_to(self.root):
            raise AcquisitionError("custody path escapes root")
        self._directory(path.parent)
        if path.is_symlink():
            raise AcquisitionError("custody file is a symlink")
        if path.exists() and not stat.S_ISREG(path.lstat().st_mode):
            raise AcquisitionError("custody entry is not a regular file")

    def _read(self, path: Path) -> bytes:
        self._safe_file(path)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise AcquisitionError("custody entry is not a regular file")
                return stream.read()
        except OSError as exc:
            raise AcquisitionError("cannot read retained custody file") from exc

    def _write_once(self, path: Path, data: bytes) -> None:
        self._safe_file(path)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if self._read(path) != data:
                raise AcquisitionError("existing custody bytes changed; refusing overwrite")
        except OSError as exc:
            raise AcquisitionError("cannot retain acquisition bytes") from exc

    def _event(self, event: str, **fields) -> None:
        path = self.root / "events.jsonl"
        self._safe_file(path)
        record = {"event": event, "time": datetime.now(timezone.utc).isoformat(), **fields}
        encoded = (json.dumps(record, sort_keys=True) + "\n").encode()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "ab") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise AcquisitionError("cannot retain acquisition event") from exc

    def _url(self, url: str) -> None:
        try:
            parsed = urlsplit(url)
            valid = (parsed.scheme == "https" and parsed.username is None
                     and parsed.password is None and not parsed.query and not parsed.fragment
                     and parsed.port in (None, 443))
        except ValueError as exc:
            raise AcquisitionError("invalid upstream URL", 403) from exc
        if not valid or not any(url.startswith(base + "/") for base in self.repositories.values()):
            raise AcquisitionError("upstream URL is outside configured HTTPS release bases", 403)
        # Redirect destinations must obey the same path and owned-source policy.
        base = next(base for base in self.repositories.values() if url.startswith(base + "/"))
        self._request_path(url[len(base) + 1:])

    def _request_path(self, path: str) -> str:
        if not isinstance(path, str) or not path or len(path) > 4096:
            raise AcquisitionError("invalid Maven artifact path", 403)
        parts = path.split("/")
        if any(part in {"", ".", ".."} or not _SEGMENT.fullmatch(part) for part in parts):
            raise AcquisitionError("unsafe Maven artifact path", 403)
        if any("SNAPSHOT" in part.upper() or part.upper() in {"LATEST", "RELEASE"} for part in parts):
            raise AcquisitionError("moving snapshot/latest/release coordinates are forbidden", 403)
        metadata = self._classification(path) != "artifact"
        if not metadata and len(parts) >= 4:
            group, artifact, version = ".".join(parts[:-3]), parts[-3], parts[-2]
            gav = f"{group}:{artifact}:{version}"
            owned = any(path.startswith(prefix) for prefix in
                        ("org/geotools/", "org/geowebcache/", "org/geoserver/"))
            geofence = (path.startswith("org/geoserver/geofence/") and version == "3.8.3")
            if gav in self.forbidden_gavs or (owned and not geofence):
                raise AcquisitionError("owned reactor artifact must be built from retained owned source", 403)
        return path

    @staticmethod
    def _classification(path: str) -> str:
        name = path.rsplit("/", 1)[-1]
        while any(name.endswith(suffix) for suffix in (".sha1", ".sha256", ".sha512", ".md5", ".asc")):
            name = name.rsplit(".", 1)[0]
        if name == "maven-metadata.xml":
            return "mutable-discovery-metadata"
        if name.endswith(".pom"):
            return "upstream-pom-metadata"
        return "artifact"

    def _download(self, url: str) -> FetchResult:
        self._url(url)
        # Ignore ambient proxy settings and credentials. Never forward client headers.
        opener = build_opener(ProxyHandler({}), _GuardedRedirect(self._url))
        request = Request(url, headers={"User-Agent": "AmbisGIS-FND-02-custody/1",
                                        "Accept-Encoding": "identity"})
        try:
            with opener.open(request, timeout=self.timeout) as response:
                final_url = response.geturl()
                self._url(final_url)
                length = response.headers.get("Content-Length")
                if length is not None and int(length) > self.max_bytes:
                    raise AcquisitionError("upstream artifact exceeds acquisition size bound")
                data = response.read(self.max_bytes + 1)
                if len(data) > self.max_bytes:
                    raise AcquisitionError("upstream artifact exceeds acquisition size bound")
                if length is not None and len(data) != int(length):
                    raise AcquisitionError("upstream response length mismatch")
                return FetchResult(data, final_url, response.status,
                                   response.headers.get("Content-Type", "application/octet-stream"))
        except HTTPError as exc:
            exc.close()
            # Error bodies/headers can contain service internals; record only code and safe URL.
            raise AcquisitionError(f"upstream returned HTTP {exc.code}", exc.code) from exc
        except (URLError, TimeoutError, OSError, ValueError, HTTPException) as exc:
            raise AcquisitionError(f"upstream acquisition failed ({type(exc).__name__})") from exc

    def _cached(self, repository: str, path: str) -> RetainedArtifact | None:
        record_path = self.root / "records" / repository / (path + ".json")
        self._safe_file(record_path)
        if not record_path.exists():
            return None
        try:
            record = json.loads(self._read(record_path))
            digest = record["sha256"]
            if (not isinstance(digest, str) or not _HASH.fullmatch(digest)
                    or record["repository"] != repository or record["maven_path"] != path
                    or record["original_url"] != self.repositories[repository] + "/" + path
                    or record["classification"] != self._classification(path)
                    or record["status"] != 200 or type(record["size"]) is not int):
                raise AcquisitionError("retained artifact record identity mismatch")
            self._url(record["final_url"])
            blob = self.root / "blobs" / "sha256" / digest
            data = self._read(blob)
            if len(data) != record["size"] or hashlib.sha256(data).hexdigest() != digest:
                raise AcquisitionError("retained artifact bytes changed; refusing reuse")
            return RetainedArtifact(blob, record)
        except (ValueError, KeyError, TypeError) as exc:
            raise AcquisitionError("invalid retained artifact record") from exc

    def _selection(self, path: str, repository: str | None = None) -> str | None:
        selection_path = self.root / "selections" / (path + ".json")
        self._safe_file(selection_path)
        if repository is not None:
            self._write_once(selection_path, (json.dumps(
                {"maven_path": path, "repository": repository}, sort_keys=True) + "\n").encode())
        if not selection_path.exists():
            return None
        try:
            record = json.loads(self._read(selection_path))
            if record["maven_path"] != path or record["repository"] not in self.repositories:
                raise AcquisitionError("retained combined-origin selection identity mismatch")
            return record["repository"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AcquisitionError("invalid retained combined-origin selection") from exc

    def fetch(self, path: str, repository: str = "all") -> RetainedArtifact:
        """Acquire or verify/replay a relative Maven path; never overwrite custody."""
        with self._lock:
            try:
                self._request_path(path)
                if repository != "all" and repository not in self.repositories:
                    raise AcquisitionError("unknown repository", 403)
            except AcquisitionError as exc:
                # Invalid input may contain credentials; retain a digest, never the raw target.
                self._event("rejected", target_sha256=hashlib.sha256(str(path).encode()).hexdigest(),
                            status=exc.status, reason=str(exc))
                raise
            candidates = list(self.repositories) if repository == "all" else [repository]
            if repository == "all":
                try:
                    selected = self._selection(path)
                    # Pin the first successful combined-route origin. Also consult retained
                    # bytes before network if an earlier process stopped before pinning it.
                    for key in ([selected] if selected else candidates):
                        cached = self._cached(key, path)
                        if cached is not None:
                            self._selection(path, key)
                            self._event("reused", repository=key, maven_path=path,
                                        sha256=cached.record["sha256"], offline=self.offline)
                            return cached
                        if selected:
                            raise AcquisitionError("selected combined-origin custody record is missing")
                except AcquisitionError as exc:
                    self._event("error", repository="all", maven_path=path,
                                status=exc.status, reason=str(exc), offline=self.offline)
                    raise
            for key in candidates:
                url = self.repositories[key] + "/" + path
                try:
                    cached = self._cached(key, path)
                    if cached is not None:
                        self._event("reused", repository=key, maven_path=path,
                                    sha256=cached.record["sha256"], offline=self.offline)
                        return cached
                    if self.offline:
                        self._event("offline-missing", repository=key, maven_path=path,
                                    original_url=url, status=404)
                        continue
                    result = self._fetcher(url)
                    self._url(result.final_url)
                    if result.status != 200:
                        raise AcquisitionError(f"upstream returned HTTP {result.status}", result.status)
                    if not isinstance(result.data, bytes) or len(result.data) > self.max_bytes:
                        raise AcquisitionError("invalid or oversized acquisition response")
                    digest = hashlib.sha256(result.data).hexdigest()
                    blob = self.root / "blobs" / "sha256" / digest
                    self._write_once(blob, result.data)
                    record = {"schema_version": 1, "repository": key, "maven_path": path,
                              "original_url": url, "final_url": result.final_url, "status": 200,
                              "sha256": digest, "size": len(result.data),
                              "classification": self._classification(path),
                              "acquired_at": datetime.now(timezone.utc).isoformat(),
                              "license_status": "unreviewed; artifact and POM retention is not license acceptance"}
                    self._write_once(self.root / "records" / key / (path + ".json"),
                                     (json.dumps(record, indent=2, sort_keys=True) + "\n").encode())
                    self._event("acquired", **record)
                    if repository == "all":
                        self._selection(path, key)
                    return RetainedArtifact(blob, record)
                except AcquisitionError as exc:
                    self._event("error", repository=key, maven_path=path, original_url=url,
                                status=exc.status, reason=str(exc), offline=self.offline)
                    # Only confirmed absence permits falling back to another approved origin.
                    if exc.status != 404:
                        raise
            raise AcquisitionError("artifact absent from configured retained/release repositories", 404)

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("proxy context has not started")
        return f"http://127.0.0.1:{self._server.server_port}/"

    def __enter__(self):
        if self._server is not None:
            raise RuntimeError("proxy already started")
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                self._serve(False)

            def do_HEAD(self):
                self._serve(True)

            def do_POST(self):
                self._reject_method()

            do_PUT = do_POST
            do_DELETE = do_POST
            do_PATCH = do_POST
            do_CONNECT = do_POST
            do_OPTIONS = do_POST

            def _reject_method(self):
                with proxy._lock:
                    proxy._event("method-rejected", method=self.command, status=405)
                self.send_error(405, "Only artifact GET and HEAD are allowed")

            def _serve(self, head):
                try:
                    if self.headers.get("Host") != f"127.0.0.1:{proxy._server.server_port}":
                        raise AcquisitionError("unexpected loopback Host", 403)
                    if self.headers.get("Authorization") or self.headers.get("Proxy-Authorization"):
                        raise AcquisitionError("client credentials are forbidden", 403)
                    if not self.path.startswith("/"):
                        raise AcquisitionError("absolute proxy targets are forbidden", 403)
                    repository, sep, path = self.path[1:].partition("/")
                    if not sep:
                        raise AcquisitionError("repository/path required", 403)
                    artifact = proxy.fetch(path, repository)
                    data = proxy._read(artifact.path)
                    if (len(data) != artifact.record["size"]
                            or hashlib.sha256(data).hexdigest() != artifact.record["sha256"]):
                        raise AcquisitionError("custody changed before HTTP response")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(artifact.record["size"]))
                    self.end_headers()
                    if not head:
                        # Hold no mutable Maven repository data: serve retained immutable bytes.
                        self.wfile.write(data)
                except AcquisitionError as exc:
                    with proxy._lock:
                        proxy._event("http-error", status=exc.status, reason=str(exc))
                    self.send_error(exc.status, "Custody acquisition refused; inspect task evidence")
                except (BrokenPipeError, ConnectionResetError):
                    with proxy._lock:
                        proxy._event("client-disconnected")

        self._server = ThreadingHTTPServer((self.host, 0), Handler)
        self._server.daemon_threads = False
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
        self._server = self._thread = None
        self._event("session-closed", offline=self.offline)

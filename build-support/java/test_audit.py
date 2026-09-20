"""Meaningful static-audit safety tests; these are not GIS/Maven build tests."""
import base64
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("java_audit", Path(__file__).with_name("audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

POM = b'''<project xmlns="http://maven.apache.org/POM/4.0.0">
 <modelVersion>4.0.0</modelVersion>
 <parent><groupId>example</groupId><artifactId>parent</artifactId><version>4.0</version><relativePath/></parent>
 <artifactId>child</artifactId>
 <properties><render.version>2.0-SNAPSHOT</render.version><alias>${render.version}</alias></properties>
 <modules><module>web</module></modules>
 <dependencyManagement><dependencies>
  <dependency><groupId>example</groupId><artifactId>bom</artifactId><version>[1.0,2.0)</version><type>pom</type><scope>import</scope></dependency>
 </dependencies></dependencyManagement>
 <dependencies><dependency><groupId>example</groupId><artifactId>render</artifactId><version>${alias}</version><classifier>tests</classifier><type>test-jar</type><scope>test</scope><optional>true</optional><exclusions><exclusion><groupId>bad</groupId><artifactId>excluded</artifactId></exclusion></exclusions></dependency></dependencies>
 <build><extensions><extension><groupId>example</groupId><artifactId>extension</artifactId><version>RELEASE</version></extension></extensions>
 <pluginManagement><plugins><plugin><groupId>example</groupId><artifactId>codegen</artifactId><version>1.0</version><executions><execution><id>rewrite</id><phase>validate</phase><goals><goal>apply</goal></goals><configuration><mode>mutable</mode></configuration></execution></executions><dependencies><dependency><groupId>example</groupId><artifactId>helper</artifactId><version>LATEST</version></dependency></dependencies></plugin></plugins></pluginManagement></build>
 <repositories><repository><id>custom</id><url>https://example.invalid/maven</url><releases><enabled>false</enabled><checksumPolicy>fail</checksumPolicy></releases><snapshots><enabled>true</enabled><updatePolicy>always</updatePolicy></snapshots></repository></repositories>
 <pluginRepositories><pluginRepository><id>plugins</id><url>https://example.invalid/plugins</url></pluginRepository></pluginRepositories>
 <distributionManagement><repository><id>donor-releases</id><url>https://example.invalid/donor/releases</url></repository><snapshotRepository><id>donor-snapshots</id><url>https://example.invalid/donor/snapshots</url></snapshotRepository><site><id>docs</id><url>scp://example.invalid/docs</url></site></distributionManagement>
 <profiles><profile><id>optional</id><distributionManagement><repository><id>alternate</id><url>https://example.invalid/alternate</url></repository></distributionManagement><activation><activeByDefault>true</activeByDefault><jdk>[17,)</jdk><property><name>!skip</name></property></activation><properties><render.version>3.0</render.version></properties><modules><module>extra</module></modules><dependencies><dependency><groupId>example</groupId><artifactId>profile-only</artifactId><version>${render.version}</version></dependency></dependencies></profile></profiles>
</project>'''


def value(tree, name):
    matches = [child for child in tree.get("children", []) if audit.local_name(child["name"]) == name]
    return matches[0] if matches else None


class DeclarationTests(unittest.TestCase):
    def setUp(self):
        self.record = audit.parse_pom(POM, "pom.xml")

    def test_inheritance_and_profiles_remain_unresolved(self):
        self.assertEqual(self.record["project"], {"artifactId": "child"})
        self.assertEqual(self.record["parent"]["relativePath"], "")
        self.assertEqual(self.record["parent"]["version"], "4.0")
        versions = [p["value"] for p in self.record["properties"] if p["name"] == "render.version"]
        self.assertEqual(versions, ["2.0-SNAPSHOT", "3.0"])
        self.assertEqual([m["value"] for m in self.record["modules"]], ["web", "extra"])
        self.assertEqual(value(self.record["profiles"][0]["activation"], "jdk")["text"], "[17,)")
        self.assertIn("/profiles[1]/profile[1]/", self.record["properties"][-1]["xml_path"])
        references = [f for f in self.record["findings"] if f["value"] == "${alias}"]
        self.assertEqual(references[0]["symbols"], ["alias"])

    def test_management_plugin_and_profile_contexts_and_policies_preserved(self):
        dependencies = self.record["dependencies"]
        self.assertEqual(len(dependencies), 4)
        self.assertIn("/dependencyManagement[1]/", dependencies[0]["xml_path"])
        self.assertEqual(value(dependencies[0]["declaration"], "scope")["text"], "import")
        normal = dependencies[1]["declaration"]
        self.assertEqual(value(normal, "classifier")["text"], "tests")
        self.assertEqual(value(normal, "type")["text"], "test-jar")
        self.assertIsNotNone(value(normal, "exclusions"))
        self.assertIn("/pluginManagement[1]/plugins[1]/plugin[1]/", dependencies[2]["xml_path"])
        self.assertIn("/profiles[1]/profile[1]/", dependencies[3]["xml_path"])
        plugin = self.record["plugins"][0]["declaration"]
        execution = value(value(plugin, "executions"), "execution")
        self.assertEqual(value(execution, "phase")["text"], "validate")
        self.assertEqual(value(value(execution, "goals"), "goal")["text"], "apply")
        repository = self.record["repositories"][0]["declaration"]
        self.assertEqual(value(value(repository, "releases"), "enabled")["text"], "false")
        self.assertEqual(value(value(repository, "snapshots"), "updatePolicy")["text"], "always")
        self.assertIn("pluginRepositories", self.record["repositories"][1]["xml_path"])
        self.assertEqual(len(self.record["extensions"]), 1)

    def test_deployment_targets_preserved_without_selection_or_execution(self):
        destinations = self.record["distribution_management"]
        self.assertEqual(len(destinations), 2)
        self.assertEqual(destinations[0]["xml_path"], "/project[1]/distributionManagement[1]")
        main = destinations[0]["declaration"]
        self.assertEqual(value(value(main, "repository"), "id")["text"], "donor-releases")
        self.assertEqual(value(value(main, "snapshotRepository"), "url")["text"], "https://example.invalid/donor/snapshots")
        self.assertEqual(value(value(main, "site"), "url")["text"], "scp://example.invalid/docs")
        self.assertIn("/profiles[1]/profile[1]/", destinations[1]["xml_path"])
        self.assertEqual(value(value(destinations[1]["declaration"], "repository"), "id")["text"], "alternate")

    def test_snapshot_indirection_and_ranges_are_findings_not_resolutions(self):
        observed = {(f["kind"], f["value"]) for f in self.record["findings"]}
        self.assertIn(("snapshot_literal", "2.0-SNAPSHOT"), observed)
        self.assertIn(("unevaluated_expression", "${render.version}"), observed)
        self.assertIn(("version_range_candidate", "[1.0,2.0)"), observed)
        self.assertIn(("floating_version_literal", "LATEST"), observed)
        self.assertIn(("floating_version_literal", "RELEASE"), observed)
        normal = self.record["dependencies"][1]["declaration"]
        self.assertEqual(value(normal, "version")["text"], "${alias}")

    def test_malformed_and_entity_input_fail_without_repair(self):
        for payload in (b"<project><broken></project>", b'<project txsi:schemaLocation="x"/>',
                        b'<!DOCTYPE project [<!ENTITY x "bad">]><project>&x;</project>',
                        '<!DOCTYPE project><project/>'.encode('utf-16'), b'<unrelated/>'):
            with self.subTest(payload=payload), self.assertRaises(audit.AuditError):
                audit.parse_pom(payload, "broken/pom.xml")


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.name = "ambisgis-geotools"
        self.repo = self.root / self.name
        self.repo.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.name", "Synthetic test")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("remote", "add", "origin", f"https://github.com/aloerch/{self.name}.git")
        (self.repo / "pom.xml").write_bytes(POM)
        config = self.repo / ".mvn"
        config.mkdir()
        (config / "jvm.config").write_text("-Xmx2g\n")
        (config / "extensions.xml").write_text("<extensions><extension><groupId>x</groupId><artifactId>y</artifactId><version>1.0</version></extension></extensions>")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "synthetic fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()
        self.git("tag", "fixture")
        self.pin = (self.name, "fixture", self.commit)

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.repo), *args], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout

    def test_pinned_objects_ignore_dirty_checkout_and_are_deterministic(self):
        first = audit.create_inventory(self.root, [self.pin])
        (self.repo / "pom.xml").write_text("malformed dirty checkout")
        (self.repo / "untracked").mkdir()
        (self.repo / "untracked/pom.xml").write_text("untracked")
        second = audit.create_inventory(self.root, [self.pin])
        self.assertEqual(first, second)
        source = first["sources"][0]
        self.assertEqual(len(source["poms"]), 1)
        self.assertEqual(source["poms"][0]["sha256"], hashlib.sha256(POM).hexdigest())
        self.assertEqual(len(source["maven_configs"]), 2)
        self.assertFalse(first["effective_poms_resolved"])
        self.assertFalse(first["transitive_closure_resolved"])
        self.assertTrue(first["xml_interpretation_complete"])

    def test_wrong_owned_origin_rejected(self):
        self.git("remote", "set-url", "origin", "https://github.com/unrelated/geotools.git")
        with self.assertRaisesRegex(audit.AuditError, "origin identity mismatch"):
            audit.create_inventory(self.root, [self.pin])

    def test_multiple_origin_urls_rejected(self):
        self.git("config", "--add", "remote.origin.url", "https://example.invalid/extra")
        with self.assertRaisesRegex(audit.AuditError, "origin identity mismatch"):
            audit.create_inventory(self.root, [self.pin])

    def test_wrong_push_origin_rejected(self):
        self.git("remote", "set-url", "--push", "origin", "https://example.invalid/extra")
        with self.assertRaisesRegex(audit.AuditError, "origin identity mismatch"):
            audit.create_inventory(self.root, [self.pin])

    def test_moved_tag_rejected(self):
        (self.repo / "extra").write_text("second commit")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "new commit")
        self.git("tag", "--force", "fixture")
        with self.assertRaisesRegex(audit.AuditError, "tag object or commit identity mismatch"):
            audit.create_inventory(self.root, [self.pin])

    def test_different_tag_object_with_same_peeled_commit_rejected(self):
        self.git("tag", "--force", "--annotate", "fixture", "-m", "different tag object")
        self.assertEqual(self.git("rev-parse", "fixture^{commit}").strip(), self.commit)
        with self.assertRaisesRegex(audit.AuditError, "tag object or commit identity mismatch"):
            audit.create_inventory(self.root, [self.pin])

    def test_promisor_input_rejected_without_fetch(self):
        self.git("config", "remote.origin.promisor", "true")
        with self.assertRaisesRegex(audit.AuditError, "partial/promisor"):
            audit.create_inventory(self.root, [self.pin])

    def test_malformed_pom_retained_and_cli_returns_nonzero(self):
        malformed = b'<project txsi:schemaLocation="x"/>'
        (self.repo / "broken").mkdir()
        (self.repo / "broken/pom.xml").write_bytes(malformed)
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "malformed inherited fixture")
        commit = self.git("rev-parse", "HEAD").strip()
        self.git("tag", "--force", "fixture")
        actual_create = audit.create_inventory
        output = self.root / "diagnostic.json"
        # Only replace the fixed production pin set; actual Git reads, XML
        # interpretation, exclusive serialization and CLI status are exercised.
        with patch.object(audit, "create_inventory", side_effect=lambda root: actual_create(root, [(self.name, "fixture", commit)])), redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            status = audit.main(["--owned-root", str(self.root), "--output", str(output)])
        self.assertEqual(status, 1)
        inventory = json.loads(output.read_text())
        self.assertTrue(inventory["tracked_file_enumeration_complete"])
        self.assertFalse(inventory["xml_interpretation_complete"])
        poms = inventory["sources"][0]["poms"]
        self.assertEqual(len(poms), 2)
        broken = next(p for p in poms if p["source_path"] == "broken/pom.xml")
        self.assertEqual(base64.b64decode(broken["content"]), malformed)
        self.assertEqual(broken["sha256"], hashlib.sha256(malformed).hexdigest())
        self.assertIn("unbound prefix", broken["parse_error"])
        self.assertNotIn("dependencies", broken)

    def test_symlink_pom_rejected(self):
        (self.repo / "linked").mkdir()
        (self.repo / "linked/pom.xml").symlink_to("../pom.xml")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "symlink fixture")
        commit = self.git("rev-parse", "HEAD").strip()
        self.git("tag", "--force", "fixture")
        with self.assertRaisesRegex(audit.AuditError, "not a regular tracked file"):
            audit.create_inventory(self.root, [(self.name, "fixture", commit)])

    def test_output_never_overwrites_existing_file_or_symlink(self):
        output = self.root / "audit.json"
        output.write_text("previous evidence")
        with self.assertRaises(FileExistsError):
            audit.write_inventory(output, {})
        self.assertEqual(output.read_text(), "previous evidence")
        link = self.root / "linked.json"
        link.symlink_to(output)
        with self.assertRaises(FileExistsError):
            audit.write_inventory(link, {})
        with redirect_stderr(io.StringIO()):
            self.assertEqual(audit.main(["--owned-root", str(self.root / "absent"), "--output", str(output)]), 1)
        self.assertEqual(output.read_text(), "previous evidence")


if __name__ == "__main__":
    unittest.main()

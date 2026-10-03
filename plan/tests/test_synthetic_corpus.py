# SPDX-License-Identifier: GPL-3.0-or-later
import csv
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import itertools
import json
from pathlib import Path
import struct
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET

MODULE = Path(__file__).resolve().parents[1] / 'tools/synthetic_corpus.py'
spec = importlib.util.spec_from_file_location('synthetic_corpus', MODULE)
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


class SyntheticCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)

    def generate(self, name='corpus', **options):
        root = self.parent / name
        corpus.generate(root, **options)
        return root

    def test_identical_seed_has_byte_identical_complete_corpus(self):
        a, b = self.generate('a'), self.generate('b')
        left = corpus.validate_manifest(a)
        right = corpus.validate_manifest(b)
        self.assertEqual(left, right)
        self.assertEqual((a / 'manifest.json').read_bytes(), (b / 'manifest.json').read_bytes())

    def test_checked_in_small_corpus_matches_current_generator_and_native_profile(self):
        generated = self.generate()
        committed = corpus.FIXTURES / 'small'
        self.assertEqual(corpus.validate_native_profile(generated), corpus.validate_native_profile(committed))
        self.assertEqual((generated / 'manifest.json').read_bytes(), (committed / 'manifest.json').read_bytes())

    def test_seed_and_scale_preserve_namespaces_without_collisions(self):
        small = list(corpus.iter_addresses(2409, 12))
        large = list(corpus.iter_addresses(2409, 10001))
        other = list(corpus.iter_addresses(2410, 12))
        self.assertEqual(small, large[:12])
        self.assertEqual(len({row['id'] for row in large}), 10001)
        self.assertFalse({r['id'] for r in small} & {r['id'] for r in other})
        self.assertNotEqual(small[0]['geometry'], other[0]['geometry'])
        for row in large:
            self.assertEqual(uuid.UUID(row['id']).version, 5)
            self.assertEqual(row['id'], row['properties']['fid'])
        self.assertEqual([r['properties']['object_id'] for r in large], list(range(1, 10002)))

    def test_independent_first_twelve_oracle(self):
        # Expectations are committed separately and are never synthesized here.
        oracle = json.loads((corpus.FIXTURES / 'expected-small.json').read_text())['first_12']
        rows = [r['properties'] for r in corpus.iter_addresses()]
        selected = lambda predicate: [r['object_id'] for r in rows if predicate(r)]
        self.assertEqual(selected(lambda r: r['name'] is None), oracle['null_name_ids'])
        self.assertEqual(selected(lambda r: r['name'] == ''), oracle['empty_name_ids'])
        self.assertEqual(selected(lambda r: r['district'] == 'north'), oracle['north_ids'])
        self.assertEqual(selected(lambda r: r['population'] >= 60), oracle['population_at_least_60_ids'])
        self.assertEqual(sum(r['population'] for r in rows), oracle['population_sum'])
        self.assertEqual(sum(r['population'] for r in rows if r['district'] == 'north'), oracle['north_population_sum'])
        self.assertEqual(sum(Decimal(str(r['elevation'])) for r in rows), Decimal(oracle['elevation_sum']))
        sorted_rows = sorted(rows, key=lambda r: (r['name'] is None, r['name'] or '', r['object_id']))
        self.assertEqual([r['object_id'] for r in sorted_rows], oracle['sorted_name_null_last_ids'])
        for row in rows:
            actual = datetime.fromisoformat(row['observed_at'].replace('Z', '+00:00')).astimezone(timezone.utc)
            self.assertEqual(actual.isoformat(), oracle['all_timestamp_instants_utc'])

    def test_native_large_numbers_and_calendar_values_remain_text(self):
        root = self.generate()
        with (root / 'native/typed-values.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        oracle = json.loads((root / 'expected-small.json').read_text())
        self.assertEqual([r['native_large_id'] for r in rows], oracle['native_large_ids'])
        self.assertEqual([r['decimal_value'] for r in rows], oracle['native_decimal_text'])
        self.assertEqual(rows[0]['date_only'], '2024-02-29')
        self.assertEqual(rows[0]['empty_text'], '')

    def test_real_binary_raster_sample_order_and_nodata(self):
        root = self.generate()
        for band, base in [(1, 0), (2, 100), (3, 200)]:
            data = (root / f'raster/multiband-band-{band}.raw').read_bytes()
            self.assertEqual(struct.unpack('<12H', data), tuple(range(base + 1, base + 12)) + (65535,))
        text = (root / 'raster/multiband.vrt').read_text()
        self.assertEqual(text.count('relativeToVRT="1"'), 3)
        self.assertIn('EPSG:4326', text)

    def test_relationships_and_attachment_hash_bind_actual_data(self):
        root = self.generate()
        fids = {r['id'] for r in corpus.iter_addresses()}
        with (root / 'inspections.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['address_fid'] in fids for r in rows))
        reference = json.loads((root / 'attachment-references.json').read_text())[0]
        self.assertIn(reference['parent_fid'], fids)
        self.assertEqual(corpus.digest(root / reference['path']), reference['sha256'])
        with (root / 'invalid/orphan-inspection.csv').open() as stream:
            self.assertNotIn(next(csv.DictReader(stream))['address_fid'], fids)

    def test_explicit_invalid_id_cases_are_really_invalid(self):
        root = self.generate()
        for filename, field in [('duplicate-object-id', 'object_id'), ('duplicate-uuid', 'fid')]:
            rows = json.loads((root / f'invalid/{filename}.geojson').read_text())['features']
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['properties'][field], rows[1]['properties'][field])
        self.assertTrue((root / 'invalid/self-intersection.geojson').is_file())

    def test_existing_directory_and_file_not_modified(self):
        target = self.parent / 'target'
        target.mkdir()
        sentinel = target / 'keep'; sentinel.write_text('user data')
        with self.assertRaisesRegex(ValueError, 'new directory'):
            corpus.generate(target)
        self.assertEqual(sentinel.read_text(), 'user data')
        with self.assertRaises(ValueError):
            corpus.generate(sentinel)

    def test_symlink_output_and_ancestor_rejected_before_write(self):
        real = self.parent / 'real'; real.mkdir()
        link = self.parent / 'link'; link.symlink_to(real, target_is_directory=True)
        for output in (link, link / 'child'):
            with self.assertRaisesRegex(ValueError, 'symlink'):
                corpus.generate(output)
        self.assertEqual(list(real.iterdir()), [])

    def test_bad_limits_rejected_before_directory_creation(self):
        for count in (-1, 0, 11, 1000001, True, 12.0):
            with self.assertRaises(ValueError):
                corpus.generate(self.parent / 'absent', addresses=count)
        for seed in (-1, 2**32, True, 'seed'):
            with self.assertRaises(ValueError):
                corpus.generate(self.parent / 'absent', seed=seed)
        self.assertFalse((self.parent / 'absent').exists())

    def test_manifest_rejects_missing_changed_extra_and_symlink_members(self):
        root = self.generate()
        address = root / 'addresses.geojson'
        original = address.read_bytes(); address.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'content differs'):
            corpus.validate_manifest(root)
        address.write_bytes(original)
        extra = root / 'unexpected'; extra.write_text('extra')
        with self.assertRaisesRegex(ValueError, 'membership'):
            corpus.validate_manifest(root)
        extra.unlink()
        address.unlink()
        with self.assertRaisesRegex(ValueError, 'membership'):
            corpus.validate_manifest(root)
        outside = self.parent / 'outside'; outside.write_bytes(original)
        address.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            corpus.validate_manifest(root)

    def test_manifest_rejects_traversal_without_outside_read(self):
        root = self.generate()
        path = root / 'manifest.json'; manifest = json.loads(path.read_text())
        manifest['files']['../outside'] = {'sha256': '0' * 64, 'bytes': 0}
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            corpus.validate_manifest(root)

    def test_streaming_interface_yields_without_materializing_million_rows(self):
        stream = corpus.iter_addresses(2409, 1000000)
        rows = list(itertools.islice(stream, 12))
        self.assertEqual(rows, list(corpus.iter_addresses(2409, 12)))

    def test_project_has_only_local_sources_and_no_author_secrets_or_macros(self):
        path = corpus.FIXTURES / 'templates/rich-style.qgs'
        root = ET.fromstring(path.read_bytes())
        sources = [node.text for node in root.findall('.//maplayer/datasource')]
        self.assertEqual(set(sources), {'./addresses.geojson', './roads.geojson',
                                       './parcels.geojson', './raster/multiband.vrt'})
        self.assertEqual(len(sources), 4)
        self.assertFalse(root.findall('.//creation'))
        self.assertFalse(any(key in root.attrib for key in ('saveUser', 'saveUserFull', 'saveDateTime')))
        self.assertNotIn('/home/', path.read_text())
        self.assertFalse(any((node.text or '').strip() for node in root.findall('.//pythonCode')))

    def test_rewritten_manifest_cannot_authorize_external_native_references(self):
        for name in ('rich-style.qgs', 'raster/multiband.vrt'):
            root = self.generate('case-' + name.split('/')[0])
            path = root / name
            original = path.read_bytes()
            replacement = (original.replace(b'./addresses.geojson', b'http://example.invalid/data')
                           if name.endswith('.qgs') else
                           original.replace(b'multiband-band-1.raw', b'/outside/secret'))
            self.assertNotEqual(original, replacement)
            path.write_bytes(replacement)
            manifest_path = root / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['files'][name] = {'bytes': path.stat().st_size, 'sha256': corpus.digest(path)}
            manifest_path.write_text(json.dumps(manifest))
            corpus.validate_manifest(root)  # Self-reported hashes alone are insufficient.
            with self.assertRaisesRegex(ValueError, 'unapproved native'):
                corpus.validate_native_profile(root)

    def test_native_report_destination_uses_same_symlink_guard(self):
        outside = self.parent / 'outside'; outside.mkdir()
        link = self.parent / 'linked'; link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            corpus.checked_new_output(link / 'report.json')
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()

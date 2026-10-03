"""Independent-oracle regression checks; no service or installer acceptance."""
import copy
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

import journey_probe as probe


def image(*, centers=((128, 384), (256, 256)), color=(32, 120, 180)):
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))
    rows = bytearray()
    for y in range(512):
        rows.append(0)
        for x in range(512):
            rows.extend(color if any((x-cx)**2 + (y-cy)**2 <= 100 for cx, cy in centers) else (255,255,255))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',512,512,8,2,0,0,0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


class IndependentOracles(unittest.TestCase):
    def setUp(self):
        self.value = {'type': 'FeatureCollection', 'features': [
            {'id': 'private_points.1', 'properties': {'object_id': 1, 'label': 'PRIVATE_A'}, 'geometry': {'type': 'Point', 'coordinates': [1,1]}},
            {'id': 'private_points.2', 'properties': {'object_id': 2, 'label': 'PRIVATE_B'}, 'geometry': {'type': 'Point', 'coordinates': [2,2]}}]}

    def test_feature_semantics_and_order_independence(self):
        self.assertEqual(probe.features(json.dumps(self.value))['count'], 2)
        self.value['features'].reverse()
        self.assertEqual(probe.features(json.dumps(self.value))['object_ids'], [1,2])

    def test_feature_corruption_duplicate_and_boolean_id_rejected(self):
        mutations = [lambda v: v['features'][0].update(id='substituted'),
                     lambda v: v['features'][0]['properties'].update(object_id=True),
                     lambda v: v['features'][0]['properties'].update(object_id=2),
                     lambda v: v['features'][0]['properties'].update(label='PRIVATE_B'),
                     lambda v: v['features'][0]['geometry'].update(coordinates=[True,True]),
                     lambda v: v['features'][0]['geometry'].update(coordinates=[2,1]),
                     lambda v: v['features'].pop()]
        for modify in mutations:
            value = copy.deepcopy(self.value); modify(value)
            with self.assertRaises(ValueError): probe.features(json.dumps(value))

    def test_actual_png_content_and_declared_spatial_symbols(self):
        result = probe.pixels(image())
        self.assertEqual(result['size'], [512,512])
        self.assertEqual(result['non_background_pixels'], 634)

    def test_header_only_blank_wrong_color_location_and_crc_rejected(self):
        for body in (image()[:33], image(centers=()), image(centers=((200,200),(400,400))),
                     image(color=(255,0,0)), image()[:-1] + b'\x00'):
            with self.assertRaises((ValueError,zlib.error)): probe.pixels(body)

    def test_transparent_color_key_cannot_pass_opaque_pixel_oracle(self):
        kind, value = b'tRNS', struct.pack('>HHH',32,120,180)
        chunk = struct.pack('>I',len(value)) + kind + value + struct.pack('>I',zlib.crc32(kind+value))
        encoded = image(); encoded = encoded[:33] + chunk + encoded[33:]
        with self.assertRaisesRegex(ValueError,'opaque'): probe.pixels(encoded)


class CreatedTokenCleanup(unittest.TestCase):
    """Pure client lifecycle tests; no HTTP, engine, or permission substitute."""
    def setUp(self):
        self.created, self.revocations, self.grants = [], [], set()
        self.login_failure = None
        self.response_change = None
        self.revoke_failure = None
        test = self
        class Browser(probe.TrackedOAuthBrowser):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.number = len(test.created)
                test.created.append(self)
            def authorize(self, username, password):
                if test.login_failure == self.number: raise ValueError('synthetic login failure')
                return probe.protocol.AuthorizationCode('code', 'v' * 48, 'state', self.redirect_uri)
            def token_request(self, form):
                if test.response_change == 'transport_failure': raise OSError('synthetic lost response')
                value = {'access_token': ('access-' + str(self.number) + '-') * 8,
                         'refresh_token': ('refresh-' + str(self.number) + '-') * 8,
                         'scope': 'read write', 'expires_in': 3600, 'token_type': 'bearer'}
                test.grants.update((value['access_token'], value['refresh_token']))
                if callable(test.response_change): test.response_change(value)
                return probe.protocol.Response(200, [], json.dumps(value).encode(), self.origin + '/o/token/')
            def revoke(self, token, hint='access_token'):
                test.revocations.append((self.number, hint, token))
                if test.revoke_failure == len(test.revocations):
                    raise OSError('sensitive diagnostic must not enter receipt: ' + token)
                test.grants.discard(token)
                return probe.protocol.Response(200, [], b'', self.origin + '/o/revoke_token/')
        self.browser_patch = patch.object(probe, 'TrackedOAuthBrowser', Browser)
        self.browser_patch.start()
        self.journey = object.__new__(probe.Journey)
        self.journey.product = {'listen': {'port': 8787}, 'owner': 'publisher', 'viewer': 'viewer',
                                'install_id': 'c1009991-b05e-4547-9b24-64d6c3976650', 'bundle': {'sha256': '1' * 64}}
        self.journey.secrets = {'oauth_client': 'synthetic-client', 'oauth_secret': 's' * 64,
                                'owner_password': 'o' * 64, 'viewer_password': 'v' * 64}
        self.journey.browsers = []; self.journey.rows = []; self.journey.cleanup_result = None

    def tearDown(self): self.browser_patch.stop()

    def exercise(self, fail=False):
        self.journey.login('owner'); self.journey.login('viewer')
        if fail: raise ValueError('synthetic later assertion failure')
        return {'synthetic': True}

    def test_success_retains_token_sets_and_revokes_both_families(self):
        self.journey.exercise = self.exercise
        self.assertEqual(self.journey.run(), {'synthetic': True})
        self.assertFalse(self.grants)
        self.assertEqual([kind for _, kind, _ in self.revocations], ['refresh_token', 'access_token'] * 2)
        self.assertEqual([len(browser.token_sets) for browser in self.created], [1, 1])
        self.assertTrue(self.journey.cleanup_result['complete'])

    def test_partial_second_login_failure_still_revokes_first_family(self):
        self.login_failure = 1; self.journey.exercise = self.exercise
        with self.assertRaisesRegex(ValueError, 'login failure'): self.journey.run()
        self.assertFalse(self.grants)
        self.assertEqual(len(self.revocations), 2)
        self.assertTrue(self.journey.cleanup_result['complete'])

    def test_later_assertion_failure_revokes_all_created_tokens(self):
        self.journey.exercise = lambda: self.exercise(fail=True)
        with self.assertRaisesRegex(ValueError, 'later assertion'): self.journey.run()
        self.assertFalse(self.grants)
        self.assertEqual(len(self.revocations), 4)

    def test_scope_validation_failure_cleans_already_issued_tokens(self):
        self.response_change = lambda value: value.update(scope='read')
        self.journey.exercise = self.exercise
        with self.assertRaisesRegex(ValueError, 'scope'): self.journey.run()
        self.assertFalse(self.grants)
        self.assertEqual(len(self.revocations), 2)

    def test_token_metadata_parse_failure_preserves_cleanup_candidates(self):
        self.response_change = lambda value: value.update(expires_in='not-an-integer')
        self.journey.exercise = self.exercise
        with self.assertRaises(probe.protocol.ProtocolError): self.journey.run()
        self.assertFalse(self.grants)
        self.assertEqual(len(self.revocations), 2)
        self.assertEqual(len(self.created[0].token_sets), 0)
        self.assertTrue(self.journey.cleanup_result['complete'])

    def test_lost_issuance_response_cannot_claim_complete_cleanup(self):
        self.response_change = 'transport_failure'; self.journey.exercise = self.exercise
        with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'): self.journey.run()
        self.assertFalse(self.journey.cleanup_result['complete'])
        self.assertEqual(self.journey.cleanup_result['unaccounted_issuance_principals'], ['owner'])

    def test_malformed_access_still_revokes_known_refresh_without_claiming_cleanup(self):
        self.response_change = lambda value: value.update(access_token=42)
        self.journey.exercise = self.exercise
        with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'): self.journey.run()
        self.assertEqual([kind for _, kind, _ in self.revocations], ['refresh_token'])
        self.assertFalse(self.journey.cleanup_result['complete'])

    def test_malformed_refresh_still_revokes_known_access_without_claiming_cleanup(self):
        self.response_change = lambda value: value.update(refresh_token=42)
        self.journey.exercise = self.exercise
        with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'): self.journey.run()
        self.assertEqual([kind for _, kind, _ in self.revocations], ['access_token'])
        self.assertFalse(self.journey.cleanup_result['complete'])

    def test_cleanup_failure_attempts_remaining_tokens_and_prevents_success(self):
        self.revoke_failure = 1; self.journey.exercise = self.exercise
        with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'): self.journey.run()
        self.assertEqual(len(self.revocations), 4)
        self.assertEqual(len(self.grants), 1)
        self.assertFalse(self.journey.cleanup_result['complete'])
        receipt = json.dumps(self.journey.cleanup_result)
        self.assertNotIn('sensitive diagnostic', receipt)
        self.assertTrue(all(token not in receipt for _, _, token in self.revocations))

    def test_browser_registry_values_block_receipt_even_after_cleanup(self):
        self.journey.exercise = self.exercise; self.journey.run()
        self.created[0].secrets.add('synthetic-cookie/value')
        self.assertTrue(self.journey.contains_secret('synthetic-cookie%2Fvalue'))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'new-evidence'
            self.journey.run = lambda: {'injected_cookie': 'synthetic-cookie/value'}
            with patch.object(probe, 'Journey', return_value=self.journey):
                with self.assertRaisesRegex(RuntimeError, 'secret scan'):
                    probe.main(SimpleNamespace(output=output, directory=Path(directory)))
            self.assertFalse((output / 'result.json').exists())


if __name__ == '__main__': unittest.main()

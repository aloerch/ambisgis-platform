"""Independent-oracle regression checks; no service or installer acceptance."""
import copy
import json
import struct
import unittest
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


if __name__ == '__main__': unittest.main()
